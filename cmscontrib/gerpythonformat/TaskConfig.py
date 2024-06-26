#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2023 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2022 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2022 Manuel Gundlach <manuel.gundlach@gmail.com>
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

from cmscontrib.gerpythonformat.Messenger import print_msg, print_block, \
    header, red, green, gray, yellow, blue, lightgreen, orange, purple, bold, \
    box, side_by_side, pad_left, add_line_breaks, \
    remaining_line_length, indent, IndentManager
from cmscontrib.gerpythonformat.CommonConfig import exported_function, \
    CommonConfig
from cmscontrib.gerpythonformat.Executable import ExitCodeException, \
    InternalPython, CPPProgram
from cmscontrib.gerpythonformat.ConstraintParser import ConstraintList, \
    merge_constraints, read_frequency, check_bounds
from cmscommon.constants import SCORE_MODE_MAX_TOKENED_LAST, \
    SCORE_MODE_MAX, SCORE_MODE_MAX_SUBTASK
from cms import FEEDBACK_LEVEL_FULL, FEEDBACK_LEVEL_RESTRICTED
from cms.db import Task, Statement, Testcase, Dataset, \
    Attachment, Spoiler, Manager, Submission, File, \
    SubmissionResult
from cms.grading.tasktypes import get_task_type, Communication
from cms.grading.languagemanager import filename_to_language, get_language
from cms.grading.Job import CompilationJob, EvaluationJob
from cms.rules.Rule import JobRule, ZipRule
from cms.service.esoperations import ESOperation
from datetime import datetime
import json
import os
import shutil

from six import iteritems, iterkeys
from textwrap import wrap


class Scope(object):
    """
    Base class for tasks, subtasks and groups.
    """

    def __init__(self, upscope=None):
        self.upscope = upscope
        self.checkers = []
        self.constraints = []
        self.special_cases = []
        if upscope is None:
            self.task = self
        else:
            self.task = upscope.task

    def _get_checkers(self):
        res = list(self.checkers)
        if self.upscope is not None:
            res += self.upscope._get_checkers()
        return res

    def _get_constraints(self):
        res = []
        if self.upscope is not None:
            res += self.upscope._get_constraints()
        res += self.constraints
        return res

    def __get_special_cases(self):
        res = []

        if self.upscope is not None:
            res += self.upscope.__get_special_cases()
        res += self.special_cases
        return res

    def _get_special_cases(self):
        L = self.__get_special_cases()

        return [x for x, y in L if y == ConstraintList.ALWAYS], \
               [(x, read_frequency(y)) for x, y in L
                                       if y != ConstraintList.ALWAYS]

    def add_checker(self, p):
        """
        Register a test case checker for this task, subtask or group.

        p (Executable): the checker (should raise an ExitCodeException if
                        the test case is invalid)

        """
        print_msg("Adding checker {}".format(p), headerdepth=10)
        self.checkers.append(p)

    def add_constraint(self, s, silent=None, frequency=ConstraintList.ALWAYS):
        """
        Add a constraint for this task, subtask or group.
        The constraint format is described in the docs
        """

        if silent is None:
            silent = (isinstance(self, MyGroup)
                      or (isinstance(self, MySubtask) and self.sample)
                      or frequency != ConstraintList.ALWAYS)

        self.constraints.append(ConstraintList.parse(s, silent, frequency))

    def add_special_case(self, descr, frequency):
        """
        Add a special case for this task, subtask or group.
        This is just a string that will be passed to the checker
        """

        self.special_cases.append((descr, frequency))

    def _collect_constraints(self):
        hard = {}
        soft = []

        for c in self._get_constraints():
            if c.soft:
                soft.append(c)
            else:
                hard = merge_constraints(hard, c.uncompress())

        return hard, soft


class MySubtask(Scope):
    """
    :ivar description: Decription of this subtask
    :ivar name: Internal (short) name of this subtask
    :ivar sample: Whether this is the sample test case subtask
    :ivar foldername: We create a directory with symlinks to cases
                      at subtasks/foldername.
    :ivar groups: Groups contained in this subtask
    :ivar scorestyle: score style (for multiscoring)
    """

    def __init__(self, task, description, name, sample, foldername, scorestyle,
                 individual):
        super(MySubtask, self).__init__(task)
        self.task = task
        self.description = description
        self.name = name
        self.sample = sample
        self.foldername = foldername
        self.groups = []
        self.feedbackcases = []
        self.checkers = []
        self.scorestyle = scorestyle
        self.individual = individual
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)

    def __enter__(self):
        self.indenter = header("Subtask {}".format(self.description),
                               depth=3)
        self.indenter.start()

        self.task.subtask_stack.append(self)
        return self

    def __exit__(self, type, value, traceback):
        self.indenter.stop()
        self.task.subtask_stack.pop()

    @property
    def unique_name(self):
        return (self.name,)

    @property
    def directory(self):
        """
        The path of the directory containing the groups for
        this subtask.
        """
        return os.path.join(self.task.wdir, "subtasks", self.foldername)

    def group(self, points, name=None, scorestyle=0):
        """
        Specify the start of a new test case group (part of a subtask).

        points (int): maximum number of points for this test case group;
                      the number of points awarded for a test case group is
                      points * (minimal outcome for test cases in this group)

        scorestyle (int): score style (for multiscoring)

        name (string): name of this group; the group object will be accessible
                       as an attribute with this name of the subtask object;
                       the subtask should not have a field with this name
                       before (e.g. do not call a group "group" or
                       "put_feedback");
                       by default, we take gNR where NR is the index of this
                       group (starting at 0)

        return (MyGroup): object representing the created group

        """
        if name is None:
            name = "g" + str(len(self.groups))

        foldername = "Group_" + str(len(self.groups)+1)
        group = MyGroup(self.task, self, points, name, foldername, scorestyle)

        self.groups.append(group)

        if hasattr(self, name):
            raise Exception("The subtask '{}' already has an attribute "
                            "called '{}'".format(self.name, name))
        setattr(self, name, group)

        return group

    def _get_cases(self):
        """
        Utility method for being able to find the test cases contained in a
        task, subtask, group or test case.

        return (list): list of test cases

        """
        return [c for g in self.groups for c in g._get_cases()]

    def _level(self):
        return 1

    def max_score(self):
        return sum(g.points for g in self.groups)

    def scoreinfo(self):
        def mystr(f):
            i = int(f + .5)
            assert abs(i - f) < 1e-4
            return "{}".format(i)

        if self.individual:
            return " + ".join(mystr(g.points) for g in self.groups)
        else:
            return mystr(self.max_score())



class MyGroup(Scope):
    """
    :ivar subtask: The subtask this group belongs to
    :ivar points: Maximum number of points for this subtask
    :ivar name: Internal (short) name of this group
    :ivar foldername: We create a directory with symlinks to cases
                      at subtasks/.../foldername.
    :ivar cases: Test cases contained in this group
    :ivar scorestyle: score style (for multiscoring)
    """

    def __init__(self, task, subtask, points, name, foldername, scorestyle):
        super(MyGroup, self).__init__(subtask)
        self.task = task
        self.subtask = subtask
        self.points = points
        self.name = name
        self.foldername = foldername
        # List of test cases in this group
        self.cases = []
        self.cases_set = set()
        # List of bools specifying for each test case whether it contributes to
        # partial feedback.
        self.feedback = []
        # how often is each soft constraint satisfied in this group?
        self.soft_constraints_stats = []
        self.soft_constraints_stats_acc = []
        self.soft_spec_stats = {}
        self.scorestyle = scorestyle

        if not os.path.exists(self.directory):
            os.mkdir(self.directory)

    def __enter__(self):
        self.indenter = header("Group {} ({} points)".format(self.name,
                                                             self.points),
                               depth=4)
        self.indenter.start()
        self.task.group_stack.append(self)
        return self

    @property
    def soft_constraints(self):
        return self._collect_constraints()[1]

    @property
    def soft_special_cases(self):
        return self._get_special_cases()[1]

    def _print_stats(self, exception):
        if len(self.soft_constraints) == 0 and \
           len(self.soft_special_cases) == 0:
            return

        if exception is not None:
            print_msg(gray("(There was an exception, so I won't collect "
                           "testcase quality statistics for this group)"),
                      use_ellipsis=False)
            return

        def format_bounds(min, max):
            if min is None:
                return "≤ {} times".format(max)
            elif max is None:
                return "≥ {} times".format(min)
            else:
                return "{}–{} times".format(min, max)

        failed = False

        def print_stats_for(desc, stats, bounds, what):
            nonlocal failed

            lower, upper = bounds
            times_satisfied = sum(a[0] for a in stats if a[0] is not None)
            this_constraint_okay = check_bounds(times_satisfied, lower, upper)

            def cf(f):
                return green if this_constraint_okay else f

            def sym(x):
                if x is None:
                    return "·"
                elif x:
                    return "●"
                else:
                    return "○"

            bars = "".join(cf(a[1])(sym(a[0])) for a in stats)
            bars = " ".join(wrap(bars, 5 * len(green("○"))))

            msg_long = "satisfied {} times, expected {}".\
                format(times_satisfied, format_bounds(lower, upper))

            if this_constraint_okay:
                msg = green(bold("OKAY"))
                msg_long = green(msg_long)
            else:
                msg = red(bold("FAIL"))
                msg_long = red(msg_long)
                failed = True

            space = remaining_line_length() - 20 - len(desc)
            print_msg("─── " + desc + " " + (space - 2) * "─" + " " + msg +
                      " ──────────")
            with IndentManager():
                print_msg(bars, use_ellipsis=False)
                print_msg(msg_long, use_ellipsis=False)

                if any(a[0] is None for a in stats):
                    print_msg("This soft " + what + " was only specified "
                              "after some cases had already been checked—are "
                              "you sure this is what you want?",
                              use_ellipsis=False)

        print_msg(bold("\nTestcase quality in this group"))

        if len(self.soft_constraints) > len(self.soft_constraints_stats):
            print_msg(yellow(bold("You specified some soft constraints "
                                  "(see the list below for details) "
                                  "after all testcases had already been "
                                  "added—why?!")), use_ellipsis=False)

            for i in range(len(self.soft_constraints),
                           len(self.soft_constraints_stats)):
                self.soft_constraints_stats.append([])

                with IndentManager():
                    print_msg(self.soft_constraints[i].terminal())

        for stats, c in zip(self.soft_constraints_stats_acc,
                            self.soft_constraints):
            print_stats_for(c.terminal(), stats, c.how_often, "constraint")

        special_cases_after = [desc for desc, _ in self.soft_special_cases
                                    if desc not in self.soft_spec_stats]

        if len(special_cases_after) > 0:
            print_msg(yellow(bold("You specified some soft special cases "
                                  "(see the list below for details) "
                                  "after all testcases had already been "
                                  "added—why?!")), use_ellipsis=False)

            with IndentManager():
                for s in special_cases_after:
                    print_msg(s)

        for desc, bounds in self.soft_special_cases:
            if desc not in self.soft_spec_stats:
                continue

            stats = self.soft_spec_stats[desc]
            print_stats_for(desc, stats, (bounds[0], bounds[1]), "special case")

        if failed:
            raise Exception("at least one testcase quality check failed")
        else:
            print_msg(green(bold("...all shall be well\n")))

    def __exit__(self, type, value, traceback):
        self._print_stats(type)

        self.indenter.stop()
        self.task.group_stack.pop()

    @property
    def unique_name(self):
        return self.subtask.unique_name + (self.name,)

    @property
    def directory(self):
        """
        The path of the directory containing the links to the test cases
        contained in this group.
        """
        return os.path.join(self.subtask.directory, self.foldername)

    def _dummy_case(self, name):
        if name is None:
            name = "t" + str(len(self.cases))

        setattr(self, name, None)
        self.cases.append(None)

    @exported_function
    def add_testcase(self, case, feedback=False, save=False, name=None,
                     must_still_be_checked=True):
        """
        Add a previously generated test case to the current test case group.
        The testcase will be checked with the current test case checkers.

        case (MyCase): the test case to add

        feedback (bool): whether this test case should be marked for detailed
                         feedback inside this subtask

        save (bool): TODO

        name (string): name of this test case; the test case object will be
                       accessible as an attribute with this name of the group
                       object;
                       the group should not have a field with this name
                       before;
                       by default, we take gNR where NR is the index of this
                       test case (starting at 0)

        """
        if case in self.cases_set:
            # This case has already been added to the group. We don't add it
            # a second time.
            # With restricted feedback, contestants would see the exact same
            # thing whether we add the test case or not. With full feedback
            # they would otherwise see the test case multiple times in
            # different places.
            return

        self.task.current_group = self
        checkers = self._get_checkers()
        if len(checkers) == 0 and must_still_be_checked:
            self.task.everything_checked = False

        soft_results = None

        for i, checker in enumerate(checkers):
            curr = self.task._check(checker, case.infile, case.outfile,
                                    case.codename, i + 1)

            if curr:
                if soft_results:
                    # TODO: should we relax this condition?
                    raise Exception("only one checker may check (soft) "
                                    "constraints")
                soft_results = curr

        soft_results = soft_results or [{}, {}]
        soft_con_results, soft_spec_results = tuple(soft_results)

        def getcolor(result, lower, upper):
            mycolor = blue
            if lower is not None and upper is None:
                mycolor = green if result else yellow
            if lower is None and upper is not None:
                mycolor = yellow if result else green
            return mycolor

        """
        for var in self.soft_constraints:
            if var not in self.soft_constraints_stats:
                self.soft_constraints_stats[var] = []

            for i, (bounds, result) in enumerate(zip(self.soft_constraints[var],
                                                     soft_con_results[var])):
                desc = format_constraint(var, bounds[0], bounds[1])
                mycolor = getcolor(result, bounds[2], bounds[3])

                print_msg(bold(mycolor(desc + ": " +
                                       ("✗ not " if not result else "✓ ") +
                                       "satisfied")))

                while i >= len(self.soft_constraints_stats[var]):
                    self.soft_constraints_stats[var].append([(None, gray)] *
                                                            len(self.cases))

                self.soft_constraints_stats[var][i].append((result, mycolor))

        """
        for i, con_list in enumerate(self.soft_constraints):
            while i >= len(self.soft_constraints_stats):
                self.soft_constraints_stats.append([])
                self.soft_constraints_stats_acc.\
                    append([(None, gray)] * len(self.cases))

            lower, upper = con_list.how_often
            desc = con_list.terminal()
            results = [res for L in soft_con_results[i] for res in L]
            results_acc = all(results)
            mycolor = getcolor(results_acc, lower, upper)
            print_msg(mycolor(bold(desc + ": " + ("✗ not " if not results_acc
                                                  else "✓ ") + "satisfied")))

            for j, con in enumerate(con_list.constraints):
                while j >= len(self.soft_constraints_stats[i]):
                    self.soft_constraints_stats[i].append([])

                for k, var in enumerate(con.variables):
                    result = soft_con_results[i][j][k]
                    # mycolor = getcolor(result, lower, upper)

                    if len(results) > 1:
                        with IndentManager():
                            print_msg(mycolor(con.subconstraint(k).terminal() +
                                              ": " + ("✗ not " if not result
                                                               else "✓ ") +
                                              "satisfied"))

                    while k >= len(self.soft_constraints_stats[i][j]):
                        self.soft_constraints_stats[i][j].\
                            append([(None, gray)] * len(self.cases))

                    self.soft_constraints_stats[i][j][k].\
                        append((result, mycolor))

            print_msg("")
            self.soft_constraints_stats_acc[i].append((results_acc, mycolor))

        for desc, bounds in self.soft_special_cases:
            result = soft_spec_results[desc]
            mycolor = getcolor(result, bounds[0], bounds[1])

            print_msg(bold(mycolor(desc + ": " +
                                   ("✗ not " if not result else "✓ ") +
                                   "satisfied")))

            if desc not in self.soft_spec_stats:
                self.soft_spec_stats[desc] = [(None, gray)] * len(self.cases)
            self.soft_spec_stats[desc].append((result, mycolor))

        self.task.current_group = None

        if name is None:
            name = "t" + str(len(self.cases))
        if hasattr(self, name):
            raise Exception(
                "The group '{}.{}' already has an attribute called '{}'"
                .format(self.subtask, self.name, name))
        setattr(self, name, case)

        dirname = "Case_" + str(len(self.cases)+1)
        linkname = os.path.join(self.directory, dirname)
        if os.path.lexists(linkname):
            os.remove(linkname)
        rel = os.path.relpath(case.directory, self.directory)
        os.symlink(rel, linkname)

        print_msg("Added test case {} ({})".format(case.codename, name))

        self.cases.append(case)
        self.cases_set.add(case)

        self.feedback.append(feedback)

        if save:
            self.task.saved.append(case)

        case.locations.append(self.subtask.name + "." + self.name + "." + name)

    @exported_function
    def testcase(self, prog, *args, **kwargs):
        """
        Generate and add a testcase to this group.

        This is a convenience function calling make_testcase(prog)
        and add_testcase(args, kwargs).
        """
        case = self.task.make_testcase(prog)

        self.add_testcase(case, *args, **kwargs)
        return case

    def _get_cases(self):
        """
        Utility method for being able to find the test cases contained in a
        subtask, group or test case.

        return (list): list of test cases

        """
        return self.cases

    def _level(self):
        return 2


class MultiGroupProxy(object):
    def __init__(self, g, L):
        self.g = g
        self.L = L

    def __enter__(self):
        return self.g.__enter__()

    def __exit__(self, *args):
        self.g.__exit__(*args)

        for x in args:
            if x is not None:
                return

        t = self.g.task
        n = self.g.name
        s = self.g.scorestyle

        for i, p in enumerate(self.L):
            with t.group(p, name=n + "##" + str(i + 1), scorestyle=s + i + 1):
                t.subsume_group(n)


class MyCase(object):
    """
    :ivar codename: The code name of this test case (usually a four-digit
                    number).

    """

    def __init__(self, task, codename, hashname):
        self.task = task
        self.codename = codename
        self.hashname = hashname
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)
        self._create_link()
        self.public = False
        # Strings specifying in which subtasks/groups this case can be found
        self.locations = []

    @property
    def directory(self):
        """
        The path (ending with a hash) of the directory containing the input
        and output files for this test case.
        """
        return os.path.join(self.task.cases_directory, self.hashname)

    @property
    def infile(self):
        """
        The input file name.
        """
        return os.path.join(self.directory, "in.txt")

    @property
    def outfile(self):
        """
        The output file name.
        """
        return os.path.join(self.directory, "out.txt")

    @property
    def codenameddirectory(self):
        """
        The path (ending with a number, which is the codename) of the link to
        the directory containing the input and output files for this test case.
        """
        return os.path.join(self.task.wdir, "cases", self.codename)

    def _create_link(self):
        """
        Create the link from the codename to the hash name directory.
        """
        if os.path.lexists(self.codenameddirectory):
            try:
                os.remove(self.codenameddirectory)
            except IsADirectoryError:
                os.rmdir(self.codenameddirectory)
        rel = os.path.relpath(self.directory, os.path.join(self.task.wdir, "cases"))
        os.symlink(rel, self.codenameddirectory)

    def _get_cases(self):
        """
        Utility method for being able to find the test cases contained in a
        subtask, group or test case.

        return (list): list of test cases

        """
        return [self]

    def _level(self):
        return 3

    def __str__(self):
        return "{} ({})".format(self.codename, " ".join(self.locations))


class MySubmission(object):
    def __init__(self, task, filenames, score, sample_score,
                 partial_feedback_score=None,
                 expected={},
                 weak_time_limit=None, strong_time_limit=None,
                 weak_mem_limit=None, strong_mem_limit=None):
        self.task = task
        self.filenames = filenames
        self.score = MySubmission.score_machine_readable(score)
        self.score_info = MySubmission.score_human_readable(score)
        self.sample_score = MySubmission.score_machine_readable(sample_score)
        self.sample_score_info = MySubmission.score_human_readable(sample_score)
        # By default, we assume that the partial feedback score equals the
        # final score.
        if partial_feedback_score is None:
            partial_feedback_score = score
        self.partial_feedback_score = MySubmission.score_machine_readable(partial_feedback_score)
        self.partial_feedback_score_info = MySubmission.score_human_readable(partial_feedback_score)

        if weak_time_limit is None:
            weak_time_limit = task.weak_time_limit
        self.weak_time_limit = weak_time_limit
        if strong_time_limit is None:
            strong_time_limit = task.strong_time_limit
        self.strong_time_limit = strong_time_limit
        if weak_mem_limit is None:
            weak_mem_limit = task.weak_mem_limit
        self.weak_mem_limit = weak_mem_limit
        if strong_mem_limit is None:
            strong_mem_limit = task.strong_mem_limit
        self.strong_mem_limit = strong_mem_limit
        if strong_time_limit > 1 or weak_time_limit < 1 \
                or strong_mem_limit > 1 or weak_mem_limit < 1:
            raise Exception(
                "Weird limits for unit test; strong limits should be <= 1 "
                "and weak limits should be >= 1")
        self.expected = expected

        keywords = {"arbitrary": ["arbitrary"],
                    "time":      ["time"],
                    "memory":    ["memory"],
                    "time?":     ["time?"],
                    "memory?":   ["memory?"],
                    "wrong":     [MySubmission.score_machine_readable(0.0)],
                    "fail":      ["time", "memory",
                                  MySubmission.score_machine_readable(0.0)],
                    "resources": ["time", "memory"]}

        def encode(key):
            try:
                return keywords[key]
            except KeyError:
                return [MySubmission.score_machine_readable(json.loads(key))]

        # Check if the expected make sense
        for k in self.expected:
            try:
                encode(k)
            except:
                raise Exception("Unknown expected result '{}'".format(k))

        self.expectations = {(): []}

        for s in self.task.subtasks:
            self.expectations[s.unique_name] = []

            for g in s.groups:
                self.expectations[g.unique_name] = []

        self.case_expectations = {}

        for c in self.task.cases:
            self.case_expectations[c.codename] = []

        def encode(key):
            try:
                return keywords[key]
            except KeyError:
                return [MySubmission.score_machine_readable(json.loads(key))]

        # Convert the given lists of expected events to something more
        # readable for ScoreTypes
        for key, items in iteritems(self.expected):
            for item in items:
                if isinstance(item, MyCase):
                    self.case_expectations[item.codename] += encode(key)
                else:
                    self.expectations[item.unique_name] += encode(key)

        # JSON doesn't allow lists nor tuples as keys so we dump them, too
        self.expectations = {json.dumps(key, sort_keys=True): val for key, val
                             in iteritems(self.expectations)}

    def _should_test(self, local_test):
        """
        Finds out whether this submission should be tested, given the
        current command line arguments.

        local_test (bool|string): if False, then no solution should be tested
                                  if True, then all solutions should be tested
                                  if string, then the solutions whose file
                                  names all contain this string, should be
                                  tested

        return (bool): whether this submission should be tested

        """
        if isinstance(local_test, bool):
            return local_test
        else:
            return all(local_test in self.task.short_path(f)
                       for f in self.filenames)

    @staticmethod
    def score_machine_readable(x):
        """
        Turn the score expectation as indicated by the user into something
        that is easily comprehensable by the score type
        """
        if x == "arbitrary":
            return [float("-inf"), float("inf")]

        try:
            float(x)
            return [float(x), float(x)]
        except TypeError:
            pass

        return x

    @staticmethod
    def score_human_readable(x):
        """
        Pretty print the score expectation as indicated by the user
        """
        return str(x)


class MyStatement(object):
    def __init__(self, file_, primary):
        self.file_ = file_
        self.primary = primary


class TaskConfig(CommonConfig, Scope):
    """
    Class for task configuration files.

    :ivar contest: The contest this task belongs to
    :ivar wdir: The build directory for this task
    :ivar name: The (short) name of this task
    :ivar num: The (0-based) index of this task
    :ivar subtasks: List of the subtasks
    :ivar cases: List of the test cases
    :ivar testsubmissions: List of the test submissions
    :ivar attachments: Dictionary of the attachments
    :ivar spoilers: Dictionary of the spoilers
    :ivar saved: List of the saved (public) test cases

    This object is exported as a variable called :samp:`task`.
    """

    def __init__(self, upstream, rules, name, num, feedback, score_mode,
                 ignore_latex=False, verbose_latex=False,
                 relevant_language=None, minimal=False, safe_latex=None,
                 standalone_task=False):
        super(TaskConfig, self).__init__(rules, ignore_latex=ignore_latex,
                                         verbose_latex=verbose_latex,
                                         relevant_language=relevant_language,
                                         safe_latex=safe_latex)
        self.no_tokens()
        Scope.__init__(self)

        if not os.path.exists("cases"):
            os.makedirs("cases")
        if not os.path.exists("cases_by_hash"):
            os.makedirs("cases_by_hash")

        if os.path.exists("subtasks"):
            shutil.rmtree("subtasks")
        if not os.path.exists("subtasks"):
            os.makedirs("subtasks")

        self.upstream = upstream
        self.contest = upstream
        if self.safe_latex is None:
            self.safe_latex = upstream.safe_latex

        self.wdir = os.getcwd()

        self.name = name
        self.num = num

        self._dataset = "imported"

        self.subtasks = []
        self.subtask_stack = []
        self.cases = []
        self.cases_by_codename = {}
        self.cases_hashnames = set()
        self.group_stack = []
        self.current_group = None
        self.output_generator = None
        self.testsubmissions = []
        self.attachments = {}
        self.spoilers = {}
        self.managers = {}
        self.tasktype = None
        self.saved = []

        self.everything_checked = True

        self._statements = {}

        self.weak_time_limit = 2
        self.strong_time_limit = 0.5
        self.weak_mem_limit = 2
        self.strong_mem_limit = 0.5

        self.exported["task"] = self

        # Default submission limits
        self.submission_limits(None, None)
        self.user_test_limits(None, None)

        # utils
        self.exported["token_equ"] = self.upstream.token_equ_fp
        self.exported["arbitrary"] = "arbitrary"

        def empty_output_generator(*args, **kwargs):
            pass
        self.exported["empty"] = InternalPython(empty_output_generator)

        # Get data from upstream, but not the other way round
        self.inheriting = True
        self.bequeathing = False

        # Feedback
        self._feedback_param = feedback
        self.feedback = feedback[0]

        if feedback[1]:
            self._feedback_level_full()
        else:
            self._feedback_level_restricted()

        if self.feedback == "token":
            self.tokens(*tuple(feedback[2:]))

        # Score mode
        self._score_mode = score_mode

        # Only compile statements that end with given string
        self.relevant_language = relevant_language

        # Only compile statement (and hopefully everything necessary for this)
        self.minimal = minimal

        # Is this task only part of a dummy contest?
        self.standalone_task = standalone_task

        # Multiscoring? (see batch())
        self.multiscore = False

    @exported_function
    def max_score(self):
        return sum(t.max_score() for t in self.subtasks if not t.sample)

    @property
    def unique_name(self):
        """Helper method for unit tests
        """
        return ()

    @property
    def cases_directory(self):
        """
        The path of the directory containing the input and output files.
        """
        return os.path.join(self.task.wdir, "cases_by_hash")

    def _readconfig(self, filename):
        with header("Loading task {}".format(self.name), depth=2):
            super(TaskConfig, self)._readconfig(filename)

        print_msg("Creating test case zip files")
        # Automatically make a ZIP file containing the saved test cases
        self._makesavedzip()
        # Automatically make a ZIP file containing all test cases for analysis mode
        self._makeallzip()
        if self.tasktype == "OutputOnly":
            self._makeinputzip()

        self._collect_garbage()

        if self.tasktype is None:
            raise Exception("You have to specify a task type")

    def curr_scope(self):
        if len(self.group_stack) > 0:
            return self.group_stack[-1]
        elif len(self.subtask_stack) > 0:
            return self.subtask_stack[-1]
        else:
            return self

    @exported_function
    def get_constraint(self, name):
        return self.curr_scope()._collect_constraints()[0][name]

    @exported_function
    def get_constraint_lower(self, name):
        return self.get_constraint(name)[0]

    @exported_function
    def get_constraint_upper(self, name):
        return self.get_constraint(name)[1]

    @exported_function
    def get_constraint_value(self, name):
        l = self.get_constraint_lower(name)
        u = self.get_constraint_upper(name)

        if l == u:
            return l
        else:
            raise ValueError("calling get_constraint_value although lower and "
                             "upper do not agree")

    # Supplement helpers

    def cpp_constraints(self):
        def cppify(x):
            if x is None:
                return "none";
            else:
                return "(string)\"{}\"".format(x)

        if self.current_group is None:
            return ""
        hard_constraints, soft_constraints = \
            self.current_group._collect_constraints()

        s =  '#define CONSTRAINTS_INCLUDED\n'
        s += '#include <checkutil.h>\n'
        s += 'void load_constraints() {\n'
        for var, ran in hard_constraints.items():
            s += '\tput_integral_constraint("{}", {}, {});\n'.\
                     format(var, cppify(ran[0]), cppify(ran[1]))

        s += '\n\tconstraint curr;\n'

        for cl in soft_constraints:
            s += '\tNEW_SOFT_CONSTRAINT_LIST;\n'

            for c in cl.constraints:
                s += '\t\tNEW_SOFT_CONSTRAINT(({}), ({}));\n'.\
                         format(cppify(c.lower()), cppify(c.upper()));

                for var in c.variables:
                    s += '\t\t\tSOFT_CONSTRAINT_VAR(("{}"));\n'.format(var.val)

        special_cases, soft_special_cases = \
            self.current_group._get_special_cases()

        for desc in special_cases:
            s += '\tadd_special_case("{}");\n'.format(desc)

        for desc, _ in soft_special_cases:
            s += '\tadd_soft_special_case("{}");\n'.format(desc)

        s += '}\n'
        return s

    # Simple task properties

    @exported_function
    def title(self, s):
        """
        Set the task title.

        s (unicode): task title

        """
        self._title = s

    @exported_function
    def dataset(self, s):
        """
        Set the description of the dataset to import to.
        If a dataset with this description already exists, it is overwritten.
        Otherwise, a new dataset is created.
        The active dataset is left unchanged when reimporting a contest.

        s (unicode): dataset description

        """
        self._dataset = s

    @exported_function
    def timelimit(self, s):
        """
        Set the time limit.

        s (float): time limit in seconds

        """
        self._timelimit = s

    @exported_function
    def memorylimit(self, s):
        """
        Set the memory limit.

        s (int): memory limit in MB

        """
        self._memorylimit = s

    @exported_function
    def statement(self, s, language="en", primary=None):
        """
        Add a task statement in a specific language.

        s (string): file name of the (compiled) task statement

        language (string): the language code of this language

        primary (bool): whether this is a primary statement for this task;
                        by default, the first statement added is primary

        """
        if primary is None:
            primary = (len(self._statements) == 0)
        if s is not None:
            self._statements[language] = MyStatement(os.path.abspath(s), primary)

    @exported_function
    def attachment(self, localname, publicname):
        """
        Add an attachment, which contestants can see when competing.

        localname (string): name of the file to add

        publicname (string): file name displayed in CMS

        """
        if localname is not None:
            self.attachments[publicname] = os.path.abspath(localname)

    @exported_function
    def spoiler(self, localname, publicname):
        """
        Add a spoiler, i.e. an attachment that contestants can only see during analysis mode.

        localname (string): name of the file to add

        publicname (string): file name displayed in CMS

        """
        if localname is not None:
            self.spoilers[publicname] = os.path.abspath(localname)

    def std_extensions(self):
        _EXTENSIONS = ["cpp", "pas", "java", "py"]

        return [e for e in _EXTENSIONS
                  if any("." + e in get_language(lang).source_extensions
                         for lang in self.upstream._languages)]

    def std_language(self, filename):
        ext = os.path.splitext(filename)[1]
        possible_languages = [l for l in self._usual_languages()
                                if ext in get_language(l).source_extensions]

        assert (len(possible_languages) == 1)
        return possible_languages[0]

    """
    **Task types**
    """

    @exported_function
    def batch(self, input='', output='', comparator=None, library=False,
              multiscore=False):
        """
        Specify this to be a batch task.

        input (string): input file name ('' means stdin)

        output (string): output file name ('' means stdout)

        comparator (CPPProgram): executable to be used as a comparator
                                 (must at least implement get_path() to get
                                 the file name of the executable)

        library (bool): whether to use a library for linking contestant
                        solutions;
                        submissions are linked together with
                        interface.{c,cpp,pas,py,...} and, if existent, lib.h
                        and lib.pas.

        multiscore (bool): whether or not we allow multiscoring
                           (award different scores to the same testcase
                           depending on subtask/group, e.g. if there is only one
                           partial scoring subtask)
        """
        self.tasktype = "Batch"
        grader_param = "alone"
        if library:
            grader_param = "grader"
            for end in self.std_extensions():
                p = os.path.join(self.wdir, "interface." + end)
                if not self.standalone_task or os.path.exists(p):
                    self.managers["grader." + end] = p
            if os.path.exists(os.path.join(self.wdir, "lib.h")):
                self.managers["%s.h" % self.name] = \
                    os.path.join(self.wdir, "lib.h")
            if os.path.exists(os.path.join(self.wdir, "lib.pas")):
                self.managers["%slib.pas" % self.name] = \
                    os.path.join(self.wdir, "lib.pas")
        evaluation_param = "diff"
        if comparator is not None:
            evaluation_param = "comparator"
            self.managers["checker"] = comparator.get_path()
        self.tasktypeparameters = ([grader_param, [input, output], evaluation_param])
        self.multiscore = multiscore

    @exported_function
    def outputonly(self, comparator=None):
        """
        Specify this to be an output-only task.

        comparator (CPPProgram): executable to be used as a comparator
                                 (must at least implement get_path() to get
                                 the file name of the executable)

        """
        self.tasktype = "OutputOnly"
        evaluation_param = "diff"
        if comparator is not None:
            evaluation_param = "comparator"
            self.managers["checker"] = comparator.get_path()
        self.tasktypeparameters = ([evaluation_param])

    @exported_function
    def communication(self, manager, stub=True, num_processes=1, multiscore=False):
        """
        Specify this to be a communication task.

        manager (CPPProgram): executable communicating with the contestant
                              submissions
                              (must at least implement get_path() to get
                              the file name of the executable)

        Submissions are linked together with interface.{c,cpp,pas,py,...}.
        num_processes:        e.g. set to 2 for a Two-Step task
        """
        self.tasktype = "Communication"
        self.multiscore = multiscore
        self._communication_common(manager, stub, num_processes)

    @exported_function
    def omnipotent_manager(self, manager, num_processes=1, multiscore=False):
        """
        Specify this to be a communication task with an "omnipotent" manager

        manager (CPPProgram): executable communicating with the contestant
                              submissions and CMS
                              (must at least implement get_path() to get
                              the file name of the executable)

        Submissions are linked together with interface.{c,cpp,pas,py,...}.
        num_processes:        e.g. set to 2 for a Two-Step task
        """
        self.tasktype = "OmnipotentManager"
        self.multiscore = multiscore
        self._communication_common(manager, True, num_processes)

    def _communication_common(self, manager, stub, num_processes):
        """
        Common code for Communication and OmnipotentManager tasktypes
        """
        if stub:
            for end in self.std_extensions():
                p = os.path.join(self.wdir, "interface." + end)
                if not self.standalone_task or os.path.exists(p):
                    self.managers["stub." + end] = p
            if os.path.exists(os.path.join(self.wdir, "lib.h")):
                self.managers["%s.h" % self.name] = \
                    os.path.join(self.wdir, "lib.h")
            if os.path.exists(os.path.join(self.wdir, "lib.pas")):
                self.managers["%slib.pas" % self.name] = \
                    os.path.join(self.wdir, "lib.pas")
        self.managers["manager"] = manager.get_path()
        self.tasktypeparameters = ([num_processes, "stub" if stub else "alone",
                                    "fifo_io"])

    @exported_function
    def output_generator(self, s):
        """
        Set the output file generator.

        s (Executable): the output generator
                        (stdin is redirected from the test case input,
                        the expected output should be written to stdout)

        """
        print_msg("Registered output generator {}".format(s), headerdepth=10)
        self.output_generator = s

    # Test cases (subtasks, groups, ...)

    @exported_function
    def make_testcase(self, prog):
        """
        Create (and return) a test case, but do not add it to any test
        case group (so it will be evaluated but doesn't count towards the
        score).

        The input file is generated via a call to prog() where stdout is
        redirected to the input file.

        The reference output file is generated using the previously specified
        output generator.

        The test case will not be checked, yet!

        prog (Executable): program to run to generate the test case

        """
        codename = case_number = "%.04d" % (len(self.cases) + 1)

        if self.output_generator is None:
            raise Exception(
                "You must specify an output generator before a test case")

        # Note that we don't use the output (infile) path of prog or the
        # in- and output part (infile and outfile) path of the output
        # generator as part of the mission hash, unlike the actual missions
        hashname = '-'.join((prog.missionhash()[:14],
                            self.output_generator.missionhash()[:14]))

        if hashname in self.cases_hashnames:
            raise Exception("Another testcase already has the identifier {}. "
                            "Perhaps you generated the same testcase twice? "
                            "You should only call testcase(x) once for any "
                            "one x for the same output generator. If you want "
                            "to add it twice, assign it like t = testcase(x) "
                            "and use add_testcase(t) later.".format(codename))

        with header("Generating test case {} ({})"
                    .format(codename, hashname), depth=5):
            case = MyCase(self, codename, hashname)

            prog(stdout=case.infile)

            self.output_generator(stdin=case.infile, stdout=case.outfile)
            self.cases.append(case)
            self.cases_by_codename[codename] = case
            self.cases_hashnames.add(hashname)
            return case

    @exported_function
    def explicit(self, filename):
        """
        Helper function for testcases which are explicitly available in a
        file (often sample test cases). Returns a generator that simply uses
        the given file as input file.

        filename (string): name of the input file

        """
        def f(stdout, stdin=None):
            with open(filename) as fi:
                shutil.copyfileobj(fi, stdout)
        return self.encapsulate(f, filename)

    @exported_function
    def verbatim(self, *args, **kwargs):
        """
        Helper function for testcases which are hardcoded in the config file
        (should be only used for very small testcases)

        You can pass any sequence of variables (that can be meaningfully
        converted to strings) to this method, they will be separated by
        blank spaces.

        The input is terminated with a newline unless you add flush=False
        as a parameter.
        """
        flush = True

        try:
            flush = kwargs["flush"]
        except:
            pass

        stdoutstring = " ".join(["{}".format(x) for x in args])
        if flush:
            stdoutstring += "\n"

        def curried(stdout=None, **kwargs):
            stdout.write(stdoutstring)

        return self.encapsulate(curried, stdoutstring)

    @exported_function
    def subtask(self, description, name=None, sample=False, scorestyle=0, individual=False):
        """
        Specify the start of a new subtask. The number of points awarded
        for a subtask is the sum of the numbers of points awarded for each
        test case group the subtask contains.

        You usually use this function in the following way:
        ::

            with subtask("Subtask 1", "small"):
                ...

        description (string): description of the subtask to be displayed to
                              the contestant

        name (string): name of this subtask; the subtask object will be
                       accessible as an attribute with this name of the
                       task object;
                       the task should not have a field with this name before
                       by default, we take sNR where NR is the index of this
                       subtask (starting at 0)

        sample (bool): whether this subtask is for sample test cases

        scorestyle (int): score style (always 0 for usual tasks, general integer
                         for multiscoring tasks)

        return (MySubtask): object representing the created subtask

        """
        if name is None:
            name = "s" + str(len(self.subtasks))

        foldername = "Subtask_" + str(len(self.subtasks))
        if sample:
            foldername += "_Public"
        subtask = MySubtask(self, description, name, sample, foldername,
                            scorestyle, individual)

        self.subtasks.append(subtask)

        if hasattr(self, name):
            raise Exception("The task already has an attribute "
                            "called '{}'".format(name))
        setattr(self, name, subtask)

        return subtask

    @exported_function
    def group(self, *args, name=None, **kwargs):
        """
        Add a group to the "current" subtask.

        See :py:meth:`cmscontrib.gerpythonformat.TaskConfig.MySubtask.group`.

        You usually use this function in the following way:
        ::

            with subtask("Subtask 1", "small"):
                with group(50):
                    ...

        """
        if len(self.subtask_stack) == 0:
            raise Exception("group() called outside subtask")

        kwargs["scorestyle"] = kwargs.get("scorestyle") or self.subtask_stack[-1].scorestyle

        g = self.subtask_stack[-1].group(*args, **kwargs)

        if name is not None:
            if hasattr(self.subtask_stack[-1], name):
                raise Exception("This subtask already has an attribute "
                                "called '{}'".format(name))
            setattr(self.subtask_stack[-1], name, g)

        return g


    @exported_function
    def multigroup(self, *args, name=None, scorestyle=None, **kwargs):
        """
        Add multiple groups with different score styles to the "current" subtask.

        This is meant if you want to grade different aspects of the output
        separately: all groups have the same testcases, but different score styles
        (consecutive styles starting with scorestyle or the score style of the
        subtask).

        You usually use it like this:
        ::

            with subtask("Subtask 1", name="fancy_partial_scoring_subtask"):
                with multigroup(10, 6, 4):
                    ...
        """
        if name is None:
            name = f"__g{len(self.subtask_stack[-1].groups)}_mg"

        kwargs["scorestyle"] = scorestyle or self.subtask_stack[-1].scorestyle
        points = list(args)

        return MultiGroupProxy(self.group(points[0], **kwargs), points[1:])

    def _subsume_group(self, g, *args, **kwargs):
        for t in g.cases:
            self.add_testcase(t, *args, **kwargs)

    @exported_function
    def subsume_subtask(self, subtask_name, *args, **kwargs):
        """
        Add a subtask's testcases to the "current" group.

        You usually use this function in the following way:
        ::

            with subtask("Subtask 2", "big"):
                with group(50):
                    subsume_subtask("small")
                    ...

        """
        for g in getattr(self.task, subtask_name).groups:
            self._subsume_group(g)

    @exported_function
    def subsume_group(self, group_name, *args, subtask_name=None, **kwargs):
        """
        Add a group's testcases to the current group.
        """
        st = self.subtask_stack[-1] if subtask_name is None \
             else getattr(self.task, subtask_name)

        self._subsume_group(getattr(st, group_name), *args, **kwargs)

    @exported_function
    def subsume_previous_group(self, *args, **kwargs):
        """
        Add the testcases of the previous group (of the same subtask) to the
        current group.
        """
        self._subsume_group(self.subtask_stack[-1].groups[-2])

    @exported_function
    def checker(self, *args, **kwargs):
        """
        Register a test case checker for the "current" task, subtask or group.

        The checker must be a CPPProgram.

        See :py:meth:`.Scope.add_checker`.

        """
        if len(self.group_stack) > 0:
            self.group_stack[-1].add_checker(*args, **kwargs)
        elif len(self.subtask_stack) > 0:
            self.subtask_stack[-1].add_checker(*args, **kwargs)
        else:
            self.add_checker(*args, **kwargs)

    @exported_function
    def constraint(self, *args, **kwargs):
        """
        Add a constraint for the "current" task, subtask or group.

        See :py:meth:`.Scope.add_constraint`.

        """
        if len(self.group_stack) > 0:
            self.group_stack[-1].add_constraint(*args, **kwargs)
        elif len(self.subtask_stack) > 0:
            self.subtask_stack[-1].add_constraint(*args, **kwargs)
        else:
            self.add_constraint(*args, **kwargs)

    @exported_function
    def constraint_variable(self, con):
        self.constraint(con + ": [,]", silent=True)

    @exported_function
    def special_case(self, case, frequency=ConstraintList.ALWAYS):
        """
        Mark a current subtask or group as "special case"

        See :py:meth:`.Scope.add_special_case`.

        """
        if len(self.group_stack) > 0:
            self.group_stack[-1].add_special_case(case, frequency)
        elif len(self.subtask_stack) > 0:
            self.subtask_stack[-1].add_special_case(case, frequency)
        else:
            if frequency == ConstraintList.ALWAYS:
                print_msg("You called special_case globally—this is a bit "
                          "weird, so I hope you know what you're doing…",
                          warning=True)

            self.add_special_case(case, frequency)

    @exported_function
    def add_testcase(self, *args, **kwargs):
        """
        Add a test case to the "current" group.

        See
        :py:meth:`cmscontrib.gerpythonformat.TaskConfig.MyGroup.add_testcase`.

        You usually use this function in the following way:
        ::

            t = make_testcase(...)
            with subtask("Subtask 1", "small"):
                with group(50):
                    add_testcase(t, ...)

        """
        if self.minimal:
            print_msg("Skipping testcase (minimal mode)")
            self.group_stack[-1]._dummy_case(kwargs.get("name"))
            return

        if len(self.group_stack) == 0:
            raise Exception("add_testcase() called outside group")
        return self.group_stack[-1].add_testcase(*args, **kwargs)

    @exported_function
    def testcase(self, *args, **kwargs):
        """
        Create and add a test case to the "current" group.

        See :py:meth:`cmscontrib.gerpythonformat.TaskConfig.MyGroup.testcase`.

        You usually use this function in the following way:
        ::

            with subtask("Subtask 1", "small"):
                with group(50):
                    testcase(...)

        """
        if not kwargs.get("save") and self.minimal:
            print_msg("Skipping testcase (minimal mode)")
            self.group_stack[-1]._dummy_case(kwargs.get("name"))
            return

        if len(self.group_stack) == 0:
            raise Exception("testcase() called outside group")
        return self.group_stack[-1].testcase(*args, **kwargs)

    def _check(self, checker, infile, outfile, caseno, check_counter):
        if self.minimal:
            return

        if not isinstance(checker, CPPProgram):
            raise Exception("Only checkers written in C++ are allowed.")

        try:
            result = checker(outfile, stdin=infile,
                             dependencies=[outfile])

            log = result.out
            return json.loads(log) if len(log) > 0 else None

        except ExitCodeException:
            raise Exception(
                "Checker {} judged case {} as wrong".format(checker, caseno))

    def _get_cases(self):
        """
        Utility method for being able to find the test cases contained in a
        task, subtask, group or test case.

        return (list): list of test cases

        """
        return self.cases

    def _level(self):
        return 0

    @exported_function
    def test_submission_limits(self,
                               weak_time_limit=None, strong_time_limit=None,
                               weak_mem_limit=None, strong_mem_limit=None):
        """
        Set default relative weak and strong time and memory limits for test
        submissions.
        """
        if weak_time_limit is not None:
            self.weak_time_limit = weak_time_limit
        if strong_time_limit is not None:
            self.strong_time_limit = strong_time_limit
        if weak_mem_limit is not None:
            self.weak_mem_limit = weak_mem_limit
        if strong_mem_limit is not None:
            self.strong_mem_limit = strong_mem_limit

    @exported_function
    def test_submission(self, *args, **kwargs):
        """
        Create a test submission from the given source file(s).

        non-keyword arguments (list): the (source) file names

        score (float): the expected official (final) score

        sample_score (float): the expected score in the sample test cases
                              (= in subtasks with sample=True)

        partial_feedback_score (float): the expected score in partial feedback
                                        mode; by default, this equals the
                                        expected final score.

        expected (dict): the expectations for the test cases;
                         by default, we expect all test cases to succeed

        weak_time_limit (float): larger time limit this submission
                                 is evaluated with (in multiples of
                                 the time limit for this task)

        strong_time_limit (float): smaller time limit this submission
                                   is evaluated with (in multiples of
                                   the time limit for this task)

        weak_mem_limit (float): larger memory limit this submission
                                is evaluated with (in multiples of
                                the memory limit for this task)

        strong_mem_limit (float): smaller memory limit this submission
                                  is evaluated with (in multiples of
                                  the memory limit for this task)

        """
        if self.minimal:
            return

        print_msg("Added test submission {}"
                  .format(", ".join(self.contest.short_path(s) for s in args)),
                  headerdepth=10)
        self.testsubmissions.append(
            MySubmission(self, [os.path.abspath(s) for s in args], **kwargs))

    def _feedback_level_full(self):
        """
        Show information about all test cases in public subtasks to the
        contestants.

        """
        self._feedback_level = FEEDBACK_LEVEL_FULL

    def _feedback_level_restricted(self):
        """
        In each non-sample group, show only the first test case with minimum
        score.
        Additionally, used time and memory are hidden in those groups.

        """
        self._feedback_level = FEEDBACK_LEVEL_RESTRICTED

    def _has_restricted_feedback_level(self):
        return self._feedback_level == FEEDBACK_LEVEL_RESTRICTED

    def score_mode(self):
        if self._score_mode is None:
            if self.feedback == "full":
                return SCORE_MODE_MAX_SUBTASK
            else:
                return SCORE_MODE_MAX_TOKENED_LAST
        else:
            return self._score_mode

    def _printresult(self):
        if self.minimal:
            return

        with header("Statistics", depth=3):
            print_msg("Taskname: {}".format(self.name))
            sts = ["{} {}{}".format(l, self.short_path(s.file_),
                                    " (primary)" if s.primary else "")
                   for l, s in iteritems(self._statements)]
            print_msg("Task statements: {}".format(", ".join(sts)))
            print_msg("Attachments: {}".format(", ".join(self.attachments)))
            print_msg("Spoilers: {}".format(", ".join(self.spoilers)))
            print_msg("Number of subtasks: {}".format(len(self.subtasks)))
            print_msg("Number of test cases: {}".format(len(self.cases)))
            print_msg("Score mode: {}".format(self.score_mode()))
            print_msg("Feedback mode: {}".format(self.feedback))
            print_msg("Feedback level: {}".format(self._feedback_level))
            if not self.everything_checked:
                print_msg("Not every test case has been checked", error=True)

    def _makesavedzip(self):
        """
        Create and add an attachment containing the saved test cases.
        """
        zipname = os.path.join(self.wdir, "savedcases.zip")
        contents = {}
        for i, c in enumerate(self.saved):
            contents["%d.in" % (i + 1)] = c.infile
            contents["%d.out" % (i + 1)] = c.outfile
        ZipRule(self.rules, zipname, contents).ensure()
        self.attachment(zipname, "%s.zip" % self.name)

    def _makeallzip(self):
        """
        Create and add a spoiler containing all test cases.
        """
        zipname = os.path.join(self.wdir, "allcases.zip")
        contents = {}
        for i, c in enumerate(self.cases):
            contents["%d.in" % (i + 1)] = c.infile
            contents["%d.out" % (i + 1)] = c.outfile
        ZipRule(self.rules, zipname, contents).ensure()
        self.spoiler(zipname, "%s_all.zip" % self.name)
        # TODO Replace by zipped subtask directory

    def _makeinputzip(self):
        """
        Create and add an attachment containing the input files (mostly
        for output-only tasks).
        """
        zipname = os.path.join(self.wdir, "inputs.zip")
        contents = {}
        for c in self.cases:
            contents["input_{}.txt".format(c.codename)] = c.infile
        ZipRule(self.rules, zipname, contents).ensure()
        self.attachment(zipname, "%s_input.zip" % self.name)

    def _collect_garbage(self):
        """
        Delete directories of test cases that weren't made in this run.
        """
        if self.minimal:
            return

        for directoryname in os.listdir(self.cases_directory):
            if directoryname not in self.cases_hashnames:
                try:
                    shutil.rmtree(os.path.join(self.cases_directory, directoryname))
                    print("Collected garbage case {}".format(directoryname))
                except OSError:
                    print("Couldn't collect garbage case {}."
                        .format(directoryname))
                    raise

    def short_path(self, f):
        """
        Return a (possibly) shorter name for a file (which can be relative
        to the contest build directory).

        f (string): file name to shorten

        return (string): shortened file name

        """
        return self.contest.short_path(f)

    def _makedbobject(self, contest, file_cacher):
        """
        Return a Task object which can be saved to the database.
        TODO What exactly happens to test submissions? Can we still add them
             to the database if local_test=True?

        file_cacher (FileCacher): for saving files (test cases,
                                  attachments, ...)

        local_test (bool|string): specifies which submissions should be tested
                                  locally (cf. MySubmission._should_test)

        return (Task): database object for the task

        """
        self.file_cacher = file_cacher

        tdb = Task(name=self.name,
                   title=self._title,
                   num=self.num,
                   contest=contest)
        self._set_tokens(tdb)
        tdb.max_submission_number = self.max_submission_number
        tdb.min_submission_interval = self.min_submission_interval
        tdb.max_user_test_number = self.max_user_test_number
        tdb.min_user_test_interval = self.min_user_test_interval
        tdb.feedback_level = self._feedback_level
        tdb.score_mode = self.score_mode()

        if self.tasktype == "OutputOnly":
            tdb.submission_format = [
                "output_%s.txt" % c.codename
                for c in self.cases]
        else:
            tdb.submission_format = [
                "%s.%%l" % self.name]
        tdb.attachments = {}
        tdb.spoilers = {}
        tdb.statements = {}
        primary_statements = []

        # Add statements
        for language, statement in iteritems(self._statements):
            digest = file_cacher.put_file_from_path(
                statement.file_,
                "Statement task %s in language %s" % (self.name, language))
            tdb.statements[language] = Statement(language=language,
                                                 digest=digest)
            if statement.primary:
                primary_statements.append(language)

        tdb.primary_statements = primary_statements

        # Add attachments
        for name, file in iteritems(self.attachments):
            digest = file_cacher.put_file_from_path(
                file,
                "Attachment %s to task %s" % (name, self.name))
            tdb.attachments[name] = Attachment(filename=name, digest=digest)

        # Add spoilers
        for name, file in iteritems(self.spoilers):
            digest = file_cacher.put_file_from_path(
                file,
                "Spoiler %s to task %s" % (name, self.name))
            tdb.spoilers[name] = Spoiler(filename=name, digest=digest)

        tdb.active_dataset = self._makedataset(file_cacher, tdb)

        return tdb

    def _makedataset(self, file_cacher, tdb):
        def make_subtask_parameters(s):
            return {
                'name': s.description,
                'key': list(s.unique_name),
                'sample': s.sample,
                'groups': [make_group_parameters(g) for g in s.groups],
            }

        def make_group_parameters(g):
            return {
                'points': g.points,
                'key': list(g.unique_name),
                'testcases': [make_case_parameters(c, f)
                              for c, f in zip(g.cases, g.feedback)],
                'scorestyle': g.scorestyle
            }

        def make_case_parameters(c, f):
            return {
                'codename': c.codename,
                'in_partial_feedback': f,
            }
        score_type_parameters = {
            'feedback': self.feedback,
            'multiscore': self.multiscore,
            'subtasks': [make_subtask_parameters(s) for s in self.subtasks],
        }

        ddb = Dataset(task=tdb,
                      description=self._dataset,
                      task_type=self.tasktype,
                      task_type_parameters=self.tasktypeparameters,
                      score_type="SubtaskGroup",
                      score_type_parameters=score_type_parameters)
        ddb.time_limit = float(self._timelimit)
        ddb.memory_limit = self._memorylimit * 1024 * 1024

        # Add test cases
        for c in self.cases:
            input_digest = file_cacher.put_file_from_path(
                os.path.join(self.wdir, c.infile),
                "Input %s for task %s" % (c.codename, self.name))
            output_digest = file_cacher.put_file_from_path(
                os.path.join(self.wdir, c.outfile),
                "Output %s for task %s" % (c.codename, self.name))
            tcdb = Testcase(codename=c.codename,
                            input=input_digest,
                            output=output_digest,
                            public=c.public)
            ddb.testcases[c.codename] = tcdb

        # Add managers
        for name, file in iteritems(self.managers):
            digest = file_cacher.put_file_from_path(
                file,
                "Manager %s for task %s" % (name, self.name))
            ddb.managers[name] = Manager(filename=name, digest=digest)

        return ddb

    def _make_test_submissions(self, pdb, tdb, local_test, tcimp=True):
        ddb = tdb.active_dataset

        sdbs = []

        failed = []
        unit_tests = []
        unit_test_results = {}

        # Test submissions
        for s in self.testsubmissions:  # submissions are saved because they
                                        # are referenced through the user
                                        # object
            sdb = self._makesubmission(s, pdb, tdb, official=False)
            # dummy id, the correct value is inserted by GerImporter.py
            sdb.task_id = 0
            sdb.task = tdb

            sdbs.append(sdb)

            if s._should_test(local_test):
                code = ", ".join(self.short_path(f) for f in s.filenames)

                sdb.id = 1
                with header("Running solution {}".format(code),
                            depth=3):
                    okay, details = self._do_test_submission(sdb, ddb)
                    if not okay:
                        failed.append(code)

                    unit_tests.append(code)
                    unit_test_results[code] = details

        if len(self.testsubmissions) == 0:
            print()
            box(" No Unit Tests for Task \"{}\"! ".format(self._title),
                red("You should define some unit tests for this task!"),
                double=True)
            print()

        elif len(unit_tests) != 0:
            print()
            box(" Unit Test Statistics for Task \"{}\" ".format(self._title),
                (green("All unit tests passed.")
                if len(failed) == 0
                else red("{} unit test{} failed:\n".format(len(failed), "s" if len(failed) > 1 else "") +
                         "\n".join(red(f) for f in failed))
                 ) +
                ("\n\n" + yellow("There are some additional (non-local) "
                                 "unit tests!") if len(unit_tests) != len(self.testsubmissions)
                 else ""), double=True)
            print()

            if tcimp:
                self._testcase_importance(unit_test_results)

        return sdbs

    def _testcase_importance(self, unit_test_results):
        essential = {}
        useful = set()
        dominated = {d.codename: {c.codename for c in self.cases
                                  if c.codename != d.codename}
                     for d in self.cases}

        for u, details in unit_test_results.items():
            useful |= set(details["useful"])

            for e in details["essential"]:
                if e not in essential:
                    essential[e] = []
                essential[e].append(u)

            for id in dominated.keys():
                dominated[id] &= set(details["dominated"][id])
        samples = {c.codename for s in self.subtasks if s.sample
                              for g in s.groups
                              for c in g.cases}
        private = {c.codename for s in self.subtasks
                              for g in s.groups
                              for c in g.cases} - samples

        essential_cases = sorted(list(essential))
        potentially_useful_cases = sorted(c for c in useful
                                          if c not in essential)
        useless_cases = sorted(list(private - (set(essential) | useful)))
        probably_useless = []
        probably_useful = []
        to_inspect = []
        strictly_dominated = {}

        for c in potentially_useful_cases:
            D = [d for d in dominated[c] if c not in dominated[d]]
            num_dominated = len(D)

            if num_dominated > 0:
                probably_useless.append(c)
                strictly_dominated[c] = D[:]
            elif len(dominated[c]) == 0:
                probably_useful.append(c)
            else:
                to_inspect.append(c)

        def color(c):
            id = c.codename
            if id in samples:
                if id in essential or id in probably_useful or id in to_inspect:
                    return yellow(str(id))
                else:
                    return gray(str(id))
            elif id in essential:
                return purple(str(id))
            elif id in probably_useful:
                return lightgreen(str(id))
            elif id in to_inspect:
                return blue(str(id))
            elif id in probably_useless:
                return orange(str(id))
            else:
                return red(str(id))

        def nice(c):
            return str(self.cases_by_codename[c])

        def nice_list(L):
            return ", ".join(nice(c) for c in sorted(L))

        with header("Testcase utility", 2):
            with header("Overview", 3):
                print_msg(" ".join(color(c) for c in self.cases),
                          use_ellipsis=False)
                print()

            if len(essential_cases) > 0:
                with header(purple("Essential"), 3):
                    print_msg("The following testcases are essential, i.e. "
                              "removing any of them would immediately affect "
                              "scoring substantially (while this means they "
                              "are strong cases, you should maybe worry about "
                              "the quality of your other testcases):",
                              use_ellipsis=False)
                    print()
                    for c in essential_cases:
                        print_msg(purple(bold(nice(c)) + " is essential for "
                                  "the following submission(s): " +
                                  ", ".join(essential[c])),
                                  use_ellipsis = True)
                    print()

            if len(probably_useful) > 0:
                with header(lightgreen("Probably useful"), 3):
                    print_msg("The following testcases are useful, but not "
                              "essential from what I can tell (that's great!):",
                              use_ellipsis=False)
                    print()
                    print_msg(lightgreen(nice_list(probably_useful)),
                              use_ellipsis=False)
                    print()

            if len(to_inspect) > 0:
                with header(blue("To inspect"), 3):
                    print_msg("For each fixed submission, the following "
                              "testcases get very similar scores; you might "
                              "want to have a closer look whether you need all "
                              "of them:", use_ellipsis=False)
                    print()

                    # We assume for simplicity that the graph of mutual
                    # domination is transitive; this might not be entirely true
                    # (due to the thresholds we set), but we're not going to
                    # solve the clique problem here (and we're in the case that
                    # the task author should have a closer look anyhow...)
                    X = set()
                    for c in to_inspect:
                        component = frozenset(d for d in dominated[c]
                                                if c in dominated[d]) | {c}
                        if component not in X:
                            X.add(component)
                            print_msg(blue("[" + nice_list(component) + "]"),
                                      use_ellipsis=True)

                    print()

            if len(probably_useless) > 0:
                with header(orange("Probably useless"), 3):
                    print_msg("The following testcases are probably useless as "
                              "there are other testcases which are at least as "
                              "sharp across all submissions (i.e. which always "
                              "produce scores which are lower or at least "
                              "close to the score of this testcase)",
                              use_ellipsis=False)
                    print()
                    for c, d in strictly_dominated.items():
                        print_msg(orange(bold(nice(c)) +
                                  " is dominated by each of the following: " +
                                  nice_list(d)), use_ellipsis=True)
                    print()

            if len(useless_cases) > 0:
                with header(red("Useless"), 3):
                    print_msg("The following testcases are useless, i.e. "
                              "removing them does not even come close to "
                              "affecting scoring (for example because every "
                              "submission succeeds on them):",
                              use_ellipsis=False)
                    print()
                    print_msg(red(nice_list(useless_cases)), use_ellipsis=False)
                    print()

            useful_sample = [id for id in samples
                                if id in essential or id in probably_useful or
                                   id in to_inspect]

            if len(useful_sample) != 0:
                with header(yellow("Warning: strong public testcases"), 3):
                    print_msg("At least one public testcase is relevant for "
                              "scoring (listed below, see the above output for "
                              "further details)—that's... kind of disturbing "
                              "to be honest.", use_ellipsis=False)
                    print()
                    print_msg(yellow(nice_list(useful_sample)),
                              use_ellipsis=False)
                    print()

    def _makesubmission(self, submission, participation, tdb, official=True):
        """
        Create and return a test submission database object.

        submission (MySubmission): configuration object for this submission

        participation (Participation): database object for the test
                                       participation

        tdb (Task): database object for the task

        official (boolean): whether this submission is official (i.e. counts
                            towards the score)

        return (Submission): database object for the submission

        """

        files = submission.filenames

        # TODO Improve this so that test submissions can consist
        # of multiple files, etc. (cf. ContestWebServer.py,
        # class SubmitHandler)
        # Maybe use a common library for submissions?

        # This ensure that the user sent one file for every name in
        # submission format and no more. Less is acceptable if task
        # type says so.
        task_type = get_task_type(name=self.tasktype,
                                  parameters=self.tasktypeparameters)
        required = set(tdb.submission_format)
        provided = set(os.path.basename(f) for f in files)
        if not (required == provided or (task_type.ALLOW_PARTIAL_SUBMISSION
                                         and required.issuperset(provided))
                or len(required) == len(provided) == 1):
            raise Exception(
                "Invalid submission format! Please select the correct files.")

        # If we allow partial submissions, implicitly we recover the
        # non-submitted files from the previous submission. And put them
        # in file_digests (i.e. like they have already been sent to FS).
        submission_lang = None

        # We need to ensure that everytime we have a .%l in our
        # filenames, the user has one amongst ".cpp", ".c", or ".pas,
        # and that all these are the same (i.e., no mixed-language
        # submissions).

        for user_filename in files:
            if len(files) == 1:
                our_filename = list(required)[0]
            else:
                our_filename = user_filename
            if our_filename.find(".%l") != -1:
                lang = self.std_language(user_filename)
                if lang is None:
                    raise Exception("Cannot recognize submission's language.")
                elif submission_lang is not None and \
                        submission_lang != lang:
                    raise Exception(
                        "All sources must be in the same language.")
                else:
                    submission_lang = lang

        # Create submission object
        sdb = Submission(
            timestamp=datetime.utcnow(),
            language=submission_lang,
            participation=participation,
            comment="%s" % (", ".join(os.path.basename(f) for f in files)),
            official=official)
        sdb.task = tdb
        sdb.timestamp = datetime.utcnow()
        sdb.language = submission_lang
        for f in files:
            if len(files) == 1:
                our_filename = list(required)[0]
            else:
                our_filename = os.path.basename(f)
            digest = self.file_cacher.put_file_from_path(
                f,
                "Test submission %s." %
                (os.path.basename(f) for f in files))
            sdb.files[our_filename] = File(our_filename, digest,
                                           submission=sdb)

        # Unit tests
        def m_abs(rel):
            return max(int(rel * self._memorylimit * 1024 * 1024), 1)

        def t_abs(rel):
            return float(rel * self._timelimit)

        sdb.additional_info = json.dumps(
            {"limits": {"weak_time_limit": t_abs(submission.weak_time_limit),
                        "strong_time_limit": t_abs(
                            submission.strong_time_limit),
                        "weak_mem_limit": m_abs(submission.weak_mem_limit),
                        "strong_mem_limit": m_abs(
                            submission.strong_mem_limit)},
             "unit_test": True,
             "expected": submission.expectations,
             "expected_case": submission.case_expectations,
             "expected_sample_score": submission.sample_score,
             "expected_sample_score_info": submission.sample_score_info,
             "expected_partial_feedback_score": submission.partial_feedback_score,
             "expected_partial_feedback_score_info": submission.partial_feedback_score_info,
             "expected_final_score": submission.score,
             "expected_final_score_info": submission.score_info,
             "task_name": self.name,
             "score_precision": tdb.score_precision}, sort_keys=True)

        return sdb

    def _do_test_submission(self, sdb, ddb):
        """
        Test the given submission.

        sdb (Submission): database object for the submission

        ddb (Dataset): database object for the data set

        """
        submission_result = SubmissionResult(submission=sdb,
                                             dataset=ddb)
        # Compile
        compile_operation = ESOperation(ESOperation.COMPILATION, -1, -1)
        compile_job = CompilationJob.from_submission(
            compile_operation, sdb, ddb)
        compile_job = self._run_job(compile_job)
        compile_job.to_submission(submission_result)
        compile_ok = (submission_result.compilation_outcome == "ok")
        if not compile_ok:
            print_msg("Compile error:")
            if submission_result.compilation_stdout is not None:
                print_block(submission_result.compilation_stdout)
            if submission_result.compilation_stderr is not None:
                print_block(submission_result.compilation_stderr)
        else:
            if submission_result.compilation_stdout is not None:
                print_block(submission_result.compilation_stdout)
            if submission_result.compilation_stderr is not None:
                print_block(submission_result.compilation_stderr)
            # Evaluate
            nr_of_testcases = len(ddb.testcases)
            for nr, codename in enumerate(sorted(iterkeys(ddb.testcases))):
                print("\033[2K\033[1GEvaluating {} / {}"
                      .format(nr+1, nr_of_testcases), end='', flush=True)
                evaluation_operation = ESOperation(ESOperation.EVALUATION,
                                                   -1, -1,
                                                   codename)
                evaluation_job = EvaluationJob.from_submission(
                    evaluation_operation,
                    sdb,
                    ddb,
                    submission_result)
                # Remove testcase_codename so the submission isn't re-evaluated
                # when only the testcase's codename has changed.
                evaluation_job.operation.testcase_codename = None
                # Human-readable info would also contain testcase_codename
                evaluation_job.info = None
                evaluation_job = self._run_job(evaluation_job)
                # We insert the codename again because to_submission actually
                # uses it
                evaluation_job.operation.testcase_codename = codename
                evaluation_job.to_submission(submission_result)
            submission_result.set_evaluation_outcome()
            print("\033[2K\033[1G", end='', flush=True)

        # Judge unit test
        score_type = ddb.score_type_object
        _, sample_details = \
            score_type._compute_score(submission_result, "sample")
        _, partial_details = \
            score_type._compute_score(submission_result, "partial")
        _, final_details = \
            score_type._compute_score(submission_result, "final")

        details = score_type.compute_unit_test_score(submission_result,
                                                     sdb.additional_info)

        def v(acc_des, z=False):
            (accepted, desc) = acc_des
            d = desc  # .replace("<br>", "\n")

            if accepted == 1337:
                return yellow(d)
            if accepted == 42:
                return gray(d)
            elif accepted <= 0:
                if z and accepted == 0:
                    return gray(d)
                return red(d)
            else:
                return green(d)

        def w(details, acc_des, length, z=False):
            (accepted, desc) = acc_des
            return v((accepted,
                      pad_left(details.strip() + " " + desc, length)), z=z)

        def myheader(name, status):
            desc = status[1]
            base_space = remaining_line_length() - 15
            space = base_space - len(name) - len(desc)

            return header(name + " " + (space - 2) * "═" + " " +
                          v(status), depth=3)

        # Present verdict
        for st in details["subtasks"]:
            with myheader(st["name"], st["status"]):
                for i, g in enumerate(st["groups"]):
                    with header("Group {}".format(i + 1), depth=4):
                        print_block(v(g["verdict"]))
                        print()

                        if not g["cases"]:
                            print(indent(yellow(
                                "This group has no testcases.")))
                            print()
                            continue

                        print(indent(side_by_side(["Time", "Memory",
                                                   "Answer", "Verdict"],
                                                  [2, 14, 27, 37])))

                        for c in g["cases"]:
                            l = [(b, (a)) for a, b in c["line"]]
                            ftime = "%.3fs" % c["time"]
                            if c["memory"] is None:
                                fmem = "??? MB"
                            else:
                                fmem = "%.1fMB" % (float(c["memory"]) / 2**20)
                            ftime = w(ftime, l[0], 8, z=True)
                            fmem = w(fmem, l[1], 10, z=True)
                            fans = v(l[2], z=True)
                            fverd = add_line_breaks(
                                v(c["verdict"]),
                                remaining_line_length() - 37)
                            print(indent(side_by_side([ftime, fmem,
                                                       fans, fverd],
                                                      [0, 12, 27, 37])))

                        print()
                        print(indent("     max. runtime in this group: " +
                                     bold("%.3fs" % g["max_runtime"])))
                        print(indent("max. memory usage in this group: " +
                                     bold("%.1fMB" %
                                          (float(g["max_memory"]) / 2**20))))
                    print()

            print()

        if compile_ok:
            submission_info = json.loads(sdb.additional_info)
            score_precision = sdb.task.score_precision

            def print_score_info(prefix, name):
                score = details[prefix + "_score"]
                rounded_score = round(score, score_precision)

                if score != rounded_score:
                    score = "{} ({})".format(rounded_score, score)

                if details[prefix + "_score_okay"]:
                    score = green(score)
                else:
                    score = red(score)
                expected_score = details["expected_" + prefix + "_score"]
                print_msg("{} score: {}; expected: {}".
                          format(name, score, expected_score))

            print_score_info("sample", "Sample")

            if details["partial_feedback_enabled"]:
                print_score_info("partial_feedback", "Partial feedback")

            print_score_info("final", "Final")

            print()

        verd = details["verdict"]
        box(" Overall verdict ", green(verd[1]) if verd[0] == 1
            else red(verd[1]))
        print()

        return verd[0] == 1, details

    def _run_job(self, job):
        """
        Run the given job (if necessary) and save the results to it.

        job (Job): the job

        """
        r = JobRule(self.rules, job, self.file_cacher).ensure()
        if not r.job.success:
            raise Exception("Evaluation failure")
        return r.job
