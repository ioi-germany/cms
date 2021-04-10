#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2021 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2016 Fabian Gundlach <320pointsguy@gmail.com>
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

from cmscontrib.gerpythonformat.Messenger import print_msg, box, yellow
from cmscontrib.gerpythonformat.CommonConfig import exported_function, CommonConfig
from cmscontrib.gerpythonformat.TaskConfig import TaskConfig
from cmscontrib.gerpythonformat.LocationStack import chdir
from cms.db import Contest, User, Group, Participation, Team
from cmscommon.crypto import build_password
from cmscommon.constants import SCORE_MODE_MAX_TOKENED_LAST, \
    SCORE_MODE_MAX, SCORE_MODE_MAX_SUBTASK

import copy
import os
import shutil
from datetime import datetime, timedelta
from importlib import import_module
import pytz


class MyGroup(object):
    def __init__(self, name, start, stop, analysis_start, analysis_stop, per_user_time):
        self.name = name
        self.start = start
        self.stop = stop
        self.analysis_start = analysis_start
        self.analysis_stop = analysis_stop
        self.per_user_time = per_user_time


class MyTeam(object):
    def __init__(self, code, name, primary_statements):
        self.code = code
        self.name = name
        self.primary_statements = copy.deepcopy(primary_statements)


class TeamContext(object):
    def __init__(self, contest, team):
        self.contest = contest
        self.team = team

    def __enter__(self):
        self.prev_team = self.contest._current_team
        self.contest._current_team = self.team
        return self.team

    def __exit__(self, *args):
        self.contest._current_team = self.prev_team


class MyUser(object):
    def __init__(self, username, password, group, firstname, lastname,
                 ip, hidden, unrestricted, timezone, primary_statements, team):
        self.username = username
        self.password = password
        self.group = group
        self.firstname = firstname
        self.lastname = lastname
        self.ip = ip
        self.hidden = hidden
        self.unrestricted = unrestricted
        self.timezone = timezone
        self.primary_statements = primary_statements
        self.team = team


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
    no_feedback = ("no", True)
    partial_feedback = ("partial", True)
    full_feedback = ("full", True)
    restricted_feedback = ("full", False)


    def __init__(self, rules, name, ignore_latex=False, relevant_language=None, onlytask=None,
                 minimal=False, safe_latex=False):
        """
        Initialize.

        rules (string): directory for rules persistency

        name (string): (short) contest name

        onlytask (string): if specified, then every task except the task with
                           this name is ignored

        """
        super(ContestConfig, self).__init__(rules, ignore_latex=ignore_latex,
                                            relevant_language=relevant_language,
                                            safe_latex=safe_latex)
        self.infinite_tokens()

        self.onlytask = onlytask

        self.contestname = name

        self._allowed_localizations = []
        # FIXME If we don't allow Java submissions, all Java test submissions
        # will fail (even locally) since multithreading is not allowed.
        self._languages = ["C++17 / g++"]

        self.tasks = {}

        self.groups = {}
        self.defaultgroup = None
        self.teams = {}
        self._current_team = MyTeam("unaffiliated", "unaffiliated", [])
        self.teams["unaffiliated"] = self._current_team
        self.users = {}

        # Export variables
        self.exported["contest"] = self
        self.exported["no_feedback"] = self.no_feedback
        self.exported["partial_feedback"] = self.partial_feedback
        self.exported["full_feedback"] = self.full_feedback
        self.exported["restricted_feedback"] = self.restricted_feedback
        self.exported["token_feedback"] = self._token_feedback
        self.exported["std_token_feedback"] = self._token_feedback(3, 2)
        self.exported["score_max"] = SCORE_MODE_MAX
        self.exported["score_max_subtask"] = SCORE_MODE_MAX_SUBTASK
        self.exported["score_max_tokened_last"] = SCORE_MODE_MAX_TOKENED_LAST

        # Default submission limits
        self.submission_limits(None, None)
        self.user_test_limits(None, None)

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

        self.minimal = minimal

    def _readconfig(self, filename):
        if not self.minimal:
            print_msg("Loading contest {}".format(self.contestname),
                      headerdepth=1)

        super(ContestConfig, self)._readconfig(filename)
        self._initialize_ranking()

    def finish(self):
        asy_cnt = self.asy_warnings + sum(t.asy_warnings
                                  for t in self.tasks.values())

        if asy_cnt != 0:
            box(" WARNING ", yellow("You compiled %d Asymptote file(s)."
                                        % asy_cnt) + "\n" +
                yellow("However, Asymptote support will be removed") + "\n" +
                yellow("from our task format in the near future") + "\n" +
                yellow("Please consider using TikZ for pictures."),
                double=True)

    def _token_feedback(self, gen_initial, gen_number,
                        gen_interval=timedelta(minutes=30), gen_max=None,
                        min_interval=timedelta(), max_number=None,
                        all_cases=True):
        """
        Specify the number of tokens available.

        initial (int): number of tokens at the beginning of the contest

        gen_number (int): number of tokens to generate each time

        gen_time (timedelta): how often new tokens are generated

        max (int): limit for the number of tokens at any time

        min_interval (timedelta): time the user has to wait after using a
                                  token before he can use another token

        total (int): maximum number of tokens the user can use in total

        all_cases (boolean): should we show the results of all cases?
                             (as opposed to restricted feedback)

        """
        return ("token", all_cases, gen_initial, gen_number, gen_interval,
                gen_max, min_interval, max_number)

    @exported_function
    def load_template(self, name, **kwargs):
        """
        Load the template of the given name
        """
        tm = import_module("cmscontrib.gerpythonformat.templates." + name)
        tm.load(self, **kwargs)

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

        timezone (string): time zone to convert from (by default the contest
                           time zone)

        return (string): string representing the time in UTC

        """
        if timezone is None:
            timezone = self._timezone
        time = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        tz = pytz.timezone(timezone)
        convtime = tz.normalize(tz.localize(time)).astimezone(pytz.utc)
        return convtime.replace(tzinfo=None)

    @exported_function
    def description(self, s):
        """
        Set the contest description.

        s (unicode): contest description

        """
        if not self.minimal:
            print_msg("Setting description to {}".format(s), headerdepth=10)
        self._description = s

    @exported_function
    def timezone(self, s):
        """
        Set the contest time zone.

        s (unicode): contest time zone (e.g. Europe/Berlin)

        """
        if not self.minimal:
            print_msg("Setting timezone to {}".format(s), headerdepth=10)
        self._timezone = s

    @exported_function
    def allowed_localizations(self, localizations):
        """
        Set the allowed web interface localizations. By default, all
        localizations are allowed.

        localizations (string[]): list of localization names

        """
        self._allowed_localizations = localizations

    @exported_function
    def languages(self, languages):
        """
        Set the allowed programming languages.

        languages (string[]): list of languages
        """
        self._languages = languages

    @exported_function
    def allow_usual_languages(self):
        self.languages(self._usual_languages())

    @exported_function
    def user_group(self, s, start, stop, analysis_start=None, analysis_stop=None, per_user_time=None):
        """
        Create a user group.

        s (unicode): user group name;
                     if the group is called "main", it is assumed to be the
                     default group.

        start (string): start time (should be created via a call to time())

        stop (string): stop time (should be created via a call to time())

        analysis_start (string): enable analysis with this start time (should be created via a call to time())

        analysis_stop (string): enable analysis with this stop time (should be created via a call to time())

        per_user_time (timedelta): enable USACO mode with this time per user;
            see :ref:`configuringacontest_usaco-like-contests`

        return (MyGroup): object representing the created group

        """
        if s in self.groups:
            raise Exception("Group {} specified multiple times".format(s))

        if self.minimal:
            return

        if (analysis_start is None) ^ (analysis_stop is None):
            raise Exception("Analysis start and stop time can only be used together")

        usaco_mode_str = ""
        if per_user_time is not None:
            usaco_mode_str = \
                " in USACO mode with time {}".format(per_user_time)
        analysis_mode_str = ""
        if analysis_start is not None:
            analysis_mode_str = \
                ", analysing from {} to {}".format(analysis_start,analysis_stop)
        print_msg("Creating user group {} (working from {} to {}{}{})"
                  .format(s, start, stop, usaco_mode_str, analysis_mode_str), headerdepth=10)

        # We allow specifying an integer or a timedelta
        try:
            per_user_time = per_user_time.seconds
        except AttributeError:
            pass

        self.groups[s] = r = MyGroup(s, start, stop, analysis_start, analysis_stop, per_user_time)
        if s == "main":
            self.defaultgroup = r
        return r

    @exported_function
    def team(self, code, name, primary_statements=[]):
        """
        Add a team (currently only used to generate a RWS directory).

        code (unicode): a short name (used to find the flag)

        name (unicode): a longer name (displayed in RWS)

        primary_statements (string[]): list of standard task languages for this
                                       team (can be overwritten for individual
                                       users)

        return (MyTeam): object representing the created team

        """
        if code in self.teams:
            raise Exception("Team {} specified multiple times".format(code))
        self.teams[code] = team = MyTeam(code, name, primary_statements)
        return TeamContext(self, team)

    @exported_function
    def user(self, username, password, firstname, lastname, group=None,
             ip=None, hidden=False, unrestricted=False, timezone=None,
             primary_statements=None, team=None):
        """
        Add a user participating in this contest.

        username (unicode): user name (for login)

        password (unicode): password used both for the user and for the
                            participation

        firstname (unicode): first name

        lastname (unicode): last name

        group (MyGroup): the group to add this user to (by default the
                         default group, which is usually called main)

        ip (unicode): ip address the user must log in from (if this feature
                      is enabled in CMS)

        hidden (bool): whether this user is hidden (not shown on the official
                       scoreboard)

        unrestricted (bool): whether this user is unrestricted (can submit at
                             any time)

        timezone (unicode): time zone for this user (if different from contest
                            time zone)

        primary_statements (string[] or None): the list of standard task
                                               languages for this user (if None,
                                               the languages for the
                                               corresponding team will be used)

        team (string or MyTeam): (name of) the team the user belongs to

        return (MyUser): object representing the created user

        """
        if self.minimal:
            return

        team = team or self._current_team
        if not isinstance(team, MyTeam):
            team = self.teams[team]
        primary_statements = primary_statements or team.primary_statements

        if username in self.users:
            raise Exception(
                "User {} specified multiple times".format(username))
        if group is None:
            if self.defaultgroup is None:
                raise Exception("You have to specify a group")
            group = self.defaultgroup

        print_msg("Adding user {} to group {}".format(username, group.name),
                  headerdepth=10)
        self.users[username] = user = \
            MyUser(username, password, group,
                   firstname, lastname,
                   ip, hidden, unrestricted, timezone, primary_statements[:],
                   team)
        return user

    def _task(self, s, feedback, score_mode, minimal, standalone_task=False):
        """
        Add a task to this contest (full version, not accessible from
        config.py).

        s (unicode): task name; the task description has to reside in the
                     folder with the same name
        feedback:    type of feedback (one of the variables no_feedback,
                     partial_feedback, full_feedback, restricted_feedback)
        score_mode:  how to calculate the final score (one of SCORE_MODE_MAX,
                     SCORE_MODE_MAX_SUBTASK, SCORE_MODE_MAX_TOKENED_LAST)
        minimal (bool): only try to compile statement?

        """
        # Check if this task should be ignored
        if self.onlytask is not None and self.onlytask != s:
            return

        if not os.path.isdir(s):
            raise Exception("No directory found for task {}".format(s))

        if s in self.tasks:
            raise Exception("Task {} specified multiple times".format(s))

        with chdir(s):
            if not os.path.isfile("config.py"):
                raise Exception("Couldn't find task config file. Make sure it "
                                "is named 'config.py' and located on the "
                                "topmost level of the folder {}"
                                .format(os.getcwd()))

            with TaskConfig(self, os.path.abspath(".rules"),
                            s, len(self.tasks),
                            feedback, score_mode,
                            ignore_latex=self.ignore_latex,
                            relevant_language=self.relevant_language,
                            minimal=minimal,
                            standalone_task=standalone_task) as taskconfig:
                for f in self.ontasks:
                    f(taskconfig)
                taskconfig._readconfig("config.py")
                taskconfig._printresult()
                self.tasks[s] = taskconfig

            if minimal:
                print_msg("Statement for task {} generated successfully".
                          format(s), success=True)
            else:
                print_msg("Task {} loaded completely".format(s), success=True)

    @exported_function
    def task(self, s, feedback=None, score_mode=None):
        """
        Add a task to this contest (version accessible from config.py).

        s (unicode): task name; the task description has to reside in the
                     folder with the same name
        feedback:    type of feedback (one of the variables no_feedback,
                     partial_feedback, full_feedback, restricted_feedback)

        """
        self._task(s, feedback or self.restricted_feedback, score_mode, False)

    @exported_function
    def test_user(self, u):
        """
        Set the user to submit unit tests as.

        u (MyUser): test user

        """
        self._mytestuser = u

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
        cdb.allowed_localizations = self._allowed_localizations
        cdb.languages = self._languages
        self._set_tokens(cdb)
        cdb.max_submission_number = self.max_submission_number
        cdb.min_submission_interval = self.min_submission_interval
        cdb.max_user_test_number = self.max_user_test_number
        cdb.min_user_test_interval = self.min_user_test_interval

        self.usersdb = {}
        self.participationsdb = {}

        self.cdb = cdb

        gdbs = {}
        for g in self.groups:
            gdbs[g] = self._makegroup(g, cdb)
        cdb.main_group = gdbs[self.defaultgroup.name]

        return cdb

    def _makegroup(self, groupname, cdb):
        group = self.groups[groupname]
        gdb = Group(name=groupname)
        gdb.contest = cdb
        gdb.start = group.start
        gdb.stop = group.stop
        gdb.analysis_enabled = group.analysis_start is not None
        if gdb.analysis_enabled:
            gdb.analysis_start = group.analysis_start
            gdb.analysis_stop = group.analysis_stop
        gdb.per_user_time = None if group.per_user_time is None else \
            timedelta(seconds=group.per_user_time)
        return gdb

    def _maketeam(self, teamname):
        team = self.teams[teamname]

        teamdb = Team(code=team.code,
                      name=team.name)

        return teamdb

    def _makeuser(self, username):
        """
        Return a User object for the specified user which can be saved
        to the database.

        username (unicode): the name of the user to generate

        return (User,Participation): database object for the user

        """
        user = self.users[username]

        # The user should never actually use this password, because we set
        # different passwords for each participation.
        udb = User(username=user.username,
                   first_name=user.firstname,
                   last_name=user.lastname,
                   password=build_password(user.password))

        udb.timezone = user.timezone
        udb.preferred_languages = user.primary_statements

        return udb

    def _makeparticipation(self, username, cdb, udb, gdb, teamdb):
        user = self.users[username]

        pdb = Participation(user=udb, contest=cdb)

        pdb.password = build_password(user.password)
        pdb.group = gdb

        pdb.ip = user.ip
        pdb.hidden = user.hidden
        pdb.unrestricted = user.unrestricted

        pdb.team = teamdb

        return pdb

    def _initialize_ranking(self):
        directory = os.path.join(self.wdir, "ranking_conf")
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.mkdir(directory)
        for d in ["flags", "faces"]:
            dd = os.path.join(directory, d)
            os.mkdir(dd)

        def copy_ranking_file(basename, target_basename):
            for ext in [".png", ".jpg", ".gif", ".bmp"]:
                origin = os.path.join(self.wdir, basename + ext)
                target = os.path.join(directory, target_basename + ext)
                if os.path.exists(origin):
                    shutil.copyfile(origin, target)
                    return

        copy_ranking_file("logo", "logo")

        for team in self.teams.values():
            copy_ranking_file("flag-" + team.code,
                              os.path.join("flags", team.code))

        for user in self.users.values():
            if not user.hidden:
                copy_ranking_file("face-" + user.username,
                                  os.path.join("faces", user.username))
