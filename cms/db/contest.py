#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2015 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
# Copyright © 2017 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2018 William Di Luigi <williamdiluigi@gmail.com>
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

"""Contest-related database interface for SQLAlchemy.

"""

from datetime import datetime, timedelta

from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column, ForeignKey, CheckConstraint
from sqlalchemy.types import Integer, Unicode, DateTime, Interval, Enum, \
    Boolean, String

from cms import TOKEN_MODE_DISABLED, TOKEN_MODE_FINITE, TOKEN_MODE_INFINITE
from . import Codename, Base, Admin


class Contest(Base):
    """Class to store a contest (which is a single day of a
    programming competition).

    """
    __tablename__ = 'contests'
    __table_args__ = (
        CheckConstraint("token_gen_initial <= token_gen_max"),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Short name of the contest.
    name = Column(
        Codename,
        nullable=False,
        unique=True)
    # Description of the contest (human readable).
    description = Column(
        Unicode,
        nullable=False)

    # The list of language codes of the localizations that contestants
    # are allowed to use (empty means all).
    allowed_localizations = Column(
        ARRAY(String),
        nullable=False,
        default=[])

    # The list of names of languages allowed in the contest.
    languages = Column(
        ARRAY(String),
        nullable=False,
        default=["C11 / gcc", "C++17 / g++", "Pascal / fpc"])

    # Whether contestants allowed to download their submissions.
    submissions_download_allowed = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether the user question is enabled.
    allow_questions = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether the user test interface is enabled.
    allow_user_tests = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether to prevent hidden participations to log in.
    block_hidden_participations = Column(
        Boolean,
        nullable=False,
        default=False)

    # Whether to allow username/password authentication
    allow_password_authentication = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether the registration of new users is enabled.
    allow_registration = Column(
        Boolean,
        nullable=False,
        default=False)

    # Whether to enforce that the IP address of the request matches
    # the IP address or subnet specified for the participation (if
    # present).
    ip_restriction = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether to automatically log in users connecting from an IP
    # address specified in the ip field of a participation to this
    # contest.
    ip_autologin = Column(
        Boolean,
        nullable=False,
        default=False)

    # The parameters that control contest-tokens follow. Note that
    # their effect during the contest depends on the interaction with
    # the parameters that control task-tokens, defined on each Task.

    # The "kind" of token rules that will be active during the contest.
    # - disabled: The user will never be able to use any token.
    # - finite: The user has a finite amount of tokens and can choose
    #   when to use them, subject to some limitations. Tokens may not
    #   be all available at start, but given periodically during the
    #   contest instead.
    # - infinite: The user will always be able to use a token.
    token_mode = Column(
        Enum(TOKEN_MODE_DISABLED, TOKEN_MODE_FINITE, TOKEN_MODE_INFINITE,
             name="token_mode"),
        nullable=False,
        default=TOKEN_MODE_INFINITE)

    # The maximum number of tokens a contestant is allowed to use
    # during the whole contest (on all tasks).
    token_max_number = Column(
        Integer,
        CheckConstraint("token_max_number > 0"),
        nullable=True)

    # The minimum interval between two successive uses of tokens for
    # the same user (on any task).
    token_min_interval = Column(
        Interval,
        CheckConstraint("token_min_interval >= '0 seconds'"),
        nullable=False,
        default=timedelta())

    # The parameters that control generation (if mode is "finite"):
    # the user starts with "initial" tokens and receives "number" more
    # every "interval", but their total number is capped to "max".
    token_gen_initial = Column(
        Integer,
        CheckConstraint("token_gen_initial >= 0"),
        nullable=False,
        default=2)
    token_gen_number = Column(
        Integer,
        CheckConstraint("token_gen_number >= 0"),
        nullable=False,
        default=2)
    token_gen_interval = Column(
        Interval,
        CheckConstraint("token_gen_interval > '0 seconds'"),
        nullable=False,
        default=timedelta(minutes=30))
    token_gen_max = Column(
        Integer,
        CheckConstraint("token_gen_max > 0"),
        nullable=True)

    # Timezone for the contest. All timestamps in CWS will be shown
    # using the timezone associated to the logged-in user or (if it's
    # None or an invalid string) the timezone associated to the
    # contest or (if it's None or an invalid string) the local
    # timezone of the server. This value has to be a string like
    # "Europe/Rome", "Australia/Sydney", "America/New_York", etc.
    timezone = Column(
        Unicode,
        nullable=True)

    # Maximum number of submissions or user_tests allowed for each user
    # during the whole contest or None to not enforce this limitation.
    max_submission_number = Column(
        Integer,
        CheckConstraint("max_submission_number > 0"),
        nullable=True)
    max_user_test_number = Column(
        Integer,
        CheckConstraint("max_user_test_number > 0"),
        nullable=True)

    # Minimum interval between two submissions or user_tests, or None to
    # not enforce this limitation.
    min_submission_interval = Column(
        Interval,
        CheckConstraint("min_submission_interval > '0 seconds'"),
        nullable=True)
    min_user_test_interval = Column(
        Interval,
        CheckConstraint("min_user_test_interval > '0 seconds'"),
        nullable=True)

    # The scores for this contest will be rounded to this number of
    # decimal places.
    score_precision = Column(
        Integer,
        CheckConstraint("score_precision >= 0"),
        nullable=False,
        default=0)

    # Contest (id and object) to which this user group belongs.
    main_group_id = Column(
        Integer,
        ForeignKey("group.id", use_alter=True, name="fk_contest_main_group_id",
                   onupdate="CASCADE", ondelete="SET NULL"),
        # nullable=False,  # This would fail with post_update=True.
        index=True)
    main_group = relationship(
        "Group",
        primaryjoin="Group.id==Contest.main_group_id",
        post_update=True)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # groups (list of Group objects)
    # These one-to-many relationships are the reversed directions of
    # the ones defined in the "child" classes using foreign keys.

    tasks = relationship(
        "Task",
        collection_class=ordering_list("num"),
        order_by="[Task.num]",
        cascade="all",
        passive_deletes=True,
        back_populates="contest")

    announcements = relationship(
        "Announcement",
        order_by="[Announcement.timestamp]",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="contest")

    participations = relationship(
        "Participation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="contest")

    # TODO Add groups here?


    # Moreover, we have the following methods.
    # get_submissions (defined in __init__.py)
    # get_submission_results (defined in __init__.py)
    # get_user_tests (defined in __init__.py)
    # get_user_test_results (defined in __init__.py)

    # FIXME - Use SQL syntax
    def get_task(self, task_name):
        """Return the first task in the contest with the given name.

        task_name (string): the name of the task we are interested in.

        return (Task): the corresponding task object.

        raise (KeyError): if no tasks with the given name are found.

        """
        for task in self.tasks:
            if task.name == task_name:
                return task
        raise KeyError("Task not found")

    # FIXME - Use SQL syntax
    def get_task_index(self, task_name):
        """Return the index of the first task in the contest with the
        given name.

        task_name (string): the name of the task we are interested in.

        return (int): the index of the corresponding task.

        raise (KeyError): if no tasks with the given name are found.

        """
        for idx, task in enumerate(self.tasks):
            if task.name == task_name:
                return idx
        raise KeyError("Task not found")

    def get_group(self, name):
        """ Return the group with the given name.

        name (string): the name of the group we are interested in.
        return (Group): the corresponding group object, or KeyError.

        """
        # FIXME - Use SQL syntax
        for g in self.groups:
            if g.name == name:
                return g
        raise KeyError("Group not found")

    def enumerate_files(self, skip_submissions=False, skip_user_tests=False,
                        skip_generated=False):
        """Enumerate all the files (by digest) referenced by the
        contest.

        return (set): a set of strings, the digests of the file
                      referenced in the contest.

        """
        # Here we cannot use yield, because we want to detect
        # duplicates

        files = set()
        for task in self.tasks:

            # Enumerate statements
            for file_ in itervalues(task.statements):
                files.add(file_.digest)

            # Enumerate attachments
            for file_ in itervalues(task.attachments):
                files.add(file_.digest)

            # Enumerate spoilers
            for file_ in itervalues(task.spoilers):
                files.add(file_.digest)

            # Enumerate managers
            for dataset in task.datasets:
                for file_ in itervalues(dataset.managers):
                    files.add(file_.digest)

            # Enumerate testcases
            for dataset in task.datasets:
                for testcase in itervalues(dataset.testcases):
                    files.add(testcase.input)
                    files.add(testcase.output)

        if not skip_submissions:
            for submission in self.get_submissions():

                # Enumerate files
                for file_ in itervalues(submission.files):
                    files.add(file_.digest)

                # Enumerate executables
                if not skip_generated:
                    for sr in submission.results:
                        for file_ in itervalues(sr.executables):
                            files.add(file_.digest)

        if not skip_user_tests:
            for user_test in self.get_user_tests():

                files.add(user_test.input)

                if not skip_generated:
                    for ur in user_test.results:
                        if ur.output is not None:
                            files.add(ur.output)

                # Enumerate files
                for file_ in itervalues(user_test.files):
                    files.add(file_.digest)

                # Enumerate managers
                for file_ in itervalues(user_test.managers):
                    files.add(file_.digest)

                # Enumerate executables
                if not skip_generated:
                    for ur in user_test.results:
                        for file_ in itervalues(ur.executables):
                            files.add(file_.digest)

        return files

    @staticmethod
    def _tokens_available(token_timestamps, token_mode,
                          token_max_number, token_min_interval,
                          token_gen_initial, token_gen_number,
                          token_gen_interval, token_gen_max, start, timestamp):
        """Do exactly the same computation stated in tokens_available,
        but ensuring only a single set of token_* directive.
        Basically, tokens_available calls this twice for contest-wise
        and task-wise parameters and then assembles the result.

        token_timestamps ([datetime]): list of timestamps of used
            tokens, sorted in chronological order.
        token_* (int): the parameters we want to enforce.
        start (datetime): the time from which we start accumulating
            tokens.
        timestamp (datetime): the time relative to which make the
            calculation (has to be greater than or equal to all
            elements of token_timestamps).

        return ((int, datetime|None, datetime|None)): same as
            tokens_available.

        """
        # If tokens are disabled there are no tokens available.
        if token_mode == "disabled":
            return (0, None, None)

        # If tokens are infinite there are always tokens available.
        if token_mode == "infinite":
            return (-1, None, None)

        # expiration is the timestamp at which all min_intervals for
        # the tokens played up to now have expired (i.e. the first
        # time at which we can play another token). If no tokens have
        # been played so far, this time is the start of the contest.
        expiration = \
            token_timestamps[-1] + token_min_interval \
            if len(token_timestamps) > 0 else start

        # If we already played the total number allowed, we don't have
        # anything left.
        played_tokens = len(token_timestamps)
        if token_max_number is not None and played_tokens >= token_max_number:
            return (0, None, None)

        # avail is the current number of available tokens. We are
        # going to rebuild all the history to know how many of them we
        # have now.
        # We start with the initial number (it's already capped to max
        # by the DB). token_gen_initial can be ignored after this.
        avail = token_gen_initial

        def generate_tokens(prev_time, next_time):
            """Compute how many tokens have been generated between the
            two timestamps.

            prev_time (datetime): timestamp of begin of interval.
            next_time (datetime): timestamp of end of interval.
            return (int): number of tokens generated.

            """
            # How many generation times we passed from start to
            # the previous considered time?
            before_prev = ((prev_time - start).total_seconds()
                           // token_gen_interval.total_seconds())
            # And from start to the current considered time?
            before_next = ((next_time - start).total_seconds()
                           // token_gen_interval.total_seconds())
            # So...
            return token_gen_number * (before_next - before_prev)

        # Previous time we considered
        prev_token = start

        # Simulating!
        for token in token_timestamps:
            # Increment the number of tokens because of generation.
            avail += generate_tokens(prev_token, token)
            if token_gen_max is not None:
                avail = min(avail, token_gen_max)

            # Play the token.
            avail -= 1

            prev_token = token

        avail += generate_tokens(prev_token, timestamp)
        if token_gen_max is not None:
            avail = min(avail, token_gen_max)

        # Compute the time in which the next token will be generated.
        next_gen_time = None
        if token_gen_number > 0 and \
                (token_gen_max is None or avail < token_gen_max):
            next_gen_time = \
                start + token_gen_interval * \
                int((timestamp - start).total_seconds() /
                    token_gen_interval.total_seconds() + 1)

        # If we have more tokens than how many we are allowed to play,
        # cap it, and note that no more will be generated.
        if token_max_number is not None:
            if avail >= token_max_number - played_tokens:
                avail = token_max_number - played_tokens
                next_gen_time = None

        return (avail,
                next_gen_time,
                expiration if expiration > timestamp else None)

    def tokens_available(self, participation, task, timestamp=None):
        """Return three pieces of data:

        [0] the number of available tokens for the user to play on the
            task (independently from the fact that (s)he can play it
            right now or not due to a min_interval wating for
            expiration); -1 means infinite tokens;

        [1] the next time in which a token will be generated (or
            None); from the user perspective, i.e.: if the user will
            do nothing, [1] is the first time in which their number of
            available tokens will be greater than [0];

        [2] the time when the min_interval will expire, or None

        In particular, let r the return value of this method. We can
        sketch the code in the following way.:

        if r[0] > 0 or r[0] == -1:
            we have tokens
            if r[2] is None:
                we can play a token
            else:
                we must wait till r[2] to play a token
            if r[1] is not None:
                next one will be generated at r[1]
            else:
                no other tokens will be generated (max/total reached ?)
        else:
            we don't have tokens right now
            if r[1] is not None:
                next one will be generated at r[1]
                if r[2] is not None and r[2] > r[1]:
                    but we must wait also till r[2] to play it
            else:
                no other tokens will be generated (max/total reached ?)

        Note also that this method assumes that all played tokens were
        regularly played, and that there are no tokens played in the
        future. Also, if r[0] == 0 and r[1] is None, then r[2] should
        be ignored.

        participation (Participation): the participation.
        task (Task): the task.
        timestamp (datetime|None): the time relative to which making
            the calculation, or None to use now.

        return ((int, datetime|None, datetime|None)): see description
            above.

        """
        if timestamp is None:
            timestamp = make_datetime()

        group = participation.group

        # Take the list of the tokens already played (sorted by time).
        tokens = participation.get_tokens()
        token_timestamps_contest = sorted(token.timestamp
                                          for token in tokens)
        token_timestamps_task = sorted(
            token.timestamp for token in tokens
            if token.submission.task.name == task.name)

        # If the contest is USACO-style (i.e., the time for each user
        # start when they log in for the first time), then we start
        # accumulating tokens from the user starting time; otherwise,
        # from the start of the contest.
        start = group.start
        if group.per_user_time is not None:
            start = participation.starting_time

        # Compute separately for contest-wise and task-wise.
        res_contest = Contest._tokens_available(
            token_timestamps_contest, self.token_mode,
            self.token_max_number, self.token_min_interval,
            self.token_gen_initial, self.token_gen_number,
            self.token_gen_interval, self.token_gen_max, start, timestamp)
        res_task = Contest._tokens_available(
            token_timestamps_task, task.token_mode,
            task.token_max_number, task.token_min_interval,
            task.token_gen_initial, task.token_gen_number,
            task.token_gen_interval, task.token_gen_max, start, timestamp)

        # Merge the results.

        # First, the "expiration".
        if res_contest[2] is None:
            expiration = res_task[2]
        elif res_task[2] is None:
            expiration = res_contest[2]
        else:
            expiration = max(res_task[2], res_contest[2])

        # Then, check if both are infinite
        if res_contest[0] == -1 and res_task[0] == -1:
            res = (-1, None, expiration)
        # Else, "combine" them appropriately.
        else:
            # Having infinite contest tokens, in this situation, is the
            # same as having a finite number that is strictly greater
            # than the task tokens. The same holds the other way, too.
            if res_contest[0] == -1:
                res_contest = (res_task[0] + 1, None, None)
            if res_task[0] == -1:
                res_task = (res_contest[0] + 1, None, None)

            # About next token generation time: we need to see when the
            # *minimum* between res_contest[0] and res_task[0] is
            # increased by one, so if there is an actual minimum we
            # need to consider only the next generation time for it.
            # Otherwise, if they are equal, we need both to generate an
            # additional token and we store the maximum between the two
            # next times of generation.
            if res_contest[0] < res_task[0]:
                # We have more task-tokens than contest-tokens.
                # We just need a contest-token to be generated.
                res = (res_contest[0], res_contest[1], expiration)
            elif res_task[0] < res_contest[0]:
                # We have more contest-tokens than task-tokens.
                # We just need a task-token to be generated.
                res = (res_task[0], res_task[1], expiration)
            else:
                # Darn, we need both!
                if res_contest[1] is None or res_task[1] is None:
                    res = (res_task[0], None, expiration)
                else:
                    res = (res_task[0], max(res_contest[1], res_task[1]),
                           expiration)

        return res

    def phase(self, timestamp):
        """Return: -1 if contest isn't started yet at time timestamp,
                    0 if the contest is active at time timestamp,
                    1 if the contest has ended but analysis mode
                      hasn't started yet
                    2 if the contest has ended and analysis mode is active
                    3 if the contest has ended and analysis mode is disabled or
                      has ended

        timestamp (datetime): the time we are iterested in.
        return (int): contest phase as above.

        """
        if timestamp < self.start:
            return -1
        if timestamp <= self.stop:
            return 0
        if self.analysis_enabled:
            if timestamp < self.analysis_start:
                return 1
            elif timestamp <= self.analysis_stop:
                return 2
        return 3

class Announcement(Base):
    """Class to store a messages sent by the contest managers to all
    the users.

    """
    __tablename__ = 'announcements'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Time, subject and text of the announcement.
    timestamp = Column(
        DateTime,
        nullable=False)
    subject = Column(
        Unicode,
        nullable=False)
    text = Column(
        Unicode,
        nullable=False)

    # Source of the announcement (web/telegram)
    src = Column(
        Unicode,
        nullable=False)

    # Contest (id and object) owning the announcement.
    contest_id = Column(
        Integer,
        ForeignKey(Contest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    contest = relationship(
        Contest,
        back_populates="announcements")

    # Admin that created the announcement (or null if the admin has been
    # later deleted). Admins only loosely "own" an announcement, so we do not
    # back populate any field in Admin, nor delete the announcement if the
    # admin gets deleted.
    admin_id = Column(
        Integer,
        ForeignKey(Admin.id,
                   onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True)
    admin = relationship(Admin)
