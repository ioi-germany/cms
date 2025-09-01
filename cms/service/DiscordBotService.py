#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
import json
import traceback
import os
import signal
import sys
import asyncio
from typing import Optional, List, Any

from threading import Thread
from time import sleep

import discord
from discord.ext import commands, tasks
from discord import app_commands

from cms import config
from cms.db import Session, Contest, Question, Participation, Announcement
from cms.db.util import get_contest_list
from cms.io import Service
from cmscommon.datetime import make_datetime

logger = logging.getLogger(__name__)

def strip_cmd(s):
    """Remove the command part from a message."""
    return " ".join(s.split(' ')[1:])

def split_off_header(s):
    """Split message into header and body."""
    lines = s.split('\n')
    return lines[0], "\n".join(lines[1:])

def bold(s):
    """Format text as bold in Discord markdown."""
    return "**" + s + "**"

def italic(s):
    """Format text as italic in Discord markdown."""
    return "*" + s + "*"

def code_block(s):
    """Format text as code block in Discord markdown."""
    return "```\n" + s + "\n```"

def code_inline(s):
    """Format text as inline code in Discord markdown."""
    return "`" + s + "`"

_session = Session()


class WithDatabaseAccess(object):
    """Base class for database access"""
    def __init__(self, sql_session):
        self.sql_session = sql_session

    def _commit(self):
        self.sql_session.commit()


class MyQuestion(WithDatabaseAccess):
    """Thin wrapper around question"""
    def __init__(self, question):
        self.question = question
        self.replied_by = None
        super(MyQuestion, self).__init__(Session.object_session(self.question))

    def answer(self, a, is_short=True, replied_by=None):
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

    def ignore(self):
        self.question.last_action = make_datetime()
        self.question.ignored = True
        self.question.reply_source = "discord"

        return self._commit()

    def answered(self):
        return self.question.reply_timestamp is not None

    def update(self):
        self.question = Question.get_from_id(self.question.id, self.sql_session)

    def ignored(self):
        return self.question.ignored

    def handled(self):
        return self.ignored() or self.answered()

    def get_answer(self):
        return self.question.reply_subject, self.question.reply_text

    def format_answer(self):
        x, y = self.get_answer()
        return bold(x) if x else y

    def status_text(self):
        if self.answered():
            answer = self.format_answer()
            reply_info = f"This question has been answered by {self.replied_by}:"
            return italic(reply_info) + "\n" + answer
        elif self.ignored():
            return italic("This question has been ignored.")
        else:
            return italic("This question is currently open.")

    def get_title(self):
        subject = self.question.subject
        if len(subject) > 60:
            subject = subject[:60] + "..."
        return f"Q{self.question.id}: {subject}"

    def format(self, new):
        Q = self.question

        return bold("contest: ") + \
               "{}\n".format(Q.participation.contest.description) + \
               bold("from: ") + Q.participation.user.username + \
               "\n" + bold("timestamp: ") + \
               "{}".format(Q.question_timestamp) + "\n\n" + \
               (bold(Q.subject) + "\n" + Q.text).strip() + \
               "\n\n" + self.status_text()


class ListOfDatabaseEntries(object):
    def __init__(self, contest_id):
        self.sql_session = _session
        self.contest_id = contest_id

    def _new_session(self):
        self.sql_session.commit()
        self.sql_session.expire_all()


class QuestionList(ListOfDatabaseEntries):
    """Keeps track of all questions"""
    def __init__(self, contest_id):
        super(QuestionList, self).__init__(contest_id)

        self.question_times = {}
        self.action_times = {}

    def poll(self):
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

    def open_questions(self):
        return [MyQuestion(q) for q in self._get_questions()
                              if q.reply_timestamp is None and not q.ignored]

    def all(self):
        return [MyQuestion(q) for q in self._get_questions()]

    def _get_questions(self):
        self._new_session()

        return self.sql_session.query(Question).join(Participation)\
                   .filter(Participation.contest_id == self.contest_id)\
                   .order_by(Question.question_timestamp.desc())\
                   .order_by(Question.id).all()


class MyAnnouncement(WithDatabaseAccess):
    """Thin wrapper around announcement"""
    def __init__(self, announcement):
        self.announcement = announcement
        super(MyAnnouncement, self).\
            __init__(Session.object_session(self.announcement))

    def get_title(self, length_limit=40):
        subject = self.announcement.subject
        if len(subject) > length_limit:
            subject = subject[:length_limit - 3] + "..."
        return f"ANNOUNCEMENT: {subject}"

    def format(self, new):
        A = self.announcement

        return bold("contest: ") + \
               "{}\n".format(A.contest.description) + \
               bold("timestamp: ") + \
               "{}\n\n".format(A.timestamp) + \
               bold(A.subject) + "\n" + A.text


class AnnouncementList(ListOfDatabaseEntries):
    """Keeps track of all announcements"""
    def __init__(self, contest_id):
        super(AnnouncementList, self).__init__(contest_id)
        self.announcements = set()

    def poll(self):
        r = []

        for a in self._get_announcements():
            if a.id not in self.announcements and a.src == "web":
                self.announcements.add(a.id)
                r.append(MyAnnouncement(a))

        return r

    def all(self):
        return [MyAnnouncement(a) for a in self._get_announcements()]

    def _get_announcements(self):
        self._new_session()
        res = self.sql_session.query(Announcement)\
                   .filter(Announcement.contest_id == self.contest_id)
        assert res is not None
        return res


class MyContest(WithDatabaseAccess):
    """Encapsulates access to the contest currently running"""
    def __init__(self, contest_id):
        super(MyContest, self).__init__(_session)

        self.contest_id = contest_id
        self.contest = Contest.get_from_id(contest_id, self.sql_session)
        self.name = self.contest.name
        self.description = self.contest.description
        self.questions = QuestionList(self.contest_id)
        self.announcements = AnnouncementList(self.contest_id)

    def announce(self, header, body):
        ann = Announcement(timestamp=make_datetime(), 
                          subject=header, 
                          text=body, 
                          src="discord",
                          contest=self.contest)
        self.sql_session.add(ann)
        return self._commit()

    def poll_questions(self):
        return self.questions.poll()

    def get_all_open_questions(self):
        return self.questions.open_questions()

    def get_all_questions(self):
        return self.questions.all()

    def poll_announcements(self):
        return self.announcements.poll()

    def get_all_announcements(self):
        return self.announcements.all()


class DiscordBot(commands.Bot):
    """A Discord bot that allows easy access to all the communication
    (Clarification Requests/Announcements/etc) happening"""

    def __init__(self, contests=None, only_listen_to=None):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents, help_command=None)

        self.pwd = getattr(config, 'discord_bot_pwd', 'pwd')  # Password needed during startup
        self.channel_id = only_listen_to   # We will only communicate with this channel
        self.contests = contests or []
        self.questions = {}
        self.q_notifications = {}
        self.messages_issued = []
        self.err_count = 0
        self.MAX_ERR_COUNT = getattr(config, 'discord_bot_max_error_messages', 10)
        self.is_registered = False

    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        if not hasattr(self, '_update_task') or self._update_task.done():
            self._update_task = self.loop.create_task(self._update_loop())

    async def on_error(self, event, *args, **kwargs):
        error = sys.exc_info()[1]
        if error:
            err = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            logger.error(f"Discord bot error in {event}: {err}")

            if self.channel_id is not None and self.is_registered:
                self.err_count += 1

                error_msg = f"⚠️ **Error occurred** ⚠️\n```\n{err}\n```"
                if len(error_msg) > 2000:
                    error_msg = error_msg[:1997] + "..."

                channel = self.get_channel(self.channel_id)
                if channel:
                    await channel.send(error_msg)

                if self.err_count >= self.MAX_ERR_COUNT:
                    await channel.send("I think I'm gonna lay down for a while...")
                    await self.close()

    async def setup_hook(self):
        """Called when the bot is starting up"""
        await self.add_cog(ContestCommands(self))
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash command(s)")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

    async def _update_loop(self):
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

                for c in self.contests:
                    try:
                        new_qs, new_as, updated_as, ignored_qs, unignored_qs = \
                            c.poll_questions()

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

                        new_announcements = c.poll_announcements()

                        for a in new_announcements:
                            await self._notify_announcement(channel, a, True)

                    except Exception as e:
                        logger.error(f"Error processing contest {c.contest_id}: {e}")

            except Exception as e:
                logger.error(f"Error in update loop: {e}")
            
            await asyncio.sleep(5)

    async def _notify_question(self, channel, q, new):
        """Send a question notification with buttons and create a thread"""
        embed = discord.Embed(
            title=q.get_title(),
            description=q.format(new),
            color=0xff6b6b if new else 0x4ecdc4
        )

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

    async def _notify_answer(self, channel, q : MyQuestion, new):
        """Notify about an answer given via web interface"""
        if q.question.id not in self.q_notifications:
            return
        q.replied_by = "CMS Web"

        notification_data = self.q_notifications[q.question.id][-1]
        msg = notification_data['message']
        thread = notification_data['thread']
        
        notification = "This question has been answered via CMS:\n\n" if new \
                       else "The answer has been edited via CMS:\n\n"

        reply_text = notification + q.format_answer()
        if len(reply_text) > 2000:
            reply_text = reply_text[:1997] + "..."

        # Send notification to the thread instead of as a reply
        reply = await thread.send(reply_text)
        self.questions[reply.id] = q
        self.messages_issued.append(reply)
        
        # Update the original message
        await self._update_question(q)

    async def _notify_question_ignore(self, channel, q, ignore):
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

    async def _notify_announcement(self, channel, a, new):
        """Send an announcement notification"""
        embed = discord.Embed(
            title=a.get_title(),
            description=a.format(new),
            color=0x45b7d1
        )

        message = await channel.send(embed=embed)
        self.messages_issued.append(message)

    async def _update_question(self, q):
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

    async def _reply_question(self, ctx, q, answer, short_answer=False, in_thread=False):
        """Reply to a user question"""
        # Get the replier information
        if hasattr(ctx, 'user'):  # Discord interaction
            replier = ctx.user.display_name
        elif hasattr(ctx, 'author'):  # Discord message
            replier = ctx.author.display_name
        else:
            replier = "Unknown"
            
        if answer.strip() == "/ignore":
            if q.answered():
                fail_msg = "This question has already been answered; I can't ignore it anymore ☹."
                if not short_answer:
                    if in_thread:
                        await ctx.channel.send(fail_msg)
                    else:
                        await ctx.reply(fail_msg)
                # For short_answer (button clicks), we don't send individual failure messages
                # since the public message is handled in _handle_reply
            else:
                q.ignore()
                if not short_answer:
                    success_msg = "I have ignored this question!"
                    if in_thread:
                        await ctx.channel.send(success_msg)
                    else:
                        await ctx.reply(success_msg)
                # For short_answer (button clicks), success message is handled in _handle_reply
                
                await self._update_question(q)
            return

        q.answer(answer, short_answer, replied_by=replier)

        if not short_answer:
            success_msg = "I have added your answer!"
            if in_thread:
                reply = await ctx.channel.send(success_msg)
            else:
                reply = await ctx.reply(success_msg)
            self.questions[reply.id] = q
            self.messages_issued.append(reply)
        # For short_answer (button clicks), success message is handled in _handle_reply

        await self._update_question(q)


class QuestionView(discord.ui.View):
    """View with buttons for question responses"""
    
    def __init__(self, bot, question, in_thread=False):
        super().__init__(timeout=None)
        self.bot = bot
        self.question = question
        self.in_thread = in_thread

    @discord.ui.button(label='Yes', style=discord.ButtonStyle.green)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_reply(interaction, "Yes")

    @discord.ui.button(label='No', style=discord.ButtonStyle.red)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_reply(interaction, "No")

    @discord.ui.button(label='Answered in task description', style=discord.ButtonStyle.secondary)
    async def task_desc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_reply(interaction, "Answered in task description")

    @discord.ui.button(label='No comment', style=discord.ButtonStyle.secondary)
    async def no_comment_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_reply(interaction, "No comment")

    @discord.ui.button(label='Invalid question', style=discord.ButtonStyle.secondary)
    async def invalid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_reply(interaction, "Invalid question")

    @discord.ui.button(label='🚫 Ignore', style=discord.ButtonStyle.danger)
    async def ignore_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_reply(interaction, "/ignore")

    async def _handle_reply(self, interaction: discord.Interaction, answer):
        """Handle button click replies"""
        channel_valid = False
        
        if self.bot.is_registered:
            if interaction.channel_id == self.bot.channel_id:
                channel_valid = True
            elif isinstance(interaction.channel, discord.Thread) and interaction.channel.parent_id == self.bot.channel_id:
                channel_valid = True
        
        if not channel_valid:
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
        
        # Find the thread for this question and send the message there
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


class ContestCommands(commands.Cog):
    """Commands for contest management"""
    
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='start')
    async def start(self, ctx, password: str = ""):
        """Register the bot to this channel"""
        if not password:
            await ctx.send("Error: Password required. Usage: `!start <password>`")
            return

        if self.bot.is_registered:
            if self.bot.channel_id == ctx.channel.id:
                await ctx.send("I'm already bound to this channel!")
                return
            else:
                await ctx.send("Error: I'm already registered with another channel")
                logger.error("Someone tried to !start me although I'm already bound to a channel")
                
                if self.bot.channel_id:
                    channel = self.bot.get_channel(self.bot.channel_id)
                    if channel:
                        await channel.send("Warning: Someone tried to !start me although I'm exclusively bound to this channel!")
                return

        if password != self.bot.pwd:
            await ctx.send("Error: wrong password")
            logger.warning("Someone tried to !start me using a wrong password")
            return

        # Everything is fine
        self.bot.channel_id = ctx.channel.id
        self.bot.is_registered = True

        message = "Congratulations! I'm now bound to this channel!\n"
        if len(self.bot.contests) == 1:
            message += "I'll assist you with the following contest.\n"
        else:
            message += "I'll assist you with the following contests.\n"
        
        for c in self.bot.contests:
            message += f"• **{c.name}**: {c.description}\n"

        await ctx.send(message)

    async def _do_announce(self, ctx, contest_id, header, msg):
        """Actually make the announcement"""
        contest = self.bot.contests[contest_id]
        
        # Get the user who made the announcement
        if hasattr(ctx, 'author'):  # Traditional command
            announcer = ctx.author.display_name
        elif hasattr(ctx, 'user'):  # Slash command interaction
            announcer = ctx.user.display_name
        else:
            announcer = "Someone"
        
        if not contest.announce(header, msg):
            # Send private confirmation
            await ctx.reply(f"I have announced the following in {contest.description}:\n\n**{header}**\n{msg}")
            
            # Send public message about who made the announcement
            public_msg = f"📢 **{announcer}** has announced the following in {contest.description}:\n\n**{header}**\n{msg}"
            if hasattr(ctx, 'channel'):
                await ctx.channel.send(public_msg)
            elif hasattr(ctx, 'followup'):  # For slash commands
                await ctx.followup.send(public_msg)
        else:
            await ctx.reply("Sorry, this didn't work...")

    @commands.command(name='help')
    async def help_command(self, ctx):
        """Show help information"""
        help_text = """**Discord Bot for CMS Contest Management**

A bot allowing access to clarification requests and announcements of a CMS contest via Discord.

**Commands:**
• `!start <password>` — bind the bot to the current channel when used with the correct password; the bot can only be bound to a single channel at a time
• `!help` — prints this message

**Text Commands are deprecated. Use slash commands (/help) instead!**

**Question Management:**
In addition this bot will post all new questions appearing in the system. You can answer them by replying to the corresponding message or using the quick-response buttons. Moreover, all answers given and announcements made via the web interface will also be posted and you can edit answers by replying to the corresponding message.

**Quick Response Buttons:**
✅ **Yes** — Simple affirmative answer
❌ **No** — Simple negative answer  
📋 **Answered in task description** — Refer to task documentation
💭 **No comment** — Decline to answer
⚠️ **Invalid question** — Mark as invalid
🚫 **Ignore** — Mark question as ignored"""

        await ctx.send(help_text)

    # Slash Commands
    @app_commands.command(name="start", description="Register the bot to this channel")
    @app_commands.describe(password="Password required to bind the bot")
    async def slash_start(self, interaction: discord.Interaction, password: str):
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
        
        if not password:
            await interaction.response.send_message("Error: Password required.", ephemeral=True)
            return

        if self.bot.is_registered:
            if self.bot.channel_id == interaction.channel.id:
                await interaction.response.send_message("I'm already bound to this channel!", ephemeral=True)
                return
            else:
                await interaction.response.send_message("Error: I'm already registered with another channel", ephemeral=True)
                logger.error("Someone tried to /start me although I'm already bound to a channel")
                
                if self.bot.channel_id:
                    channel = self.bot.get_channel(self.bot.channel_id)
                    if channel and hasattr(channel, 'send'):
                        await channel.send("Warning: Someone tried to /start me although I'm exclusively bound to this channel!")
                return

        if password != self.bot.pwd:
            await interaction.response.send_message("Error: wrong password", ephemeral=True)
            logger.warning("Someone tried to /start me using a wrong password")
            return

        # Everything is fine
        self.bot.channel_id = interaction.channel.id
        self.bot.is_registered = True

        message = "Congratulations! I'm now bound to this channel!\n"
        if len(self.bot.contests) == 1:
            message += "I'll assist you with the following contest.\n"
        else:
            message += "I'll assist you with the following contests.\n"
        
        for c in self.bot.contests:
            message += f"• **{c.name}**: {c.description}\n"

        await interaction.response.send_message(message)

    group_announcements = app_commands.Group(name="announcements", description="Manage announcements")
    @group_announcements.command(name="make", description="Make an announcement to the contest")
    @app_commands.describe(
        subject="The subject/title of the announcement",
        content="The content/body of the announcement"
    )
    async def slash_announce(self, interaction: discord.Interaction, subject: str, content: str):
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
    async def slash_all_announcements(self, interaction: discord.Interaction):
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
    async def slash_open_questions(self, interaction: discord.Interaction):
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

**Prefix Commands (!):**
• `!start <password>` — bind the bot to the current channel when used with the correct password; the bot can only be bound to a single channel at a time
• `!help` — prints this message

**Slash Commands (/):**
• `/start <password>` — bind the bot to the current channel when used with the correct password
• `/announce <announcement>` — adds the text as an announcement to the current contest
• `/openquestions` — shows all *unanswered* questions of the current contest
• `/allannouncements` — shows all announcements of the current contest
• `/help` — prints this message
• `/purge` — deletes all messages sent by the bot during the current session

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


class AnnouncementView(discord.ui.View):
    """View for announcement contest selection"""
    
    def __init__(self, bot, ctx, header, msg):
        super().__init__(timeout=60)
        self.bot = bot
        self.ctx = ctx
        self.header = header
        self.msg = msg

        for i, contest in enumerate(bot.contests):
            button = discord.ui.Button(
                label=contest.description[:80],  # Discord button label limit
                style=discord.ButtonStyle.primary,
                custom_id=f"announce_{i}"
            )
            button.callback = self._make_callback(i)
            self.add_item(button)

        # Add cancel button
        cancel_button = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id="announce_cancel"
        )
        cancel_button.callback = self._cancel_callback
        self.add_item(cancel_button)

    def _make_callback(self, contest_id):
        async def callback(interaction):
            await interaction.response.defer()
            cog = self.bot.get_cog('ContestCommands')
            await cog._do_announce(self.ctx, contest_id, self.header, self.msg)
            await interaction.delete_original_response()
        return callback

    async def _cancel_callback(self, interaction):
        await interaction.response.send_message("Announcement cancelled.", ephemeral=True)
        await interaction.delete_original_response()


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
                logger.error(f"Failed to delete message: {e}")

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
    
    def __init__(self, bot, interaction):
        super().__init__(timeout=60)
        self.bot = bot
        self.interaction = interaction

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
                if hasattr(msg.channel, 'id') and msg.channel.id == self.bot.channel_id:
                    await msg.delete()
            except discord.NotFound:
                pass  # Message already deleted
            except Exception as e:
                logger.error(f"Failed to delete message: {e}")

        self.bot.messages_issued.clear()
        self.bot.q_notifications.clear()


class DiscordBotService(Service):
    """A service running the Discord bot"""
    
    def __init__(self, shard, contest_id=None):
        Service.__init__(self, shard)
        self.contest_id = contest_id
        self.bot_instance = None

    def run(self):
        """Run the Discord bot service"""
        while True:
            try:
                # A contest_id was provided: we restrict ourselves to that contest
                if self.contest_id is not None:
                    contests = [MyContest(self.contest_id)]
                # No contest_id was provided: we fetch all contests in the database
                else:
                    contest_list = get_contest_list(_session)
                    contests = [MyContest(c.id) for c in contest_list]

                # Create and run the bot
                self.bot_instance = DiscordBot(contests)
                
                # Run the bot
                token = getattr(config, 'discord_bot_token', '')
                if not token:
                    logger.error("Discord bot token not configured")
                    break

                logger.info(f"Starting Discord bot with token={token[:4]}")
                asyncio.run(self.bot_instance.run(token))
                
            except KeyboardInterrupt:
                logger.info("Discord bot service stopped by user")
                break
            except Exception as e:
                logger.error(f"Discord bot service error: {e}")
                sleep(5)  # Wait before restarting

    def exit(self):
        """Stop the Discord bot service"""
        if self.bot_instance:
            asyncio.create_task(self.bot_instance.close())
