#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2014 Fabian Gundlach <320pointsguy@gmail.com>
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

from Messenger import print_msg
from CommonConfig import exported_function, CommonConfig
from TaskConfig import TaskConfig
from LocationStack import chdir
from cms.db import Contest, User, Group
import os
import shutil
from datetime import datetime
import pytz
import json


class MyGroup(object):
    def __init__(self, name, start, stop, per_user_time):
        self.name = name
        self.start = start
        self.stop = stop
        self.per_user_time = per_user_time


class MyUser(object):
    def __init__(self, username, password, group, firstname, lastname,
                 ip, hidden, timezone, primary_statements):
        self.username = username
        self.password = password
        self.group = group
        self.firstname = firstname
        self.lastname = lastname
        self.ip = ip
        self.hidden = hidden
        self.timezone = timezone
        self.primary_statements = primary_statements


class ContestConfig(CommonConfig):
    """
    Class for contest configuration files.

    :ivar wdir: The build directory for this contest
    :ivar contestname: The (short) name of this contest
    :ivar tasks: List of task configuration objects
    :ivar groups: List of user groups
    :ivar defaultgroup: The default user group
    :ivar users: List of users

    This object is exported as a variable called :samp:`contest`.
    """
    def __init__(self, rules, name, ignore_latex=False, onlytask=None,
                 make_datasets=True):
        """
        Initialize.

        rules (string): directory for rules persistency

        name (string): (short) contest name

        onlytask (string): if specified, then every task except the task with
                           this name is ignored

        """
        super(ContestConfig, self).__init__(rules, ignore_latex=ignore_latex)

        self.onlytask = onlytask

        self.make_datasets = make_datasets

        self.contestname = name

        self.tasks = []

        self.groups = []
        self.defaultgroup = None
        self.users = []

        # Export contest variable
        self.exported["contest"] = self

        # Default submission limits
        self.submission_limits(None, None)
        self.user_test_limits(None, None)

        self._analysis = False

        # a standard tokenwise comparator (specified here so that it has to be
        # compiled at most once per contest)
        shutil.copy(os.path.join(self._get_ready_dir(), "tokens.cpp"),
                    "tokens.cpp")
        self.token_equ_fp = self.compile("tokens")

        # there is no upstream for contest
        self.bequeathing = False
        self.inheriting = False

        self.wdir = os.getcwd()

        self.ontasks = []

    def _readconfig(self, filename):
        print_msg("Loading contest {}".format(self.contestname), headerdepth=1)
        super(ContestConfig, self)._readconfig(filename)

    @exported_function
    def ontask(self, f):
        """
        Register this function for being called immediately before a task is
        loaded. The function will get the task object as first and only
        argument.
        """
        self.ontasks.append(f)

    @exported_function
    def time(self, s, timezone=None):
        """
        Convert a time from a given time zone to UTC.

        s (string): time to convert in the format %Y-%m-%d %H:%M:%S

        timezone (string): time zone to convert to (by default the contest
                           time zone)

        return (string): string representing the time in UTC

        """
        if timezone is None:
            timezone = self._timezone
        time = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        tz = pytz.timezone(timezone)
        convtime = tz.normalize(tz.localize(time)).astimezone(pytz.utc)
        return str(convtime)

    @exported_function
    def description(self, s):
        """
        Set the contest description.

        s (unicode): contest description

        """
        print_msg("Setting description to {}".format(s), headerdepth=10)
        self._description = s

    @exported_function
    def timezone(self, s):
        """
        Set the contest time zone.

        s (unicode): contest time zone (e.g. Europe/Berlin)

        """
        print_msg("Setting timezone to {}".format(s), headerdepth=10)
        self._timezone = s

    @exported_function
    def user_group(self, s, start, stop, per_user_time=None):
        """
        Create a user group.

        s (unicode): user group name;
                     if the group is called "main", it is assumed to be the
                     default group.

        start (string): start time (should be created via a call to time())

        stop (string): stop time (should be created via a call to time())

        per_user_time (timedelta): enable USACO mode with this time per user;
            see :ref:`configuringacontest_usaco-like-contests`

        return (MyGroup): object representing the created group

        """
        usaco_mode_str = ""
        if per_user_time is not None:
            usaco_mode_str = \
                " in USACO mode with time {}".format(per_user_time)
        print_msg("Creating user group {} (working from {} to {}{})"
                  .format(s, start, stop, usaco_mode_str), headerdepth=10)
        r = MyGroup(s, start, stop, per_user_time)
        self.groups.append(r)
        if s == "main":
            self.defaultgroup = r
        return r

    @exported_function
    def user(self, username, password, firstname, lastname, group=None,
             ip=None, hidden=False, timezone=None, primary_statements=[]):
        """
        Add a user.

        username (unicode): user name (for login)

        password (unicode): password

        group (MyGroup): the group to add this user to (by default the
                         default group, which is usually called main)

        firstname (unicode): first name

        lastname (unicode): last name

        ip (unicode): ip address the user must log in from (if this feature
                      is enabled in CMS)

        hidden (bool): whether this user is hidden (not shown on the official
                       scoreboard)

        timezone (unicode): time zone for this user (if different from contest
                            time zone)

        primary_statements (string[] or {string: string[]}): either a list of
            languages (it is assumed that all tasks have a translation for
            this language) or a dictionary mapping task names to language names

        return (MyUser): object representing the created user

        """
        if group is None:
            if self.defaultgroup is None:
                raise Exception("You have to specify a group")
            group = self.defaultgroup
        print_msg("Adding user {} to group {}".format(username, group.name),
                  headerdepth=10)
        self.users.append(MyUser(username, password, group,
                                 firstname, lastname,
                                 ip, hidden, timezone, primary_statements))
        return self.users[-1]

    @exported_function
    def task(self, s):
        """
        Add a task to this contest.

        s (unicode): task name; the task description has to reside in the
                     folder with the same name

        """
        # Check if this task should be ignored
        if self.onlytask is not None and self.onlytask != s:
            return

        if not os.path.isdir(s):
            raise Exception("No directory found for task {}".format(s))

        with chdir(s):
            if not os.path.isfile("config.py"):
                raise Exception("Couldn't find task config file. Make sure it "
                                "is named 'config.py' and located on the "
                                "topmost level of the folder {}"
                                .format(os.getcwd()))

            with TaskConfig(self, self.rules, s, len(self.tasks),
                            ignore_latex=self.ignore_latex,
                            make_datasets=self.make_datasets) as taskconfig:
                for f in self.ontasks:
                    f(taskconfig)
                taskconfig._readconfig("config.py")
                taskconfig._printresult()
                self.tasks.append(taskconfig)
            print_msg("Task {} loaded completely".format(s), success=True)

    @exported_function
    def test_user(self, u):
        """
        Set the user to submit unit tests as.

        u (MyUser): test user

        """
        self._mytestuser = u

    @exported_function
    def analysis(self):
        """
        Activate analysis mode for all users (subject to the start and end
        times specified for the corresponding user groups).
        This has the following consequences:
         a) The token modes for the contest and for all tasks are set to
            'infinite'.
         b) All test cases are offered for download.

        WARNING: Be careful with user groups: Users that shall not be allowed
        to participate in the analysis mode must not be able to log in! Set
        their start and end time to a point in the far future.

        WARNING: Export the scores before activating the analysis mode!
        """
        self._analysis = True

    def short_path(self, f):
        """
        Return a (possibly) shorter name for a file (which can be relative
        to the contest build directory).

        f (string): file name to shorten

        return (string): shortened file name

        """
        return os.path.relpath(os.path.abspath(f), self.wdir)

    def _makecontest(self):
        """
        Return a Contest object which can be saved to the database.

        return (Contest): database object for the contest

        """
        if self.defaultgroup is None:
            raise Exception("You have to specify a default group")
        cdb = Contest(name=self.contestname, description=self._description)
        cdb.timezone = self._timezone
        if self._analysis:
            self.infinite_tokens()
        self._set_tokens(cdb)
        cdb.max_submission_number = self.max_submission_number
        cdb.min_submission_interval = self.min_submission_interval
        cdb.max_user_test_number = self.max_user_test_number
        cdb.min_user_test_interval = self.min_user_test_interval

        self.groupsdb = {}
        for g in self.groups:
            if g.name in self.groupsdb:
                raise Exception("Group {} specified multiple times")
            gdb = Group(name=g.name)
            gdb.start = g.start
            gdb.stop = g.stop
            gdb.per_user_time = g.per_user_time
            self.groupsdb[g.name] = gdb
            cdb.groups.append(gdb)

        cdb.main_group = self.groupsdb[self.defaultgroup.name]

        self.usersdb = {}

        self.cdb = cdb

        return cdb

    @property
    def testuser(self):
        return self._makeuser(self._mytestuser.username)

    def _makeuser(self, username):
        """
        Return a User object for the specified user which can be saved
        to the database.

        username (unicode): the name of the user to generate

        return (User): database object for the user

        """
        if username in self.usersdb:
            return self.usersdb[username]

        for user in self.users:  # FIXME This could be done faster...
            if user.username == username:
                if isinstance(user.primary_statements, list):
                    primary_statements = {t.name: user.primary_statements
                                          for t in self.tasks}
                else:
                    primary_statements = user.primary_statements
                udb = User(username=user.username,
                           password=user.password,
                           first_name=user.firstname,
                           last_name=user.lastname,
                           ip=user.ip,
                           hidden=user.hidden,
                           group=self.groupsdb[user.group.name],
                           timezone=user.timezone,
                           primary_statements=json.dumps(primary_statements))
                self.usersdb[username] = udb
                return udb
        raise KeyError

    def _maketask(self, file_cacher, taskname, local_test=False):
        """
        Return a Task object for the specified task which can be saved
        to the database.

        file_cacher (FileCacher): for saving files (test cases,
                                  attachments, ...)

        taskname (unicode): name of the task to create

        local_test (bool|string): specifies which submissions should be tested
                                  locally (cf. MySubmission.should_test)

        """
        for task in self.tasks:  # FIXME This could be done faster...
            if task.name == taskname:
                tdb = task._makedbobject(file_cacher, local_test)
                return tdb
        raise KeyError

    def _makedataset(self, file_cacher, taskname):
        for task in self.tasks:  # FIXME This could be done faster...
            if task.name == taskname:
                tdb = task._makedataset(file_cacher)
                return tdb
        raise KeyError
