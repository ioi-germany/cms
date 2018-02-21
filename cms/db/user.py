#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2015 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2015 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

"""User-related database interface for SQLAlchemy.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *

from datetime import datetime, timedelta

from sqlalchemy.schema import Column, ForeignKey, CheckConstraint, \
    UniqueConstraint
from sqlalchemy.types import Boolean, Integer, String, Unicode, DateTime, \
    Interval
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import ARRAY, CIDR

from cmscommon.crypto import generate_random_password, build_password

from . import Base, Contest, CastingArray, CodenameConstraint


class Group(Base):
    """Class to store a group of users (for timing, etc.).

    """
    __tablename__ = 'group'
    __table_args__ = (
        UniqueConstraint('contest_id', 'name'),
        CheckConstraint("start <= stop"),
        CheckConstraint("stop <= analysis_start"),
        CheckConstraint("analysis_start <= analysis_stop"),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    name = Column(
        Unicode,
        nullable=False)

    # Beginning and ending of the contest.
    start = Column(
        DateTime,
        nullable=False,
        default=datetime(2000, 1, 1))
    stop = Column(
        DateTime,
        nullable=False,
        default=datetime(2100, 1, 1))

    # Beginning and ending of the contest anaylsis mode.
    analysis_enabled = Column(
        Boolean,
        nullable=False,
        default=False)
    analysis_start = Column(
        DateTime,
        nullable=False,
        default=datetime(2100, 1, 1))
    analysis_stop = Column(
        DateTime,
        nullable=False,
        default=datetime(2100, 1, 1))

    # Max contest time for each user in seconds.
    per_user_time = Column(
        Interval,
        CheckConstraint("per_user_time >= '0 seconds'"),
        nullable=True)

    # Contest (id and object) to which this user group belongs.
    contest_id = Column(
        Integer,
        ForeignKey(Contest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        # nullable=False,
        index=True)
    contest = relationship(
        Contest,
        backref=backref('groups',
                        cascade="all, delete-orphan",
                        passive_deletes=True),
        primaryjoin="Contest.id==Group.contest_id")

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

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # participations (list of Participation objects)


class User(Base):
    """Class to store a user.

    """

    __tablename__ = 'users'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Real name (human readable) of the user.
    first_name = Column(
        Unicode,
        nullable=False)
    last_name = Column(
        Unicode,
        nullable=False)

    # Username and password to log in the CWS.
    username = Column(
        Unicode,
        CodenameConstraint("username"),
        nullable=False,
        unique=True)
    password = Column(
        Unicode,
        nullable=False,
        default=lambda: build_password(generate_random_password()))

    # Email for any communications in case of remote contest.
    email = Column(
        Unicode,
        nullable=True)

    # Timezone for the user. All timestamps in CWS will be shown using
    # the timezone associated to the logged-in user or (if it's None
    # or an invalid string) the timezone associated to the contest or
    # (if it's None or an invalid string) the local timezone of the
    # server. This value has to be a string like "Europe/Rome",
    # "Australia/Sydney", "America/New_York", etc.
    timezone = Column(
        Unicode,
        nullable=True)

    # The language codes accepted by this user (from the "most
    # preferred" to the "least preferred"). If in a contest there is a
    # statement available in some of these languages, then the most
    # preferred of them will be highlighted.
    # FIXME: possibly move it to Participation and change it back to
    # primary_statements
    preferred_languages = Column(
        ARRAY(String),
        nullable=False,
        default=[])

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # participations (list of Participation objects)


class Team(Base):
    """Class to store a team.

    A team is a way of grouping the users participating in a contest.
    This grouping has no effect on the contest itself; it is only used
    for display purposes in RWS.

    """

    __tablename__ = 'teams'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Team code (e.g. the ISO 3166-1 code of a country)
    code = Column(
        Unicode,
        CodenameConstraint("code"),
        nullable=False,
        unique=True)

    # Human readable team name (e.g. the ISO 3166-1 short name of a country)
    name = Column(
        Unicode,
        nullable=False)

    # TODO: decide if the flag images will eventually be stored here.
    # TODO: (hopefully, the same will apply for faces in User).


class Participation(Base):
    """Class to store a single participation of a user in a contest.

    """
    __tablename__ = 'participations'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # The user can log in CWS only from this IP address or subnet.
    ip = Column(
        CastingArray(CIDR),
        nullable=True)

    # Starting time: for contests where every user has at most x hours
    # of the y > x hours totally available, this is the time the user
    # decided to start their time-frame.
    starting_time = Column(
        DateTime,
        nullable=True)

    # A shift in the time interval during which the user is allowed to
    # submit.
    delay_time = Column(
        Interval,
        CheckConstraint("delay_time >= '0 seconds'"),
        nullable=False,
        default=timedelta())

    # An extra amount of time allocated for this user.
    extra_time = Column(
        Interval,
        CheckConstraint("extra_time >= '0 seconds'"),
        nullable=False,
        default=timedelta())

    # Contest-specific password. If this password is not null then the
    # traditional user.password field will be "replaced" by this field's
    # value (only for this participation).
    password = Column(
        Unicode,
        nullable=True)

    # A hidden participation (e.g. does not appear in public rankings), can
    # also be used for debugging purposes.
    hidden = Column(
        Boolean,
        nullable=False,
        default=False)

    # An unrestricted participation (e.g. contest time,
    # maximum number of submissions, minimum interval between submissions,
    # maximum number of user tests, minimum interval between user tests),
    # can also be used for debugging purposes.
    unrestricted = Column(
        Boolean,
        nullable=False,
        default=False)

    # Contest (id and object) to which the user is participating.
    contest_id = Column(
        Integer,
        ForeignKey(Contest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    contest = relationship(
        Contest,
        backref=backref("participations",
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # User (id and object) which is participating.
    user_id = Column(
        Integer,
        ForeignKey(User.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    user = relationship(
        User,
        backref=backref("participations",
                        cascade="all, delete-orphan",
                        passive_deletes=True))
    __table_args__ = (UniqueConstraint('contest_id', 'user_id'),)

    # Group this user belongs to
    group_id = Column(
        Integer,
        ForeignKey(Group.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    group = relationship(
        Group,
        backref=backref("participations",
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # Team (id and object) that the user is representing with this
    # participation.
    team_id = Column(
        Integer,
        ForeignKey(Team.id,
                   onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=True)
    team = relationship(
        Team,
        backref=backref("participations",
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # messages (list of Message objects)
    # questions (list of Question objects)
    # submissions (list of Submission objects)
    # user_tests (list of UserTest objects)

    # Moreover, we have the following methods.
    # get_tokens (defined in __init__.py)


class Message(Base):
    """Class to store a private message from the managers to the
    user.

    """
    __tablename__ = 'messages'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Time the message was sent.
    timestamp = Column(
        DateTime,
        nullable=False)

    # Subject and body of the message.
    subject = Column(
        Unicode,
        nullable=False)
    text = Column(
        Unicode,
        nullable=False)

    # Participation (id and object) owning the message.
    participation_id = Column(
        Integer,
        ForeignKey(Participation.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    participation = relationship(
        Participation,
        backref=backref('messages',
                        order_by=[timestamp],
                        cascade="all, delete-orphan",
                        passive_deletes=True))


class Question(Base):
    """Class to store a private question from the user to the
    managers, and its answer.

    """
    __tablename__ = 'questions'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Time the question was made.
    question_timestamp = Column(
        DateTime,
        nullable=False)

    # Subject and body of the question.
    subject = Column(
        Unicode,
        nullable=False)
    text = Column(
        Unicode,
        nullable=False)

    # Time the reply was sent.
    reply_timestamp = Column(
        DateTime,
        nullable=True)
    
    # Last time something about the answer changed
    last_action = Column(
        DateTime,
        nullable=True)

    # Has this message been ignored by the admins?
    ignored = Column(
        Boolean,
        nullable=False,
        default=False)

    # Short (as in 'chosen amongst some predetermined choices') and
    # long answer.
    reply_subject = Column(
        Unicode,
        nullable=True)
    reply_text = Column(
        Unicode,
        nullable=True)

    # Source of the answer (web / telegram)
    reply_source = Column(
        Unicode,
        nullable=True)

    # Participation (id and object) owning the question.
    participation_id = Column(
        Integer,
        ForeignKey(Participation.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    participation = relationship(
        Participation,
        backref=backref('questions',
                        order_by=[question_timestamp, reply_timestamp],
                        cascade="all, delete-orphan",
                        passive_deletes=True))
