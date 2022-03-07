#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017-2020 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2020-2021 Manuel Gundlach <manuel.gundlach@gmail.com>
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

from threading import Thread
from time import sleep

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, bot
from telegram.ext import *
from telegram.ext.messagequeue import MessageQueue, queuedmessage
from telegram.utils.request import Request
from telegram.error import BadRequest as TelegramBadRequest

from cms import config
from cms.db import Session, Contest, Question, Participation, Announcement
from cms.db.util import get_contest_list
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

def escape(s):
    return "".join("\\" + c if ord(c) > 32 and ord(c) < 127 else c for c in s)

def code(s):
    linebreak = "" if len(s) > 0 and s[-1] == "\n" else "\n"
    return "```\n" + s + linebreak + "```\n"

_session = Session()


class WithDatabaseAccess(object):
    """ Base class for database access
    """
    def __init__(self, sql_session):
        self.sql_session = sql_session

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
        return bold(x) if x else escape(y)

    def status_text(self):
        if self.answered():
            return italic(escape("This question has been answered:\n\n")) + \
                   self.format_answer()
        elif self.ignored():
            return italic(escape("This question has been ignored."))
        else:
            return italic(escape("This question is currently open."))

    def format(self, new):
        Q = self.question

        return bold(("NEW " if new else "") + "QUESTION\n") + \
               italic("    contest: ") + \
               escape("{}\n".format(Q.participation.contest.description)) + \
               italic("    from: ") + escape(Q.participation.user.username) + \
               "\n" + italic("    timestamp: ") + \
               escape("{}".format(Q.question_timestamp)) + "\n\n" + \
               (bold(escape(Q.subject)) + "\n" + escape(Q.text)).strip() + \
               "\n\n" + self.status_text()


class ListOfDatabaseEntries(object):
    def __init__(self, contest_id):
        self.sql_session = _session
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
               italic("    contest: ") + \
               escape("{}\n".format(A.contest.description)) + \
               italic("    timestamp: ") + \
               escape("{}\n\n".format(A.timestamp)) + \
               bold(escape(A.subject)) + "\n" + escape(A.text)


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
        super(MyContest, self).__init__(_session)

        self.contest_id = contest_id
        self.contest = Contest.get_from_id(contest_id, self.sql_session)
        self.name = self.contest.name
        self.description = self.contest.description
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


class BotWithMessageQueue(bot.Bot):
    def __init__(self, *args, all_burst_limit = 2, all_time_limit_ms = 1010,
                 group_burst_limit = 18, group_time_limit_ms = 60500, **kwargs):
        super(BotWithMessageQueue, self).__init__(*args, **kwargs)

        # internal variables used by @queuedmessage
        self._is_messages_queued_default = True
        self._msg_queue = MessageQueue(all_burst_limit, all_time_limit_ms,
                                       group_burst_limit, group_time_limit_ms)

    def __del__(self):
        try:
            self._msg_queue.stop()
        except:
            pass

    def send_message(self, *args, **kwargs):
        return self._send_message_internal(*args, isgroup=True, **kwargs)

    @queuedmessage
    def _send_message_internal(self, *args, on_send=lambda _ : None, **kwargs):
        msg = super(BotWithMessageQueue, self).send_message(*args, **kwargs)
        on_send(msg)
        return msg


class TelegramBot:
    """ A telegram bot that allows easy access to all the communication
        (Clarification Requests/Announcements/etc) happening
    """

    def __init__(self, contests=None, only_listen_to=None):
        self.pwd = config.bot_pwd # Password needed during startup
        self.id = None            # We will only communicate with the group of
                                  # this id (will be set during startup)
        self.only_listen_to = only_listen_to
        self.questions = {}
        self.q_notifications = {}
        self.messages_issued = []
        self.contests = contests
        self.err_count = 0
        self.MAX_ERR_COUNT = config.telegram_bot_max_error_messages

        self.bot = BotWithMessageQueue(token=config.bot_token,
                                       request=Request(con_pool_size=8))

        self.updater = Updater(bot=self.bot)
        self.dispatcher = self.updater.dispatcher
        self.job_queue = self.updater.job_queue

        self.dispatcher.add_error_handler(self.handle_error)

        self.dispatcher.add_handler(CommandHandler('start', self.start,
                                                   pass_args=True))
        self.dispatcher.add_handler(CommandHandler('help', self.help))

    def _really_start_bot(self):
        self.dispatcher.add_handler(CommandHandler('announce', self.announce))
        self.dispatcher.add_handler(CommandHandler('openquestions',
                                                   self.list_open_questions))
        self.dispatcher.add_handler(CommandHandler('allannouncements',
                                                   self.list_all_announcements))
        self.dispatcher.add_handler(CommandHandler('purge', self.purge))
        self.dispatcher.add_handler(MessageHandler(Filters.reply,
                                                   self.on_reply))
        self.dispatcher.add_handler(CallbackQueryHandler(self.button_callback))

        self.job_queue.run_repeating(self.update, interval=5, first=0)

    def die(self):
        def just_DIE_already():
            os.kill(os.getpid(), signal.SIGINT)

        Thread(target=just_DIE_already).start()

    def handle_error(self, update, context):
        e = context.error
        err = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        logger.error(err)

        if self.id is not None:
            self.err_count += 1

            ea = escape("⌁")
            error_msg = ea + bold("brzzlt") + ea + escape(" not... feee") + \
                        ea + bold("brrzzl") + ea + escape("eeling ") + \
                        escape("welllllll...") + "\n\n" + code(escape(err)) + \
                        bold("Update was: ") + code(escape(str(update)))

            context.bot.send_message(chat_id=self.id, text=error_msg,
                                     parse_mode="MarkdownV2")

            if self.err_count == self.MAX_ERR_COUNT:
                context.bot.send_message(chat_id=self.id,
                                         text=escape("I...") +  "\n" + \
                                              escape("I think I'm gonna lay "
                                                     "down for a while..."),
                                         parse_mode="MarkdownV2")
                self.die()

    def _record_msg(self, f):
        def do_record_msg(msg):
            f(msg)
            self.messages_issued.append(msg)

        return do_record_msg

    def issue_message(self, bot, on_send = lambda _ : None, **kwargs):
        bot.send_message(on_send = self._record_msg(on_send), **kwargs)

    def issue_reply(self, msg, *args, on_send = lambda _ : None, **kwargs):
        self.bot.send_message(msg.chat.id, *args, **kwargs,
                              reply_to_message_id=msg.message_id,
                              on_send=self._record_msg(on_send))

    def start(self, update, context):
        """ The registration process

            For security reasons our bot will always only communicate with one
            chat, namely the first one that can authenticate to it using the
            password saved in the config file
        """
        bot = context.bot
        args = context.args

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

        if self.only_listen_to is not None and \
           self.only_listen_to != update.message.chat_id:
                bot.send_message(chat_id=update.message.chat_id,
                                 text="Error: I'm already pre-bound to another "
                                      "chat")
                logger.error("Someone tried to /start me although I'm "
                             "pre-bound to another chat")
                return

        # Everything is fine
        self.id = update.message.chat_id

        message = "Congratulations! I'm now bound to thy will!\n"
        if len(self.contests) == 1:
            message += "I'll assist you with the following contest.\n"
        else:
            message += "I'll assist you with the following contests.\n"
        message = escape(message) + \
                      '\n'.join(italic(" " + escape(c.name) + ": ") + \
                                escape(c.description) for c in self.contests)
        bot.send_message(chat_id=self.id,
                        text=message,
                        parse_mode="MarkdownV2")

        self._really_start_bot()

    def announce(self, update, context):
        """ Make an announcement
        """
        bot = context.bot

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

        if len(self.contests) == 0:
            update.answer(text="There's no contest I could announce this in.")
            return

        if len(self.contests) > 1:
            kb =  [[InlineKeyboardButton(text=self.contests[i].description,
                                        callback_data="A_"+str(i))]
                   for i in range(len(self.contests)) ] + \
                  [[InlineKeyboardButton(text="<I would not.>",
                                        callback_data="A_N")]]
            text = "Which contest would you like to announce this in?"
        else:
            kb =  [[InlineKeyboardButton(text="Yes", callback_data="A_0"),
                    InlineKeyboardButton(text="No",  callback_data="A_N")]]
            text = "Would you like to announce the following?"

        announcement_text = update.message.text
        header, msg = split_off_header(strip_cmd(announcement_text))
        text += "\n\n" + bold(escape(header)) + "\n" + escape(msg)

        bot.send_message(chat_id=self.id,
                            reply_to_message_id=update.message.message_id,
                            text=text,
                            reply_markup=InlineKeyboardMarkup(kb),
                            parse_mode="MarkdownV2")

    def _callback_announce(self, update, decision):
        bot = update.bot

        if decision == "N":
            update.answer(text="Alright, I won't announce anything. "
                          "Why bother?")
        else:
            self._do_announce(update, contest_id=int(decision))

        bot.delete_message(chat_id=self.id,
                           message_id=update.message.message_id)

    def _do_announce(self, update, contest_id=0):
        orig_msg = update.message.reply_to_message
        text = orig_msg.text
        contest = self.contests[contest_id]
        header, msg = split_off_header(strip_cmd(text))
        if not contest.announce(header, msg):
            self.issue_reply(orig_msg,
                             escape("I have announced the following " +
                                    "in " + contest.description + ":\n\n") +
                             bold(escape(header)) + "\n" + escape(msg),
                             parse_mode="MarkdownV2")
        else:
            self.issue_reply(orig_msg,
                             "Sorry, this didn't work...")


    def button_callback(self, update, context):
        bot = context.bot
        cq = update.callback_query

        if cq.message.chat.id != self.id:
            logger.warning("Warning! Someone tried to use the inline keyboard "
                           "in a chat I'm not registered in!")

            if self.id is not None:
                self.issue_message(bot,
                                   chat_id=self.id,
                                   text="Warning! Someone tried to use the "
                                        "inline keyboard in another chat!")
            return

        a = cq.data

        if len(a) < 2:
            logger.warning("A weird callback has occured!")
            self.issue_message(bot,
                               chat_id=self.id,
                               text="Warning! A weird callback that I can't "
                                    "interprete has occured!")

        if a[0] == 'R':
            self._callback_reply(cq, a[2:])
        elif a[0] == 'P':
            self._callback_purge(cq, a[2:])
        elif a[0] == 'A':
            self._callback_announce(cq, a[2:])
        else:
            logger.warning("A weird callback has occured!")
            self.issue_message(bot,
                               chat_id=self.id,
                               text="Warning! A weird callback that I can't "
                                    "interprete has occured!")

    def _callback_reply(self, cq, a):
        msg_id = cq.message.message_id
        q = self.questions[msg_id]

        self.reply_question(cq, q, a, short_answer=True)

    def _question_notification_params(self, q, new):
        kb =  [[InlineKeyboardButton(text="Yes", callback_data="R_Yes"),
                InlineKeyboardButton(text="No",  callback_data="R_No")],
               [InlineKeyboardButton(text="Answered in task description",
                                     callback_data="R_Answered in task "
                                                   "description")],
               [InlineKeyboardButton(text="No comment",
                                     callback_data="R_No comment"),
                InlineKeyboardButton(text="Invalid question",
                                     callback_data="R_Invalid question")],
               [InlineKeyboardButton(text="〈ignore question〉",
                                     parse_mode="MarkdownV2",
                                     callback_data="R_/ignore")]]

        return {"text": q.format(new), "parse_mode": "MarkdownV2",
                "reply_markup": InlineKeyboardMarkup(kb)}

    def _record_question(self, q, full):
        def do_record(msg):
            self.questions[msg.message_id] = q

            if full:
                Q = q.question

                if Q.id not in self.q_notifications:
                    self.q_notifications[Q.id] = []
                self.q_notifications[Q.id].append(msg)

                try:
                    msg.edit_text(**self._question_notification_params(q,
                                                                       False))
                except TelegramBadRequest:
                    logger.info("question was already up to date")

        return do_record

    def _notify_question(self, bot, q, new, show_status):
        msg = self.issue_message(bot,
                                 chat_id=self.id,
                                 **self._question_notification_params(q, new),
                                 on_send=self._record_question(q, True))

    def _update_question(self, q):
        for msg in self.q_notifications[q.question.id]:
            msg.edit_text(**self._question_notification_params(q, False))

    def _record_answer(self, q):
        def do_record(msg):
            self.questions[msg.message_id] = q
            self._update_question(q)

        return do_record

    def _notify_answer(self, q, new):
        msg = self.q_notifications[q.question.id][-1]

        notification = "This question has been answered via CMS:\n\n" if new \
                       else "The answer has been edited via CMS:\n\n"

        reply = self.issue_reply(msg,
                                 text=escape(notification) + q.format_answer(),
                                 parse_mode="MarkdownV2",
                                 on_send=self._record_answer(q))

    def _notify_question_ignore(self, q, ignore):
        msg = self.q_notifications[q.question.id][-1]

        notification = "This question has been " \
                       "{}ignored.\n\n".format("" if ignore else "un")

        reply = self.issue_reply(msg,
                                 text=escape(notification),
                                 parse_mode="MarkdownV2",
                                 on_send=self._record_answer(q))

    def _notify_announcement(self, bot, a, new):
        self.issue_message(bot,
                           chat_id=self.id,
                           text=a.format(new),
                           parse_mode="MarkdownV2")

    def update(self, context):
        """ Check for new questions, answers, and announcements
        """
        bot = context.bot
        job = context.job

        if self.id is None:
            return

        for c in self.contests:
            new_qs, new_as, updated_as, ignored_qs, unignored_qs = \
                c.poll_questions()

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

            new_announcements = c.poll_announcements()

            for a in new_announcements:
                self._notify_announcement(bot, a, True)

    def list_open_questions(self, update, context):
        bot = context.bot

        if self.id is None:
            update.message.reply_text("You have to register me first (using "
                                      "the /start command).")
            return

        if self.id != update.message.chat_id:
            logger.warning("Warning! Someone tried to list open questions in "
                           "a chat I'm not registered in!")
            self.issue_message(bot,
                               chat_id=self.id,
                               text="Warning! Someone tried to list open "
                                    "questions in another chat!")
            return

        qs = [q for c in self.contests
                for q in c.get_all_open_questions()]

        notification = ""

        if len(qs) == 1:
            notification = "There is currently *1* open question:"
        else:
            notification = "There are currently " + \
                           bold("no" if len(qs) == 0 else str(len(qs))) + \
                           " open questions" + ("" if len(qs) == 0 else ":")

        self.issue_message(bot,
                           chat_id=self.id,
                           text=notification,
                           parse_mode="MarkdownV2")

        for q in qs:
            self._notify_question(bot, q, False, False)


    def list_all_announcements(self, update, context):
        bot = context.bot

        if self.id is None:
            update.message.reply_text("You have to register me first (using "
                                      "the /start command).")
            return

        if self.id != update.message.chat_id:
            logger.warning("Warning! Someone tried to list all announcements "
                           "in a chat I'm not registered in!")
            self.issue_message(bot,
                               chat_id=self.id,
                               text="Warning! Someone tried to list all "
                                    "announcements in another chat!")
            return

        announcements = [a for c in self.contests
                           for a in c.get_all_announcements()]

        if len(announcements) == 1:
            notification = "There is currently *1* announcement:"
        else:
            notification = "There are currently " +\
                           bold("no" if len(announcements) == 0
                                     else str(len(announcements))) + " "\
                           "announcements" + ("" if len(announcements) == 0
                                                 else ":")

        self.issue_message(bot,
                           chat_id=self.id,
                           text=notification,
                           parse_mode="MarkdownV2")

        for a in announcements:
            self._notify_announcement(bot, a, False)

    def help(self, update, context):
        HELP_TEXT = \
            escape("A bot allowing to access clarification requests and "
                   "announcements of a CMS contest via Telegram.\n\n") + \
            bold("/start") + " 〈" + italic("pwd") + "〉" + \
            escape(" — tries to bind the bot to the current chat when used "
                   "with the correct password; the bot can only be bound to a "
                   "single chat at a time and all further binding attempts "
                   "will be rejected until the bot service has been "
                   "restarted\n") + \
            bold("/announce") + \
            escape(" — adds the rest of the message as an announcement to the "
                   "current contest; everything before the first line break "
                   "will be used as header\n") + \
            bold("/openquestions") + \
            escape(" — shows all ") + italic("unanswered") + \
            escape(" questions of the current contest\n") + \
            bold("/allannouncements") + \
            escape(" — shows all announcements of the current contest (") + \
            italic("use this with care as it could produce quite a lot of "
                   "output") + escape(")\n") + \
            bold("/help") + escape(" — prints this message\n") + \
            bold("/purge") + \
            escape(" — deletes all messages sent by the bot during the current "
                   "session\n\n") + \
            escape("In addition this bot will post all new questions "
                   "appearing in the system. You can answer them by "
                   "replying to the corresponding post or using the "
                   "respective inline buttons. Moreover, all answers given "
                   "and announcements made via the web interface will also "
                   "be posted and you can edit answers by replying to the "
                   "corresponding message")

        if update.message.chat_id == self.id:
            self.issue_reply(update.message,
                             HELP_TEXT,
                             parse_mode="MarkdownV2")
        else:
            update.message.reply_text(HELP_TEXT,
                                      parse_mode="MarkdownV2")

    def purge(self, update, context):
        bot = context.bot

        if self.id is None:
            update.message.reply_text("You have to register me first (using "
                                      "the /start command) — and then there "
                                      "will be nothing to purge at the "
                                      "moment anyhow…")
            return

        if self.id != update.message.chat_id:
            logger.warning("Warning! Someone issued /purge in a chat I'm not "
                           "registered in!")
            self.issue_message(bot,
                               chat_id=self.id,
                               text="Warning! Someone tried to issue /purge in "
                                    "another chat!")
            return

        kb =  [[InlineKeyboardButton(text="Yes, of course. Why wouldn't I?",
                                     callback_data="P_Yes")],
               [InlineKeyboardButton(text="Oh my god, no! Stop it! STOP!!!",
                                     callback_data="P_No")]]

        update.message.reply_text(text="Are you sure you want me to " +
                                       bold("delete") + " all messages I've "
                                       "sent during the current session?",
                                  reply_markup=InlineKeyboardMarkup(kb))

    def _callback_purge(self, update, decision):
        bot = update.bot

        if decision == "Yes":
            update.answer(text="(passive-aggressive voice) Fine, I'll delete "
                               "my recent messages.")
            self._do_purge(bot)
        else:
            update.answer(text="Okay, I won't delete nothing.")

        bot.delete_message(chat_id=self.id,
                           message_id=update.message.message_id)

    def _do_purge(self, bot):
        for msg in self.messages_issued:
            if self.id == msg.chat_id:
                bot.delete_message(chat_id=self.id,
                                   message_id=msg.message_id)

        self.messages_issued.clear()
        self.q_notifications.clear()

    def on_reply(self, update, context):
        """ Replying to a user question posted in the chat uploads the reply as
            answer.

            TODO: edits
            TODO: Replying to answers and announcements?
        """
        bot = context.bot

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
                    self.issue_reply(update.message,
                                     IGNORE_FAIL_MSG)

            else:
                q.ignore()

                if short_answer:
                    update.answer(text="I have ignored this question!")
                else:
                    self.issue_reply(update.message,
                                     "I have ignored this question!")

                self._update_question(q)

            return

        q.answer(a)

        if short_answer:
            update.answer(text="I have added your answer (“{}”)!".format(a))
        else:
            msg = self.issue_reply(update.message,
                                   "I have added your answer!",
                                   on_send=self._record_question(q, False))

        self._update_question(q)

    def run(self):
        self.updater.start_polling()
        self.updater.idle()


class TelegramBotService(Service):
    """ A service running the above bot
    """
    def __init__(self, shard, contest_id=None):
        Service.__init__(self, shard)
        self.contest_id = contest_id

    def run(self):
        id = None

        while True:
            # A contest_id was provided: we restrict ourselves to that contest
            if self.contest_id is not None:
                contests = [MyContest(self.contest_id)]
            # No contest_id was provided: we fetch all contests in the database
            else:
                contest_list = get_contest_list(_session)
                contests = [ MyContest(c.id) for c in contest_list ]

            # TODO: this should be handled better in the future (once the bot is
            # persistent?)
            # We save the id so that nobody else can access the bot after it
            # shut down (for security reasons)
            bot = TelegramBot(contests, id)
            bot.run()
            id = bot.id or id
            sleep(1)
