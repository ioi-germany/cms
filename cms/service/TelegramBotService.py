#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017-2018 Tobias Lenz <t_lenz94@web.de>
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

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import *

from cms import config
from cms.db import Session, Contest, Question, Participation, Announcement
from cms.io import Service
from cmscommon.datetime import make_datetime

logger = logging.getLogger(__name__)

def strip_cmd(s):
    return " ".join(s.split(' ')[1:])

def split_off_header(s):
    l = s.split('\n')
    return l[0], "\n".join(l[1:])

def bold(s):
    return "*" + s + "*"

def italic(s):
    return "_" + s + "_"


class WithDatabaseAccess(object):
    """ Base class for database access
    """
    def __init__(self, sql_session=None):
        self.sql_session = sql_session or Session()

    def _commit(self):
        self.sql_session.commit()


class MyQuestion(WithDatabaseAccess):
    """ Thin wrapper around question
    """
    def __init__(self, question):
        self.question = question
        super(MyQuestion, self).__init__(Session.object_session(self.question))

    def answer(self, a):
        self.question.last_action = make_datetime()
        self.question.reply_timestamp = self.question.last_action
        self.question.reply_subject = ""
        self.question.reply_text = a
        self.question.reply_source = "telegram"
        self.question.ignored = False

        return self._commit()

    def ignore(self):
        self.question.last_action = make_datetime()
        self.question.ignored = True
        self.question.reply_source = "telegram"

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
        x,y = self.get_answer()
        return bold(x) if x else y

    def status_text(self):
        if self.answered():
            return italic("This question has been answered:\n\n") + \
                   self.format_answer()
        elif self.ignored():
            return italic("This question has been ignored.")
        else:
            return italic("This question is currently open.")

    def format(self, new):
        Q = self.question
    
        return bold(("NEW " if new else "") + "QUESTION\n") +  \
               italic("    from: ") + Q.participation.user.username + "\n" + \
               italic("    timestamp: ") + "{}".format(Q.question_timestamp) + \
               "\n\n" + (bold(Q.subject) + "\n" + Q.text).strip() + "\n\n" + \
               self.status_text()


class ListOfDatabaseEntries(object):
    def __init__(self, contest_id):
        self.sql_session = Session()
        self.contest_id = contest_id

    def _new_session(self):
        self.sql_session.commit()
        self.sql_session.expire_all()


class QuestionList(ListOfDatabaseEntries):
    """ Keeps track of all questions
    """
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
    """ Thin wrapper around announcement
    """
    def __init__(self, announcement):
        self.announcement = announcement
        super(MyAnnouncement, self).\
            __init__(Session.object_session(self.announcement))    

    def format(self, new):
        A = self.announcement
    
        return bold(("NEW " if new else "") + "ANNOUNCEMENT\n") + \
               italic("    timestamp: ") + "{}\n\n".format(A.timestamp) + \
               bold(A.subject) + "\n" + A.text


class AnnouncementList(ListOfDatabaseEntries):
    """ Keeps track of all announcements
    """
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

        return self.sql_session.query(Announcement)\
                   .filter(Announcement.contest_id == self.contest_id)


class MyContest(WithDatabaseAccess):
    """ Encapsulates access to the contest currently running
    """
    def __init__(self, contest_id):
        super(MyContest, self).__init__()

        self.contest_id = contest_id
        self.contest = Contest.get_from_id(contest_id, self.sql_session)
        self.questions = QuestionList(self.contest_id)
        self.announcements = AnnouncementList(self.contest_id)

    def announce(self, header, body):
        ann = Announcement(make_datetime(), header, body, "telegram",
                           contest=self.contest)
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


class TelegramBot:
    """ A telegram bot that allows easy access to all the communication
        (Clarification Requests/Announcements/etc) happening
    """

    def __init__(self, contest):
        self.pwd = config.bot_pwd # Password needed during startup
        self.id = None            # We will only communicate with the group of
                                  # this id (will be set during startup)
        self.questions = {}
        self.q_notifications = {}
        self.contest = contest

        self.updater = Updater(token=config.bot_token)
        self.dispatcher = self.updater.dispatcher
        self.job_queue = self.updater.job_queue

        self.dispatcher.add_handler(CommandHandler('start', self.start,
                                                   pass_args=True))
        self.dispatcher.add_handler(CommandHandler('announce', self.announce))
        self.dispatcher.add_handler(CommandHandler('openquestions',
                                                   self.list_open_questions))
        self.dispatcher.add_handler(CommandHandler('allquestions',
                                                   self.list_all_questions))
        self.dispatcher.add_handler(CommandHandler('allannouncements',
                                                   self.list_all_announcements))
        self.dispatcher.add_handler(CommandHandler('help', self.help))
        self.dispatcher.add_handler(MessageHandler(Filters.reply,
                                                   self.on_reply))
        self.dispatcher.add_handler(CallbackQueryHandler(self.button_callback))

        self.job_queue.run_repeating(self.update, interval=5, first=0)

    def start(self, bot, update, args=None):
        """ The registration process

            For security reasons our bot will always only communicate with one
            chat, namely the first one that can authenticate to it using the
            password saved in the config file
        """
        params = args or []

        if self.id is not None:
            if self.id == update.message.chat_id:
                bot.send_message(chat_id=self.id,
                                 text="I'm already bound to thy will!")
                return

            bot.send_message(chat_id=update.message.chat_id,
                             text="Error: I'm already registered with another "
                                  "chat")
            logger.error("Someone tried to /start me although I'm already "
                         "bound to a chat")
            bot.send_message(chat_id=self.id,
                             text="Warning: Someone tried to /start me "
                                  "although I'm exclusively bound to thy will!")
            return

        if len(params) != 1:
            bot.send_message(chat_id=update.message.chat_id,
                             text="Error: exactly one argument needed")
            logger.warning("Someone tried to /start me without providing a "
                           "password")
            return

        if params[0] != self.pwd:
            bot.send_message(chat_id=update.message.chat_id,
                             text="Error: wrong password")
            logger.warning("Someone tried to /start me using a wrong password")
            return

        # Everything is fine
        self.id = update.message.chat_id

        bot.send_message(chat_id=self.id,
                         text="Congratulations! I'm now bound to thy will!")

    def announce(self, bot, update):
        """ Make an announcement
        """
        if self.id is None:
            update.message.reply_text("You have to register me first (using "
                                      "the /start command).")
            return

        if self.id != update.message.chat_id:
            logger.warning("Warning! Someone tried to make an announcement in "
                           "a chat I'm not registered in!")
            bot.send_message(chat_id=self.id,
                             text="Warning! Someone tried to make an "
                             "announcement in another chat!")
            return

        header, msg = split_off_header(strip_cmd(update.message.text))

        if not self.contest.announce(header, msg):
            update.message.reply_text("I have announced the following:\n\n" +
                                      bold(header) + "\n" + msg,
                                      parse_mode="Markdown")
        else:
            update.message.reply_text("Sorry, this didn't work...")


    def button_callback(self, bot, update):
        cq = update.callback_query

        if cq.message.chat.id != self.id:
            logger.warning("Warning! Someone tried to use the inline keyboard "
                           "in a chat I'm not registered in!")

            if self.id is not None:
                bot.send_message(chat_id=self.id,
                                 text="Warning! Someone tried to use the "
                                      "inline keyboard in another chat!")
            return

        a = cq.data
        msg_id = cq.message.message_id
        q = self.questions[msg_id]

        self.reply_question(cq, q, a, short_answer=True)

    def _notify_question(self, bot, q, new, show_status):
        kb =  [[InlineKeyboardButton(text="Yes", callback_data="Yes"),
                InlineKeyboardButton(text="No",  callback_data="No")],
               [InlineKeyboardButton(text="Answered in task description",
                                     callback_data="Answered in task "
                                                   "description")],
               [InlineKeyboardButton(text="No comment",
                                     callback_data="No comment"),
                InlineKeyboardButton(text="Invalid question",
                                     callback_data="Invalid question")],
               [InlineKeyboardButton(text="〈ignore question〉",
                                     parse_mode="Markdown",
                                     callback_data="/ignore")]]

        Q = q.question

        msg = bot.send_message(chat_id=self.id,
                               text=q.format(new),
                               parse_mode="Markdown",
                               reply_markup=InlineKeyboardMarkup(kb))
        self.questions[msg.message_id] = q
        self.q_notifications[Q.id] = msg

    def _notify_answer(self, q, new):
        msg = self.q_notifications[q.question.id]

        notification = "This question has been answered via CMS:\n\n" if new \
                       else "The answer has been edited via CMS:\n\n"

        reply = msg.reply_text(text=notification + q.format_answer(),
                               quote=True,
                               parse_mode="Markdown")

        self.questions[reply.message_id] = q

    def _notify_question_ignore(self, q, ignore):
        msg = self.q_notifications[q.question.id]

        notification = italic("This question has been "
                              "{}ignored.\n\n".format("" if ignore else "un"))

        reply = msg.reply_text(text=notification,
                               quote=True,
                               parse_mode="Markdown")

        self.questions[reply.message_id] = q

    def _notify_announcement(self, bot, a, new):
        bot.send_message(chat_id=self.id,
                         text=a.format(new),
                         parse_mode="Markdown")

    def update(self, bot, job):
        """ Check for new questions, answers, and announcements
        """
        if self.id is None:
            return

        new_qs, new_as, updated_as, ignored_qs, unignored_qs = \
            self.contest.poll_questions()

        for q in new_qs:
            self._notify_question(bot, q, True, False)

        for q in new_as:
            self._notify_answer(q, True)

        for q in updated_as:
            self._notify_answer(q, False)

        for q in ignored_qs:
            self._notify_question_ignore(q, True)

        for q in unignored_qs:
            self._notify_question_ignore(q, False)

        new_announcements = self.contest.poll_announcements()

        for a in new_announcements:
            self._notify_announcement(bot, a, True)

    def list_open_questions(self, bot, update):
        if self.id is None:
            update.message.reply_text("You have to register me first (using "
                                      "the /start command).")
            return

        if self.id != update.message.chat_id:
            logger.warning("Warning! Someone tried to list open questions in "
                           "a chat I'm not registered in!")
            bot.send_message(chat_id=self.id,
                             text="Warning! Someone tried to list open "
                             "questions in another chat!")
            return

        qs = self.contest.get_all_open_questions()

        notification = ""

        if len(qs) == 1:
            notification = "There is currently *1* open question:"
        else:
            notification = "There are currently " + \
                           bold("no" if len(qs) == 0 else str(len(qs))) + \
                           " open questions" + ("" if len(qs) == 0 else ":")

        bot.send_message(chat_id=self.id,
                         text=notification,
                         parse_mode="Markdown")

        for q in qs:
            self._notify_question(bot, q, False, False)

    def list_all_questions(self, bot, update):
        if self.id is None:
            update.message.reply_text("You have to register me first (using "
                                      "the /start command).")
            return

        if self.id != update.message.chat_id:
            logger.warning("Warning! Someone tried to list all questions in "
                           "a chat I'm not registered in!")
            bot.send_message(chat_id=self.id,
                             text="Warning! Someone tried to list all "
                             "questions in another chat!")
            return

        qs = self.contest.get_all_questions()

        if len(qs) == 1:
            notification = "There is currently *1* question:"
        else:
            notification = "There are currently " + \
                           bold("no" if len(qs) == 0 else str(len(qs))) + " "\
                           "questions" + ("" if len(qs) == 0 else ":")

        bot.send_message(chat_id=self.id,
                         text=notification,
                         parse_mode="Markdown")

        for q in qs:
            self._notify_question(bot, q, False, True)

    def list_all_announcements(self, bot, update):
        if self.id is None:
            update.message.reply_text("You have to register me first (using "
                                      "the /start command).")
            return

        if self.id != update.message.chat_id:
            logger.warning("Warning! Someone tried to list all announcements "
                           "in a chat I'm not registered in!")
            bot.send_message(chat_id=self.id,
                             text="Warning! Someone tried to list all "
                             "announcements in another chat!")
            return

        announcements = self.contest.get_all_announcements()

        if len(announcements) == 1:
            notification = "There is currently *1* announcement:"
        else:
            notification = "There are currently " +\
                           bold("no" if len(announcements) == 0
                                     else str(len(announcements))) + " "\
                           "announcements" + ("" if len(announcements) == 0
                                                 else ":")

        bot.send_message(chat_id=self.id,
                         text=notification,
                         parse_mode="Markdown")

        for a in announcements:
            self._notify_announcement(bot, a, False)

    def help(self, bot, update):
        update.message.reply_text("A bot allowing to access clarification "
                                  "requests and announcements of a CMS contest "
                                  "via Telegram.\n\n"
                                  "/start <pwd> - Registers the bot with the "
                                  "current chat. The bot can be only bound to "
                                  "a single chat; further binding attempts "
                                  "will be rejected.\n"
                                  "/announce - adds the rest of the message as "
                                  "an announcement to the current contest.\n"
                                  "/openquestions - shows all unanswered "
                                  "questions\n"
                                  "/allquestions - shows all questions\n"
                                  "/help - shows this message\n\n"
                                  "In addition this bot will post all new "
                                  "questions appearing in the system. You can "
                                  "answer them by replying to the "
                                  "corresponding post. Moreover, all answers "
                                  "given via the web interface will also be "
                                  "posted and you can edit them by replying to "
                                  "the corresponding message")

    def on_reply(self, bot, update):
        """ Replying to a user question posted in the chat uploads the reply as
            answer.

            TODO: edits
            TODO: Replying to answers and announcements?
        """
        if self.id is None:
            return

        orig_msg = update.message.reply_to_message
        new_msg = update.message

        if not (self.id == orig_msg.chat.id == new_msg.chat.id):
            logger.warning("Someone tried to reply to a message outside of the "
                           "chat I'm bound to (or magically answered to a "
                           "question from my fixed chat in a DIFFERENT chat)")
            bot.send_message(chat_id=self.id,
                             text="Warning! Someone tried to reply to a "
                                  "message outside of this chat "
                                  "(or magically answered to a question from "
                                  "this chat in a DIFFERENT chat)")
            return

        msg_id = orig_msg.message_id

        if msg_id in self.questions:
            q = self.questions[msg_id]

        else:
            return

        self.reply_question(update, q, new_msg.text)

    def reply_question(self, update, q, a, short_answer=False):
        """ Reply to the user question q with the answer a
        """
        # q.update()
        if a.strip() == "/ignore":
            if q.answered():
                IGNORE_FAIL_MSG = "This question has already been answered; " \
                                  "I can't ignore it anymore ☹."

                if short_answer:
                    update.answer(text=IGNORE_FAIL_MSG)
                else:
                    update.message.reply_text(IGNORE_FAIL_MSG, quote=True)

            else:
                q.ignore()
                
                if short_answer:
                    update.answer(text="I have ignored this question!")
                else:
                    update.message.reply_text("I have ignored this question!",
                                              quote=True)

            return

        q.answer(a)

        if short_answer:
            update.answer(text="I have added your answer (“{}”)!".format(a))
        else:
            msg = update.message.reply_text("I have added your answer!",
                                            quote=True)
            self.questions[msg.message_id] = q

    def run(self):
        self.updater.start_polling()
        self.updater.idle()


class TelegramBotService:
    """ A service running the above bot
    """
    def __init__(self, shard, contest_id):
        self.contest = MyContest(contest_id)
        self.bot = TelegramBot(self.contest)

    def run(self):
        self.bot.run()
