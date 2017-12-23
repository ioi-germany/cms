#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017 Tobias Lenz <t_lenz94@web.de>
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

from telegram.ext import *

from cms import config
from cms.db import Session, Contest, Question, User, Announcement
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
        try:
            self.sql_session.commit()
        except IntegrityError as e:
            logger.error("Couldn't apply commit to database. Message: {}".\
                             format(e))
            return False
        else:
            return True


class MyQuestion(WithDatabaseAccess):
    """ Thin wrapper around question
    """
    def __init__(self, question, sql_session):
        self.question = question
        self.answered_via_telegram = False
        super(MyQuestion, self).__init__(sql_session)

    def answer(self, a):
        self.question.reply_timestamp = make_datetime()
        self.question.reply_subject = ""
        self.question.reply_text = a
        self.answered_via_telegram = True
        
        return self._commit()
    
    def get_answer(self):
        q = Question.get_from_id(self.question.id, Session())
        return q.reply_subject, q.reply_text
    
    def __getattr__(self, attr):    
        return self.question.__getattribute__(attr)
        

class QuestionList:
    """ Keeps track of all the currently unanswered questions
    """
    def __init__(self):
        self.known_unanswered = []
    
    def update(self, unanswered):
        all_unanswered_ids = {q.id for q in unanswered}
        known_unanswered_ids = {q.id for q in self.known_unanswered}
        
        new_questions = [q for q in unanswered 
                                 if q.id not in known_unanswered_ids]
        
        external_answers = [q for q in self.known_unanswered
                                    if q.id not in all_unanswered_ids and
                                       not q.answered_via_telegram]
        
        self.known_unanswered = [q for q in self.known_unanswered
                                         if q.id in all_unanswered_ids] + \
                                new_questions
        
        return new_questions, external_answers
    
    def open_questions(self):
        return self.known_unanswered[:]


class MyContest(WithDatabaseAccess):
    """ Encapsulates access to the contest currently running
    """    
    def __init__(self, contest_id):
        super(MyContest, self).__init__()

        self.contest_id = contest_id
        self.contest = Contest.get_from_id(contest_id, self.sql_session)
        self.questions = QuestionList()

    def announce(self, header, body):
        ann = Announcement(make_datetime(), header, body, contest=self.contest)
        return self._commit()

    def poll_questions(self):
        unanswered = self.sql_session.query(Question).join(User)\
                         .filter(User.contest_id == self.contest_id)\
                         .filter(Question.reply_timestamp == None)\
                         .filter(Question.ignored == False)
        
        return self.questions.update([MyQuestion(q, self.sql_session)
                                      for q in unanswered])

    def get_all_open_questions(self):
        return self.questions.open_questions()

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
        self.dispatcher.add_handler(CommandHandler('help', self.help))
        self.dispatcher.add_handler(MessageHandler(Filters.reply,
                                                   self.on_reply))
       
        self.job_queue.run_repeating(self.update_questions, interval=5, first=0)
        
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
        
        header,msg = split_off_header(strip_cmd(update.message.text))
        
        if self.contest.announce(header, msg):
            update.message.reply_text("I have announced the following:\n\n" + 
                                      bold(header) + "\n" + msg,
                                      parse_mode="Markdown")
        else:
            update.message.reply_text("Sorry, this didn't work...")
            
    def _notify_question(self, bot, q, new):
        msg = bot.send_message(chat_id=self.id,
                               text=("New question" if new else "Question") + 
                                    " by " + italic(q.user.username) +
                                    " (Timestamp: {}):\n\n".\
                                       format(q.question_timestamp) +
                                    bold(q.subject) + "\n" +
                                    q.text,
                               parse_mode="Markdown")
        self.questions[msg.message_id] = q
        self.q_notifications[q.id] = msg
        
        logger.info(self.q_notifications)
    
    def _notify_answer(self, q):
        msg = self.q_notifications[q.id]
        rep_subject, rep_text = q.get_answer()
        
        msg.reply_text(text="This question has been answered via CMS:\n\n" +
                            (bold(rep_subject) if rep_subject else rep_text),
                       quote=True,
                       parse_mode="Markdown")
    
    def update_questions(self, bot, job):
        """ Check for new questions and answers
        """
        if self.id is None:
            return
        
        unanswered, answered_in_system = self.contest.poll_questions()
        
        for q in unanswered:
            self._notify_question(bot, q, True)

        for q in answered_in_system:
            self._notify_answer(q)

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
            notification = "There is currently *1* open question"
        else:
            notification = "There are currently " + \
                           bold("no" if len(qs) == 0 else str(len(qs))) + \
                           " open questions"
        
        bot.send_message(chat_id=self.id,
                         text=notification,
                         parse_mode="Markdown")
        
        for q in qs:
            self._notify_question(bot, q, False)
  
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
                                  "/help - shows this message\n\n"
                                  "In addition this bot will post all new "
                                  "questions appearing in the system. You can "
                                  "answer them by replying to the "
                                  "corresponding post.")
    
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
                                  "message outside of the chat I'm bound to "
                                  "(or magically answered to a question from "
                                  "my fixed chat in a DIFFERENT chat)")
            return
        
        msg_id = orig_msg.message_id
        
        if msg_id in self.questions: 
            q = self.questions[msg_id]
            
        else:
            return
        
        self.reply_question(update, q, new_msg.text)
        
    def reply_question(self, update, q, a):
        """ Reply to the user question q with the answer a
        """
        q.answer(a)
        
        update.message.reply_text("I have added your answer!", quote=True)
    
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
