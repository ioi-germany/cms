#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2025 Chuyang Wang <mail@chuyang-wang.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import traceback
import sys
import asyncio
import signal
from typing import Optional, List, Any, Dict, Tuple, Union

from time import sleep

import discord
from discord.ext import commands
from discord import app_commands

from cms import config
from cms.db import Session, Contest, Question, Participation, Announcement
from cms.db.util import get_contest_list
from cms.io import Service
from cmscommon.datetime import make_datetime

logger = logging.getLogger(__name__)

def strip_cmd(s: str) -> str:
    """Remove the command part from a message."""
    return " ".join(s.split(' ')[1:])

def split_off_header(s: str) -> Tuple[str, str]:
    """Split message into header and body."""
    lines = s.split('\n')
    return lines[0], "\n".join(lines[1:])

def bold(s: str) -> str:
    """Format text as bold in Discord markdown."""
    return "**" + s + "**"

def italic(s: str) -> str:
    """Format text as italic in Discord markdown."""
    return "*" + s + "*"

def code_block(s: str) -> str:
    """Format text as code block in Discord markdown."""
    return "```\n" + s + "\n```"

def code_inline(s: str) -> str:
    """Format text as inline code in Discord markdown."""
    return "`" + s + "`"

_session = Session()


class WithDatabaseAccess:
    """Base class for database access"""
    def __init__(self, sql_session: Any) -> None:
        self.sql_session = sql_session

    def _commit(self) -> None:
        self.sql_session.commit()


class MyQuestion(WithDatabaseAccess):
    """Thin wrapper around question"""
    def __init__(self, question: Question) -> None:
        self.question = question
        self.replied_by: Optional[str] = None
        super(MyQuestion, self).__init__(Session.object_session(self.question))

    def answer(self, a: str, is_short: bool = True, replied_by: Optional[str] = None) -> Any:
        self.question.last_action = make_datetime()
        self.question.reply_timestamp = self.question.last_action

        self.question.reply_subject = ""
        self.question.reply_text = "" 
        if is_short:
            self.question.reply_subject = a
        else:
            self.question.reply_text = a

        self.question.reply_source = "discord"
        self.question.ignored = False
        self.replied_by = replied_by

        return self._commit()

    def ignore(self) -> Any:
        self.question.last_action = make_datetime()
        self.question.ignored = True
        self.question.reply_source = "discord"

        return self._commit()

    def answered(self) -> bool:
        return self.question.reply_timestamp is not None

    def update(self) -> None:
        self.question = Question.get_from_id(self.question.id, self.sql_session)

    def ignored(self) -> bool:
        return self.question.ignored

    def handled(self) -> bool:
        return self.ignored() or self.answered()

    def get_answer(self) -> Tuple[str, str]:
        return self.question.reply_subject, self.question.reply_text

    def format_answer(self) -> str:
        x, y = self.get_answer()
        return bold(x) if x else y

    def status_text(self) -> str:
        if self.answered():
            answer = self.format_answer()
            reply_info = f"This question has been answered by {self.replied_by}:"
            return italic(reply_info) + "\n" + answer
        elif self.ignored():
            return italic("This question has been ignored.")
        else:
            return italic("This question is currently open.")

    def get_title(self) -> str:
        subject = self.question.subject
        if len(subject) > 60:
            subject = subject[:60] + "..."
        return f"Q{self.question.id}: {subject}"

    def format(self, new: bool) -> str:
        Q = self.question

        return bold("contest: ") + \
               "{}\n".format(Q.participation.contest.description) + \
               bold("from: ") + Q.participation.user.username + \
               "\n" + bold("timestamp: ") + \
               "{}".format(Q.question_timestamp) + "\n\n" + \
               (bold(Q.subject) + "\n" + Q.text).strip() + \
               "\n\n" + self.status_text()


class ListOfDatabaseEntries:
    def __init__(self, contest_id: int) -> None:
        self.sql_session = _session
        self.contest_id = contest_id

    def _new_session(self) -> None:
        self.sql_session.commit()
        self.sql_session.expire_all()


class QuestionList(ListOfDatabaseEntries):
    """Keeps track of all questions"""
    def __init__(self, contest_id: int) -> None:
        super(QuestionList, self).__init__(contest_id)

        self.question_times: Dict[int, Any] = {}
        self.action_times: Dict[int, Any] = {}
        # Initialize with existing questions to avoid duplicates on startup
        self._initialize_existing_questions()

    def _initialize_existing_questions(self) -> None:
        """Initialize tracking dictionaries with existing questions to avoid posting them on startup"""
        for q in self._get_questions():
            self.question_times[q.id] = q.question_timestamp
            self.action_times[q.id] = q.last_action

    def poll(self) -> Tuple[List[MyQuestion], List[MyQuestion], List[MyQuestion], List[MyQuestion], List[MyQuestion]]:
        question_list = self._get_questions()

        new_questions = []
        new_answers = []
        ignores = []
        unignores = []
        updated_answers = []

        for q in question_list:
            # Case 1: new question
            if q.id not in self.question_times:
                # We don't mention questions that are already replied to or
                # marked as ignored
                if not q.ignored and q.reply_timestamp is None:
                    new_questions.append(MyQuestion(q))

            # Case 2: old question
            elif q.reply_source == "web":
                old_last_action = self.action_times.get(q.id)

                # Case 2.1: ignored
                if q.ignored:
                    if q.last_action != old_last_action:
                        ignores.append(MyQuestion(q))

                # Case 2.2: answered
                elif q.reply_timestamp is not None:
                    # Case 2.2.1: first answer
                    if self.action_times[q.id] is None:
                        new_answers.append(MyQuestion(q))

                    # Case 2.2.2: edited answer
                    elif q.last_action != old_last_action:
                        updated_answers.append(MyQuestion(q))

                # Case 2.3: unignored
                else:
                    if q.last_action != old_last_action:
                        unignores.append(MyQuestion(q))

            self.question_times[q.id] = q.question_timestamp
            self.action_times[q.id] = q.last_action

        return new_questions, new_answers, updated_answers, ignores, unignores

    def open_questions(self) -> List[MyQuestion]:
        return [MyQuestion(q) for q in self._get_questions()
                              if q.reply_timestamp is None and not q.ignored]

    def all(self) -> List[MyQuestion]:
        return [MyQuestion(q) for q in self._get_questions()]

    def _get_questions(self) -> List[Question]:
        self._new_session()

        return self.sql_session.query(Question).join(Participation)\
                   .filter(Participation.contest_id == self.contest_id)\
                   .order_by(Question.question_timestamp.desc())\
                   .order_by(Question.id).all()


class MyAnnouncement(WithDatabaseAccess):
    """Thin wrapper around announcement"""
    def __init__(self, announcement: Announcement) -> None:
        self.announcement = announcement
        super(MyAnnouncement, self).\
            __init__(Session.object_session(self.announcement))

    def format(self) -> str:
        A = self.announcement

        return bold("contest: ") + \
               "{}\n".format(A.contest.description) + \
               bold("timestamp: ") + \
               "{}\n\n".format(A.timestamp) + \
               bold(A.subject) + "\n" + A.text


class AnnouncementList(ListOfDatabaseEntries):
    """Keeps track of all announcements"""
    def __init__(self, contest_id: int) -> None:
        super(AnnouncementList, self).__init__(contest_id)
        self.announcements: set[int] = set()
        # Initialize with existing announcements to avoid posting them on startup
        self._initialize_existing_announcements()

    def _initialize_existing_announcements(self) -> None:
        """Initialize the tracking set with existing announcements to avoid posting them on startup"""
        for a in self._get_announcements():
            self.announcements.add(a.id)

    def poll(self) -> List[MyAnnouncement]:
        r = []

        for a in self._get_announcements():
            if a.id not in self.announcements:
                self.announcements.add(a.id)
                r.append(MyAnnouncement(a))

        return r

    def all(self) -> List[MyAnnouncement]:
        return [MyAnnouncement(a) for a in self._get_announcements()]

    def _get_announcements(self) -> List[Announcement]:
        self._new_session()
        res = self.sql_session.query(Announcement)\
                   .filter(Announcement.contest_id == self.contest_id)
        assert res is not None
        return res


class MyContest(WithDatabaseAccess):
    """Encapsulates access to the contest currently running"""
    def __init__(self, contest_id: int) -> None:
        super(MyContest, self).__init__(_session)

        self.contest_id = contest_id
        self.contest = Contest.get_from_id(contest_id, self.sql_session)
        self.name = self.contest.name
        self.description = self.contest.description
        self.questions = QuestionList(self.contest_id)
        self.announcements = AnnouncementList(self.contest_id)

    def announce(self, header: str, body: str) -> Any:
        ann = Announcement(timestamp=make_datetime(), 
                          subject=header, 
                          text=body, 
                          src="discord",
                          contest=self.contest)
        self.sql_session.add(ann)
        return self._commit()

    def poll_questions(self) -> Tuple[List[MyQuestion], List[MyQuestion], List[MyQuestion], List[MyQuestion], List[MyQuestion]]:
        return self.questions.poll()

    def get_all_open_questions(self) -> List[MyQuestion]:
        return self.questions.open_questions()

    def get_all_questions(self) -> List[MyQuestion]:
        return self.questions.all()

    def poll_announcements(self) -> List[MyAnnouncement]:
        return self.announcements.poll()

    def get_all_announcements(self) -> List[MyAnnouncement]:
        return self.announcements.all()


class DiscordBot(commands.Bot):
    """A Discord bot that allows easy access to all the communication
    (Clarification Requests/Announcements/etc) happening"""

    def __init__(self, contests: Optional[List[MyContest]] = None, only_listen_to: Optional[int] = None) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents, help_command=None)

        self.pwd: str = getattr(config, 'discord_bot_pwd', 'pwd')  # Password needed during startup
        self.admin_roles: List[str] = getattr(config, 'discord_bot_admin_roles', [])  # Admin roles that can start without password
        self.channel_id: Optional[int] = only_listen_to   # We will only communicate with this channel
        self.contests: List[MyContest] = contests or []
        self.questions: Dict[int, MyQuestion] = {}
        self.q_notifications: Dict[int, List[Dict[str, Any]]] = {}
        self.messages_issued: List[discord.Message] = []
        self.err_count: int = 0
        self.MAX_ERR_COUNT: int = getattr(config, 'discord_bot_max_error_messages', 10)
        self.is_registered: bool = False


    async def on_ready(self) -> None:
        logger.info('%s has connected to Discord!', self.user)
        if not hasattr(self, '_update_task') or self._update_task.done():
            self._update_task = self.loop.create_task(self._update_loop())

    async def _send_error_to_channel(self, error_msg: str) -> None:
        """Helper function to send error messages to the registered channel"""
        if self.channel_id is not None and self.is_registered:
            channel = self.get_channel(self.channel_id)
            if channel and hasattr(channel, 'send'):
                try:
                    await channel.send(error_msg)
                except Exception as e:
                    logger.error("Failed to send error message to channel: %s", e)

    async def on_error(self, event: str, *args: Any, **kwargs: Any) -> None:
        error = sys.exc_info()[1]
        if error:
            err = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            logger.error("Discord bot error in %s: %s", event, err)

            if self.channel_id is not None and self.is_registered:
                self.err_count += 1

                error_msg = f"⚠️ **Error occurred** ⚠️\n```\n{err}\n```"
                if len(error_msg) > 2000:
                    error_msg = error_msg[:1997] + "..."

                await self._send_error_to_channel(error_msg)

                if self.err_count >= self.MAX_ERR_COUNT:
                    await self._send_error_to_channel("I think I'm gonna lay down for a while...\n(Bot shutdown. Reason: Maximum error count exceeded.)")
                    await self.close()

    def _is_channel_authorized(self, channel_id: int) -> bool:
        """Check if the channel is authorized for bot operations"""
        if not self.is_registered:
            return False
        
        # Direct channel match
        if channel_id == self.channel_id:
            return True
            
        # Thread in authorized channel
        channel = self.get_channel(channel_id)
        if isinstance(channel, discord.Thread) and channel.parent_id == self.channel_id:
            return True
            
        return False

    def _user_has_admin_role(self, user: Union[discord.User, discord.Member]) -> bool:
        """Check if the user has any of the configured admin roles"""
        if not self.admin_roles:
            return False
        
        # Only Members (users in a guild) have roles, not direct message users
        if not isinstance(user, discord.Member):
            return False
        
        user_role_names = [role.name for role in user.roles]
        return any(role_name in user_role_names for role_name in self.admin_roles)

    async def setup_hook(self) -> None:
        """Called when the bot is starting up"""
        await self.add_cog(ContestCommands(self))
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info("Synced %d slash command(s)", len(synced))
        except discord.DiscordException as e:
            logger.error("Failed to sync slash commands: %s", e)

    async def _update_loop(self) -> None:
        """Check for new questions, answers, and announcements"""
        while not self.is_closed():
            try:
                if not self.is_registered or self.channel_id is None:
                    await asyncio.sleep(5)
                    continue

                channel = self.get_channel(self.channel_id)
                if not channel:
                    await asyncio.sleep(5)
                    continue

                await self._process_all_contests(channel)

            except Exception as e:
                logger.error("Error in update loop: %s", e)
            
            await asyncio.sleep(5)

    async def _process_all_contests(self, channel: Union[discord.TextChannel, discord.Thread]) -> None:
        """Process all contests for updates"""
        for c in self.contests:
            try:
                await self._process_contest_updates(channel, c)
            except Exception as e:
                logger.error("Error processing contest %s: %s", c.contest_id, e)

    async def _process_contest_updates(self, channel: Union[discord.TextChannel, discord.Thread], contest: MyContest) -> None:
        """Process updates for a single contest"""
        new_qs, new_as, updated_as, ignored_qs, unignored_qs = contest.poll_questions()

        # Process question updates
        for q in new_qs:
            await self._notify_question(channel, q, True)

        for q in new_as:
            await self._notify_answer(channel, q, True)

        for q in updated_as:
            await self._notify_answer(channel, q, False)

        for q in ignored_qs:
            await self._notify_question_ignore(channel, q, True)

        for q in unignored_qs:
            await self._notify_question_ignore(channel, q, False)

        # Process announcements
        new_announcements = contest.poll_announcements()
        for a in new_announcements:
            await self._notify_announcement(channel, a, True)

    async def _create_embed_for_question(self, q: MyQuestion, new: bool) -> discord.Embed:
        """Create a Discord embed for a question"""
        return discord.Embed(
            title=q.get_title(),
            description=q.format(new),
            color=0xff6b6b if new else 0x4ecdc4
        )

    async def _notify_question(self, channel: Union[discord.TextChannel, discord.Thread], q: MyQuestion, new: bool) -> None:
        """Send a question notification with buttons and create a thread"""
        embed = await self._create_embed_for_question(q, new)

        view = QuestionView(self, q)
        message = await channel.send(embed=embed, view=view)
        
        # Create a thread for this question
        thread_name = f"Q{q.question.id}: {q.question.subject[:80]}"  # Discord thread name limit
        thread = await message.create_thread(name=thread_name, auto_archive_duration=1440)  # 24 hours
        
        # Store both message and thread references
        self.questions[message.id] = q
        
        Q = q.question
        if Q.id not in self.q_notifications:
            self.q_notifications[Q.id] = []
        
        # Store both message and thread
        notification_data = {
            'message': message,
            'thread': thread
        }
        self.q_notifications[Q.id].append(notification_data)
        self.messages_issued.append(message)
        
        # Send initial message to thread with buttons for replying
        thread_message = await thread.send(
            "Reply in this thread to answer the question."
        )
        self.questions[thread_message.id] = q

    async def _notify_answer(self, channel: Union[discord.TextChannel, discord.Thread], q: MyQuestion, new: bool) -> None:
        """Notify about an answer given via web interface"""
        if q.question.id not in self.q_notifications:
            return

        def map_reply_source(reply_source: str) -> str:
            if reply_source == "web":
                return "CMS Web"
            elif reply_source == "discord":
                return "Discord"
            elif reply_source == "telegram":
                return "Telegram"
            return reply_source if len(reply_source) > 0 else "Unknown"

        q.replied_by = map_reply_source(q.question.reply_source)

        notification_data = self.q_notifications[q.question.id][-1]
        msg = notification_data['message']
        thread = notification_data['thread']
        
        notification = f"This question has been answered via {q.replied_by}:\n\n" if new \
                       else f"The answer has been edited via {q.replied_by}:\n\n"

        reply_text = notification + q.format_answer()
        if len(reply_text) > 2000:
            reply_text = reply_text[:1997] + "..."

        # Send notification to the thread instead of as a reply
        reply = await thread.send(reply_text)
        self.questions[reply.id] = q
        self.messages_issued.append(reply)
        
        # Update the original message
        await self._update_question(q)

    async def _notify_question_ignore(self, channel: Union[discord.TextChannel, discord.Thread], q: MyQuestion, ignore: bool) -> None:
        """Notify about a question being ignored/unignored"""
        if q.question.id not in self.q_notifications:
            return

        notification_data = self.q_notifications[q.question.id][-1]
        msg = notification_data['message']
        thread = notification_data['thread']
        
        notification = f"This question has been {'ignored' if ignore else 'unignored'}."
        
        # Send notification to the thread instead of as a reply
        reply = await thread.send(notification)
        self.questions[reply.id] = q
        self.messages_issued.append(reply)
        
        # Update the original message
        await self._update_question(q)

    async def _notify_announcement(self, channel: Union[discord.TextChannel, discord.Thread], a: MyAnnouncement, new: bool) -> None:
        """Send an announcement notification"""
        embed = discord.Embed(
            title=f"ANNOUNCEMENT {a.announcement.id}",
            description=a.format(),
            color=0x5545D1
        )

        message = await channel.send(embed=embed)
        self.messages_issued.append(message)

    async def _update_question(self, q: MyQuestion) -> None:
        """Update question message with current status"""
        if q.question.id not in self.q_notifications:
            return

        for notification_data in self.q_notifications[q.question.id]:
            try:
                msg = notification_data['message']
                embed = discord.Embed(
                    title=f"QUESTION {q.question.id}",
                    description=q.format(False),
                    color=0x4ecdc4
                )
                # Only show buttons if question is still open
                view = QuestionView(self, q) if not q.handled() else None
                await msg.edit(embed=embed, view=view)
            except discord.NotFound:
                logger.info("Question message was already deleted")
            except Exception as e:
                logger.error("Failed to update question message: %s", str(e))

    async def _get_replier_name(self, ctx: Union[discord.Interaction, discord.Message]) -> str:
        """Get the name of the person replying"""
        if isinstance(ctx, discord.Interaction):
            return ctx.user.display_name
        elif isinstance(ctx, discord.Message):
            return ctx.author.display_name
        else:
            return "Unknown"

    def _get_replier_user(self, ctx: Union[discord.Interaction, discord.Message]) -> Optional[Union[discord.User, discord.Member]]:
        """Get the user object of the person replying for mentions"""
        if isinstance(ctx, discord.Interaction):
            return ctx.user
        elif isinstance(ctx, discord.Message):
            return ctx.author
        else:
            return None

    async def _send_reply_message(self, ctx: Union[discord.Interaction, discord.Message], message: str, in_thread: bool = False) -> Optional[discord.Message]:
        """Send a reply message to the appropriate location"""
        if in_thread and hasattr(ctx, 'channel') and hasattr(ctx.channel, 'send'):
            return await ctx.channel.send(message)
        elif isinstance(ctx, discord.Message):
            return await ctx.reply(message)
        elif isinstance(ctx, discord.Interaction):
            if ctx.response.is_done():
                return await ctx.followup.send(message)
            else:
                await ctx.response.send_message(message)
                return None
        return None

    async def _reply_question(self, ctx: Union[discord.Interaction, discord.Message], q: MyQuestion, answer: str, 
                             short_answer: bool = False, in_thread: bool = False) -> None:
        """Reply to a user question"""
        replier = await self._get_replier_name(ctx)
            
        if answer.strip() == "/ignore":
            if q.answered():
                fail_msg = "This question has already been answered; I can't ignore it anymore ☹."
                if not short_answer:
                    await self._send_reply_message(ctx, fail_msg, in_thread)
                # For short_answer (button clicks), we don't send individual failure messages
                # since the public message is handled in _handle_reply
            else:
                q.ignore()
                if not short_answer:
                    success_msg = "I have ignored this question!"
                    await self._send_reply_message(ctx, success_msg, in_thread)
                # For short_answer (button clicks), success message is handled in _handle_reply
                
                await self._update_question(q)
            return

        q.answer(answer, short_answer, replied_by=replier)

        if not short_answer:
            user = self._get_replier_user(ctx)
            if user:
                success_msg = f"✅ {user.mention} I have added your answer!"
            else:
                success_msg = f"✅ @{replier} I have added your answer!"
            reply = await self._send_reply_message(ctx, success_msg, in_thread)
            if reply is not None and hasattr(reply, 'id'):
                self.questions[reply.id] = q
                self.messages_issued.append(reply)
        # For short_answer (button clicks), success message is handled in _handle_reply

        await self._update_question(q)


class QuestionView(discord.ui.View):
    """View with buttons for question responses"""
    
    def __init__(self, bot: DiscordBot, question: MyQuestion, in_thread: bool = False) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.question = question
        self.in_thread = in_thread

    @discord.ui.button(label='Yes', style=discord.ButtonStyle.green)
    async def yes_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_reply(interaction, "Yes")

    @discord.ui.button(label='No', style=discord.ButtonStyle.red)
    async def no_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_reply(interaction, "No")

    @discord.ui.button(label='Answered in task description', style=discord.ButtonStyle.secondary)
    async def task_desc_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_reply(interaction, "Answered in task description")

    @discord.ui.button(label='No comment', style=discord.ButtonStyle.secondary)
    async def no_comment_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_reply(interaction, "No comment")

    @discord.ui.button(label='Invalid question', style=discord.ButtonStyle.secondary)
    async def invalid_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_reply(interaction, "Invalid question")

    @discord.ui.button(label='Ignore', style=discord.ButtonStyle.danger)
    async def ignore_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_reply(interaction, "/ignore")

    def _is_channel_authorized(self, interaction: discord.Interaction) -> bool:
        """Check if the interaction is from an authorized channel"""
        if not self.bot.is_registered:
            return False
        
        if interaction.channel_id == self.bot.channel_id:
            return True
        
        if isinstance(interaction.channel, discord.Thread) and interaction.channel.parent_id == self.bot.channel_id:
            return True
            
        return False

    async def _send_thread_notification(self, interaction: discord.Interaction, public_message: str) -> None:
        """Send notification to the appropriate thread"""
        if self.question.question.id in self.bot.q_notifications:
            notification_data = self.bot.q_notifications[self.question.question.id][-1]
            thread = notification_data['thread']
            
            # Send the public message to the thread
            await thread.send(public_message)
            
            # Send a brief acknowledgment to the interaction
            await interaction.followup.send("Response recorded!", ephemeral=True)
        else:
            # Fallback: send to the interaction location if thread not found
            await interaction.followup.send(public_message, ephemeral=False)

    async def _handle_reply(self, interaction: discord.Interaction, answer: str) -> None:
        """Handle button click replies"""
        if not self._is_channel_authorized(interaction):
            await interaction.response.send_message("Unauthorized access!", ephemeral=True)
            return

        # Acknowledge the interaction first
        await interaction.response.defer()
        
        # Handle the reply in the database
        await self.bot._reply_question(interaction, self.question, answer, short_answer=True, in_thread=self.in_thread)
        
        # Send a message about the action
        user = interaction.user
        question_preview = (self.question.question.subject[:50] + "...") if len(self.question.question.subject) > 50 else self.question.question.subject
        
        if answer == "/ignore":
            public_message = f"🚫 **{user.display_name}** ignored the question: \"{question_preview}\""
        else:
            public_message = f"✅ **{user.display_name}** answered \"{question_preview}\" with: **{answer}**"
        
        await self._send_thread_notification(interaction, public_message)


class ContestCommands(commands.Cog):
    """Commands for contest management"""
    
    def __init__(self, bot: DiscordBot) -> None:
        self.bot = bot


    # Slash Commands
    @app_commands.command(name="start", description="Register the bot to this channel")
    @app_commands.describe(password="Password to bind the bot (optional if you have admin role)")
    async def slash_start(self, interaction: discord.Interaction, password: Optional[str] = None):
        """Slash command version of start"""
        if not interaction.channel:
            await interaction.response.send_message("Error: Could not determine channel.", ephemeral=True)
            return
            
        # Create a mock context-like object for compatibility
        class MockContext:
            def __init__(self, interaction):
                self.channel = interaction.channel
                self.send = interaction.response.send_message
                
        ctx = MockContext(interaction)

        if self.bot.is_registered:
            if self.bot.channel_id == interaction.channel.id:
                await interaction.response.send_message("I'm already bound to this channel!", ephemeral=True)
                return
            else:
                await interaction.response.send_message("Error: I'm already registered with another channel", ephemeral=True)
                logger.error("%s tried to /start me although I'm already bound to a channel", interaction.user.name)
                
                if self.bot.channel_id:
                    channel = self.bot.get_channel(self.bot.channel_id)
                    if channel and hasattr(channel, 'send'):
                        await channel.send(f"Warning: {interaction.user.name} tried to /start me although I'm exclusively bound to this channel!")
                return

        async def register_success(is_admin_auth=False):
            # Everything is fine
            self.bot.channel_id = interaction.channel.id
            self.bot.is_registered = True

            message = f"Congratulations! I'm now bound to this channel! {'(Admin role authenticated)' if is_admin_auth else ''}\n"
            if len(self.bot.contests) == 1:
                message += "I'll assist you with the following contest.\n"
            else:
                message += "I'll assist you with the following contests.\n"
            
            for c in self.bot.contests:
                message += f"• **{c.name}**: {c.description}\n"

            await interaction.response.send_message(message)

        # Check if user has admin role (no password required)
        if self.bot._user_has_admin_role(interaction.user):
            # Admin user can start without password
            logger.info("Bot started by admin user %s in channel %s", interaction.user, interaction.channel.id)
            await register_success(is_admin_auth=True)
            return

        # Fallback to password authentication
        if not password:
            logger.warning("%s tried to /start the bot without a password in channel %s", interaction.user.name, interaction.channel.id)
            await interaction.response.send_message("Error: Password required for non-admin users.", ephemeral=True)
            return

        if password != self.bot.pwd:
            logger.warning("%s tried to /start the bot using a wrong password in channel %s", interaction.user.name, interaction.channel.id)
            await interaction.response.send_message("Error: wrong password", ephemeral=True)
            return

        await register_success()


    group_announcements = app_commands.Group(name="announcements", description="Manage announcements")
    @group_announcements.command(name="make", description="Make an announcement to the contest")
    @app_commands.describe(
        subject="The subject/title of the announcement",
        content="The content/body of the announcement"
    )
    async def slash_announcement_make(self, interaction: discord.Interaction, subject: str, content: str):
        """Slash command version of announce"""
        if not interaction.channel:
            await interaction.response.send_message("Error: Could not determine channel.", ephemeral=True)
            return
            
        if not self.bot.is_registered:
            await interaction.response.send_message("You have to register me first (using the `/start` command).", ephemeral=True)
            return

        if self.bot.channel_id != interaction.channel.id:
            logger.warning("Warning! Someone tried to make an announcement in a channel I'm not registered in!")
            channel = self.bot.get_channel(self.bot.channel_id)
            if channel and hasattr(channel, 'send'):
                await channel.send("Warning! Someone tried to make an announcement in another channel!")
            await interaction.response.send_message("Error: I'm not registered to this channel.", ephemeral=True)
            return

        if not subject or not content:
            await interaction.response.send_message("Error: Please provide both a subject and content for the announcement.", ephemeral=True)
            return

        if len(self.bot.contests) == 0:
            await interaction.response.send_message("There's no contest I could announce this in.", ephemeral=True)
            return

        # Use the provided subject and content directly instead of splitting
        header, msg = subject, content

        if len(self.bot.contests) > 1:
            view = SlashAnnouncementView(self.bot, interaction, header, msg)
            await interaction.response.send_message("Which contest would you like to announce this in?", view=view, ephemeral=True)
        else:
            await self._do_slash_announce(interaction, 0, header, msg)

    async def _do_slash_announce(self, interaction: discord.Interaction, contest_id, header, msg):
        """Actually make the announcement via slash command"""
        contest = self.bot.contests[contest_id]
        try:
            contest.announce(header, msg)
            
            # Get the user who made the announcement
            announcer = interaction.user.display_name
            
            response_msg = f"I have announced the following in {contest.description}:\n\n**{header}**\n{msg}"
            
            # Check if we already responded
            if not interaction.response.is_done():
                await interaction.response.send_message(response_msg, ephemeral=True)
            else:
                await interaction.followup.send(response_msg, ephemeral=True)
                
            # Send public message about who made the announcement
            public_msg = f"📢 **{announcer}** has announced the following in {contest.description}:\n\n**{header}**\n{msg}"
            
            # Check if the channel supports sending messages (TextChannel, Thread, etc.)
            if interaction.channel and hasattr(interaction.channel, 'send'):
                try:
                    await interaction.channel.send(public_msg)
                except Exception as e:
                    logger.error("Failed to send public announcement message: %s", str(e))
            
        except Exception as e:
            logger.error("Failed to make announcement: %s", e, stack_info=True)
            error_msg = "Sorry, this didn't work..."
            if not interaction.response.is_done():
                await interaction.response.send_message(error_msg, ephemeral=True)
            else:
                await interaction.followup.send(error_msg, ephemeral=True)

    @group_announcements.command(name="list", description="List all announcements")
    async def slash_announcements_list(self, interaction: discord.Interaction):
        """Slash command version of allannouncements"""
        if not interaction.channel:
            await interaction.response.send_message("Error: Could not determine channel.", ephemeral=True)
            return
            
        if not self.bot.is_registered:
            await interaction.response.send_message("You have to register me first (using the `/start` command).", ephemeral=True)
            return

        if self.bot.channel_id != interaction.channel.id:
            logger.warning("Warning! Someone tried to list all announcements in a channel I'm not registered in!")
            channel = self.bot.get_channel(self.bot.channel_id)
            if channel and hasattr(channel, 'send'):
                await channel.send("Warning! Someone tried to list all announcements in another channel!")
            await interaction.response.send_message("Error: I'm not registered to this channel.", ephemeral=True)
            return

        announcements = [a for c in self.bot.contests for a in c.get_all_announcements()]

        if len(announcements) == 0:
            notification = "There are currently **no** announcements"
        elif len(announcements) == 1:
            notification = "There is currently **1** announcement:"
        else:
            notification = f"There are currently **{len(announcements)}** announcements:"

        await interaction.response.send_message(notification)

        for a in announcements:
            await self.bot._notify_announcement(interaction.channel, a, False)

    group_questions = app_commands.Group(name="questions", description="Manage questions")

    @group_questions.command(name="list", description="List all open questions")
    async def slash_questions_list(self, interaction: discord.Interaction):
        """Slash command version of openquestions"""
        if not interaction.channel:
            await interaction.response.send_message("Error: Could not determine channel.", ephemeral=True)
            return
            
        if not self.bot.is_registered:
            await interaction.response.send_message("You have to register me first (using the `/start` command).", ephemeral=True)
            return

        if self.bot.channel_id != interaction.channel.id:
            logger.warning("Warning! Someone tried to list open questions in a channel I'm not registered in!")
            channel = self.bot.get_channel(self.bot.channel_id)
            if channel and hasattr(channel, 'send'):
                await channel.send("Warning! Someone tried to list open questions in another channel!")
            await interaction.response.send_message("Error: I'm not registered to this channel.", ephemeral=True)
            return

        qs = [q for c in self.bot.contests for q in c.get_all_open_questions()]

        if len(qs) == 0:
            notification = "There are currently **no** open questions"
        elif len(qs) == 1:
            notification = "There is currently **1** open question:"
        else:
            notification = f"There are currently **{len(qs)}** open questions:"

        await interaction.response.send_message(notification)

        for q in qs:
            await self.bot._notify_question(interaction.channel, q, False)


    @app_commands.command(name="purge", description="Delete all messages sent by the bot during the current session")
    async def slash_purge(self, interaction: discord.Interaction):
        """Slash command version of purge"""
        if not interaction.channel:
            await interaction.response.send_message("Error: Could not determine channel.", ephemeral=True)
            return
            
        if not self.bot.is_registered:
            await interaction.response.send_message("You have to register me first (using the `/start` command) — and then there will be nothing to purge at the moment anyhow…", ephemeral=True)
            return

        if self.bot.channel_id != interaction.channel.id:
            logger.warning("Warning! Someone issued /purge in a channel I'm not registered in!")
            channel = self.bot.get_channel(self.bot.channel_id)
            if channel and hasattr(channel, 'send'):
                await channel.send("Warning! Someone tried to issue /purge in another channel!")
            await interaction.response.send_message("Error: I'm not registered to this channel.", ephemeral=True)
            return

        view = SlashPurgeView(self.bot, interaction)
        await interaction.response.send_message("Are you sure you want me to **delete** all messages I've sent during the current session?", view=view, ephemeral=True)

    @app_commands.command(name="help", description="Show help information about the bot")
    async def slash_help(self, interaction: discord.Interaction):
        """Slash command version of help"""
        help_text = """**Discord Bot for CMS Contest Management**

A bot allowing access to clarification requests and announcements of a CMS contest via Discord.

**Slash Commands (/):**
• `/help` — prints this message
• `/start [password]` — bind the bot to the current channel. Password is optional if you have an admin role.
• `/announcements list` — shows all announcements of the current contest
• `/announcements make <announcement_title> <announcement_content>` — adds the text as an announcement to the current contest
• `/questions list` — shows all *unanswered* questions of the current contest
• `/purge` — deletes all messages sent by the bot during the current session

**Authentication:**
The bot can be started either with a password or by users with configured admin roles. Admin roles are configured in the CMS configuration file.

**Question Management:**
In addition this bot will post all new questions appearing in the system. You can answer them by replying to the corresponding message or using the quick-response buttons. Moreover, all answers given and announcements made via the web interface will also be posted and you can edit answers by replying to the corresponding message.

**Quick Response Buttons:**
✅ **Yes** — Simple affirmative answer
❌ **No** — Simple negative answer  
📋 **Answered in task description** — Refer to task documentation
💭 **No comment** — Decline to answer
⚠️ **Invalid question** — Mark as invalid
🚫 **Ignore** — Mark question as ignored"""

        await interaction.response.send_message(help_text, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle replies to questions"""
        if message.author == self.bot.user:
            return

        if not self.bot.is_registered:
            return

        # Check if message is in the registered channel
        if message.channel.id == self.bot.channel_id:
            # Check if this is a reply to a bot message
            if message.reference and message.reference.message_id in self.bot.questions:
                q = self.bot.questions[message.reference.message_id]
                
                # Check if there's a thread for this question
                if q.question.id in self.bot.q_notifications:
                    notification_data = self.bot.q_notifications[q.question.id][-1]
                    thread = notification_data['thread']
                    
                    # Move the message to the thread
                    await self._move_message_to_thread(message, thread, q)
                else:
                    # No thread exists, handle normally
                    await self.bot._reply_question(message, q, message.content)
                    
        # Check if message is in a thread of the registered channel        
        elif isinstance(message.channel, discord.Thread) and message.channel.parent_id == self.bot.channel_id:
            # Find the question associated with this thread
            for question_id, notifications in self.bot.q_notifications.items():
                for notification_data in notifications:
                    if notification_data['thread'].id == message.channel.id:
                        # Found the question for this thread, get fresh question data
                        try:
                            fresh_question = Question.get_from_id(question_id, _session)
                            if fresh_question:
                                q = MyQuestion(fresh_question)
                                await self.bot._reply_question(message, q, message.content, in_thread=True)
                        except Exception as e:
                            logger.error("Failed to get question %s: %s", question_id, str(e))
                        return

    async def _move_message_to_thread(self, message, thread, question):
        """Move a message from the main channel to the appropriate thread"""
        try:
            # Send the content to the thread
            thread_message = f"**{message.author.display_name}** replied: {message.content}"
            await thread.send(thread_message)
            
            # Process the answer
            await self.bot._reply_question(message, question, message.content, in_thread=True)
            
            # Delete the original message and send a redirect message
            redirect_msg = f"Your reply has been moved to the question thread: {thread.mention}"
            await message.reply(redirect_msg, delete_after=10)
            await message.delete()
            
        except Exception as e:
            logger.error("Failed to move message to thread: %s", str(e))


class PurgeView(discord.ui.View):
    """View for purge confirmation"""
    
    def __init__(self, bot, ctx):
        super().__init__(timeout=60)
        self.bot = bot
        self.ctx = ctx

    @discord.ui.button(label='Yes, of course. Why wouldn\'t I?', style=discord.ButtonStyle.danger)
    async def confirm_purge(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Fine, I'll delete my recent messages.", ephemeral=True)
        await self._do_purge()
        await interaction.delete_original_response()

    @discord.ui.button(label='Oh my god, no! Stop it! STOP!!!', style=discord.ButtonStyle.secondary)
    async def cancel_purge(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Okay, I won't delete anything.", ephemeral=True)
        await interaction.delete_original_response()

    async def _do_purge(self):
        """Delete all messages sent by the bot"""
        for msg in self.bot.messages_issued:
            try:
                if msg.channel.id == self.bot.channel_id:
                    await msg.delete()
            except discord.NotFound:
                pass  # Message already deleted
            except Exception as e:
                logger.error("Failed to delete message: %s", e)

        self.bot.messages_issued.clear()
        self.bot.q_notifications.clear()


class SlashAnnouncementView(discord.ui.View):
    """View for slash command announcement contest selection"""
    
    def __init__(self, bot, interaction, header, msg):
        super().__init__(timeout=60)
        self.bot = bot
        self.interaction = interaction
        self.header = header
        self.msg = msg

        for i, contest in enumerate(bot.contests):
            button = discord.ui.Button(
                label=contest.description[:80],  # Discord button label limit
                style=discord.ButtonStyle.primary,
                custom_id=f"slash_announce_{i}"
            )
            button.callback = self._make_callback(i)
            self.add_item(button)

        # Add cancel button
        cancel_button = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id="slash_announce_cancel"
        )
        cancel_button.callback = self._cancel_callback
        self.add_item(cancel_button)

    def _make_callback(self, contest_id):
        async def callback(interaction):
            await interaction.response.defer()
            cog = self.bot.get_cog('ContestCommands')
            await cog._do_slash_announce(self.interaction, contest_id, self.header, self.msg)
            await interaction.delete_original_response()
        return callback

    async def _cancel_callback(self, interaction):
        await interaction.response.send_message("Announcement cancelled.", ephemeral=True)
        await interaction.delete_original_response()


class SlashPurgeView(discord.ui.View):
    """View for slash command purge confirmation"""
    
    def __init__(self, bot: DiscordBot, interaction: discord.Interaction) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.interaction = interaction

    @discord.ui.button(label='Yes, of course. Why wouldn\'t I?', style=discord.ButtonStyle.danger)
    async def confirm_purge(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message("Fine, I'll delete my recent messages.", ephemeral=True)
        await self._do_purge()
        await interaction.delete_original_response()

    @discord.ui.button(label='Oh my god, no! Stop it! STOP!!!', style=discord.ButtonStyle.secondary)
    async def cancel_purge(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message("Okay, I won't delete anything.", ephemeral=True)
        await interaction.delete_original_response()

    async def _do_purge(self) -> None:
        """Delete all messages sent by the bot"""
        for msg in self.bot.messages_issued:
            try:
                if hasattr(msg.channel, 'id') and msg.channel.id == self.bot.channel_id:
                    await msg.delete()
            except discord.NotFound:
                pass  # Message already deleted
            except Exception as e:
                logger.error("Failed to delete message: %s", e)

        self.bot.messages_issued.clear()
        self.bot.q_notifications.clear()


class DiscordBotService(Service):
    """A service running the Discord bot"""
    
    def __init__(self, shard: int, contest_id: Optional[int] = None) -> None:
        Service.__init__(self, shard)
        self.contest_id = contest_id
        self.bot_instance: Optional[DiscordBot] = None
        self._shutdown_event: Optional[asyncio.Event] = None

    def _get_contests(self) -> List[MyContest]:
        """Get the list of contests to monitor"""
        if self.contest_id is not None:
            return [MyContest(self.contest_id)]
        else:
            contest_list = get_contest_list(_session)
            return [MyContest(c.id) for c in contest_list]

    def _get_bot_token(self) -> str:
        """Get the Discord bot token from config"""
        token = getattr(config, 'discord_bot_token', '')
        if not token:
            raise ValueError("Discord bot token not configured")
        return token

    def run(self) -> None:
        """Run the Discord bot service"""
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info("Received signal %s, initiating shutdown...", signum)
            if self._shutdown_event is not None:
                # We're in an asyncio context, set the event
                try:
                    loop = asyncio.get_running_loop()
                    loop.call_soon_threadsafe(self._shutdown_event.set)
                except RuntimeError:
                    # No running loop, just exit
                    sys.exit(0)
            else:
                sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        while True:
            try:
                asyncio.run(self._run_bot())
                break  # If we reach here, the bot exited normally
            except KeyboardInterrupt:
                logger.info("Discord bot service stopped by user")
                break
            except Exception as e:
                logger.error("Discord bot service error: %s", e)
                sleep(3)  # Wait before restarting

    async def _run_bot(self) -> None:
        """Internal method to run the bot with proper async handling"""
        # Initialize the shutdown event in the async context
        self._shutdown_event = asyncio.Event()
        
        try:
            contests = self._get_contests()
            self.bot_instance = DiscordBot(contests)
            
            token = self._get_bot_token()
            logger.info("Starting Discord bot with token=%s...", token[:4])
            
            # Start the bot and wait for shutdown signal
            bot_task = asyncio.create_task(self.bot_instance.start(token))
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())
            
            # Wait for either the bot to finish or shutdown signal
            done, pending = await asyncio.wait(
                [bot_task, shutdown_task], 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # If shutdown was requested, close the bot gracefully
            if shutdown_task in done:
                logger.info("Shutdown signal received, closing bot...")
                if not self.bot_instance.is_closed():
                    await self.bot_instance.close()
                
                # Cancel the bot task if it's still running
                if not bot_task.done():
                    bot_task.cancel()
                    try:
                        await bot_task
                    except asyncio.CancelledError:
                        pass
            else:
                # Bot finished on its own, cancel shutdown task
                shutdown_task.cancel()
                
        except KeyboardInterrupt:
            logger.info("Bot interrupted, closing...")
            if self.bot_instance and not self.bot_instance.is_closed():
                await self.bot_instance.close()
            raise

    def exit(self) -> None:
        """Stop the Discord bot service"""
        logger.info("Exit method called, initiating shutdown...")
        
        # Set the shutdown event if it exists
        if self._shutdown_event is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self._shutdown_event.set)
            except RuntimeError:
                # No running loop, fall back to direct bot closure
                pass
        
        # Also try to close the bot instance directly
        if self.bot_instance:
            try:
                if not self.bot_instance.is_closed():
                    # Try to get the event loop and close the bot
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self.bot_instance.close())
                    except RuntimeError:
                        # No running loop, create a new one
                        asyncio.run(self.bot_instance.close())
            except Exception as e:
                logger.error("Error closing Discord bot: %s", e)
