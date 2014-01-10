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

from Messenger import print_msg, print_block, header
from CommonConfig import exported_function, CommonConfig
from Executable import ExitCodeException
from ConstraintParser import ConstraintList, merge_constraints
from cms import SOURCE_EXT_TO_LANGUAGE_MAP
from cms.db import Task, Statement, Testcase, Dataset, \
    SubmissionFormatElement, Attachment, Manager, Submission, File, \
    SubmissionResult
from cms.grading import format_status_text, unit_test_compare
from cms.grading.scoretypes import get_score_type
from cms.grading.tasktypes import get_task_type
from cms.grading.Job import JobGroup
from cms.rules.Rule import JobRule, ZipRule
from cmscommon.datetime import make_timestamp
from datetime import datetime
import json
import os
import shutil


def mem_human(mem):
    if mem is None:
        return "None"
    if mem > 2 ** 30:
        return "%4.3gG" % (float(mem) / (2 ** 30))
    if mem > 2 ** 20:
        return "%4.3gM" % (float(mem) / (2 ** 20))
    if mem > 2 ** 10:
        return "%4dK" % (mem / (2 ** 10))
    return "%4d" % mem


class Scope(object):
    """
    Base class for tasks, subtasks and groups.
    """
    def __init__(self, upscope=None):
        self.upscope = upscope
        self.checkers = []
        self.constraints = []
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

    def add_checker(self, p):
        """
        Register a test case checker for this task, subtask or group.

        p (Executable): the checker (should raise an ExitCodeException if
                        the test case is invalid)

        """
        print_msg("Adding checker {}".format(p), headerdepth=10)
        self.checkers.append(p)

    def add_constraint(self, s, silent=None):
        """
        Add a constraint for this task, subtask or group.
        The constraint format is described in the docs
        """

        if silent is None:
            silent = (isinstance(self, MyGroup)
                      or (isinstance(self, MySubtask) and self.public))

        self.constraints.append(ConstraintList.parse(s, silent))


class MySubtask(Scope):
    """
    :ivar description: Decription of this subtask
    :ivar name: Internal (short) name of this subtask
    :ivar public: Whether this subtask is public
    :ivar groups: Groups contained in this subtask
    """
    def __init__(self, task, description, name, public):
        super(MySubtask, self).__init__(task)
        self.task = task
        self.description = description
        self.name = name
        self.public = public
        self.groups = []
        self.feedbackcases = []
        self.checkers = []
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)

    def __enter__(self):
        info = ""
        if self.public:
            info = ", public"
        self.indenter = header("Subtask {}".format(self.description) + info,
                               depth=3)
        self.indenter.start()

        self.task.subtask_stack.append(self)
        return self

    def __exit__(self, type, value, traceback):
        self.indenter.stop()
        self.task.subtask_stack.pop()

    @property
    def directory(self):
        """
        The name of the directory containing the groups for
        this subtask.
        """
        return os.path.join(self.task.wdir, "subtasks", self.name)

    def group(self, points, name=None):
        """
        Specify the start of a new test case group (part of a subtask).

        points (int): maximum number of points for this test case group;
                      the number of points awarded for a test case group is
                      points * (minimal outcome for test cases in this group)

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

        group = MyGroup(self.task, self, points, name)

        self.groups.append(group)

        if hasattr(self, name):
            raise Exception("The subtask '{}' already has an attribute "
                            "called '{}'".format(self.name, name))
        setattr(self, name, group)

        return group

    def put_feedback(self, description, name, points=None):
        """
        Create a subtask containing all cases inside the current subtask
        that have been marked as detailed feedback cases. All the test cases
        will be put into a single test case group.

        description (string): description of the subtask to create

        name (string): name of the subtask to create

        points (int): number of points the subtask should get (by default
                      the sum of the numbers of points of the groups in this
                      subtask)

        """
        if len(self.feedbackcases) == 0:
            return
        if points is None:
            points = sum(g.points for g in self.groups)
        with self.task.subtask(description, name=name, public=True) as s:
            with s.group(points) as g:
                for case in self.feedbackcases:
                    g.add_testcase(case)

    def _get_cases(self):
        """
        Utility method for being able to find the test cases contained in a
        task, subtask, group or test case.

        return (list): list of test cases

        """
        return [c for g in self.groups for c in g._get_cases()]

    def _level(self):
        return 1


class MyGroup(Scope):
    """
    :ivar subtask: The subtask this group belongs to
    :ivar points: Maximum number of points for this subtask
    :ivar name: Internal (short) name of this group
    :ivar cases: Test cases contained in this group
    """
    def __init__(self, task, subtask, points, name):
        super(MyGroup, self).__init__(subtask)
        self.task = task
        self.subtask = subtask
        self.points = points
        self.name = name
        self.cases = []
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)

    def __enter__(self):
        self.indenter = header("Group {} ({} points)".format(self.name,
                                                             self.points),
                               depth=4)
        self.indenter.start()
        self.task.group_stack.append(self)
        return self

    def __exit__(self, type, value, traceback):
        self.indenter.stop()
        self.task.group_stack.pop()

    @property
    def directory(self):
        """
        The name of the directory containing the links to the test cases
        contained in this group.
        """
        return os.path.join(self.subtask.directory, self.name)

    def _collect_constraints(self):
        res = {}
        for c in self._get_constraints():
            res = merge_constraints(res, c.uncompress())
        return res

    @exported_function
    def add_testcase(self, case, feedback=False, save=False, name=None):
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
        self.task.current_group = self
        for i, checker in enumerate(self._get_checkers()):
            self.task._check(checker, case.infile, case.outfile,
                             case.codename, i+1)
        self.task.current_group = None

        if name is None:
            name = "t" + str(len(self.cases))
        if hasattr(self, name):
            raise Exception(
                "The group '{}.{}' already has an attribute called '{}'"
                .format(self.subtask, self.name, name))
        setattr(self, name, case)

        linkname = os.path.join(self.directory, name)
        if os.path.exists(linkname):
            os.remove(linkname)
        os.symlink(case.directory, linkname)

        print_msg("Added test case {} ({})".format(case.codename, name))

        self.cases.append(case)
        if self.subtask.public:
            case.public = True

        if feedback:
            self.subtask.feedbackcases.append(case)
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


class MyCase(object):
    """
    :ivar codename: The code name of this test case (usually a four-digit
    number).
    """
    def __init__(self, task, codename):
        self.task = task
        self.codename = codename
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)
        self.public = False
        # Strings specifying in which subtasks/groups this case can be found
        self.locations = []

    @property
    def directory(self):
        """
        The name of the directory containing the input and output files for
        this test case.
        """
        return os.path.join(self.task.wdir, "cases", self.codename)

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
    def __init__(self, task, filenames, score, public_score, expected={},
                 weak_time_limit=None, strong_time_limit=None,
                 weak_mem_limit=None, strong_mem_limit=None):
        self.task = task
        self.filenames = filenames
        self.score = score
        self.public_score = public_score
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
                "Weird limits for unit test; strong limits should be > 1 "
                "and weak limits should be < 1")
        self.expected = expected

        # Check if the expected make sense
        for k in self.expected:
            try:
                float(k)
            except:
                if not k in ["time", "memory", "time?", "memory?", "any"]:
                    raise Exception("Unknown expected result '{}'".format(k))

        # Convert the given lists of expected events to something more
        # readable for ScoreTypes
        # Assume full score by default
        self.expected_by_case = {c.codename: "1.0" for c in self.task.cases}
        expectation__levels = {c.codename: -1 for c in self.task.cases}
        for key, items in self.expected.iteritems():
            for item in items:
                for c in item._get_cases():
                    if expectation__levels[c.codename] == item._level():
                        raise Exception(
                            "Multiple expected outcomes specified for "
                            "test case {}".format(c.codename))
                    elif expectation__levels[c.codename] < item._level():
                        self.expected_by_case[c.codename] = key
                        expectation__levels[c.codename] = item._level()

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
    :ivar saved: List of the saved (public) test cases

    This object is exported as a variable called :samp:`task`.
    """
    def __init__(self, upstream, rules, name, num, make_datasets,
                 ignore_latex=False):
        super(TaskConfig, self).__init__(rules, ignore_latex)
        Scope.__init__(self)

        if not os.path.exists("cases"):
            os.makedirs("cases")

        if not os.path.exists("subtasks"):
            os.makedirs("subtasks")

        self.upstream = upstream
        self.contest = upstream

        self.wdir = os.getcwd()

        self.name = name
        self.num = num

        self.make_datasets = make_datasets

        self.subtasks = []
        self.subtask_stack = []
        self.cases = []
        self.cases_by_codename = {}
        self.group_stack = []
        self.current_group = None
        self.output_generator = None
        self.testsubmissions = []
        self.attachments = {}
        self.managers = {}
        self.tasktype = None
        self.saved = []

        self.weak_time_limit = 2
        self.strong_time_limit = 0.5
        self.weak_mem_limit = 2
        self.strong_mem_limit = 0.5

        self.exported["task"] = self

        # utils
        self.exported["token_equ"] = self.upstream.token_equ_fp

        # Get data from upstream, but not the other way round
        self.inheriting = True
        self.bequeathing = False

    def _readconfig(self, filename):
        with header("Loading task {}".format(self.name), depth=2):
            super(TaskConfig, self)._readconfig(filename)

    # Supplement helpers

    def cpp_constraints(self):
        if self.current_group is None:
            return ""
        constraints = self.current_group._collect_constraints()
        s = "#define __constraints\n"
        s += '#include <checkutil.h>\n'
        s += "void load_constraints() {\n"
        for var, ran in constraints.iteritems():
            s += '\tput_constraint("{}", {}, {});\n'.format(var,
                                                            ran[0], ran[1])
        s += "}\n"
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
    def timelimit(self, s):
        """
        Set the time limit.

        s (float): time limit in seconds

        """
        self._timelimit = s

    def latex_timelimit(self):
        """
        Return the time limit in LaTeX format.

        return (string): LaTeX string
        """
        return "{}$\,$s".format(self._timelimit)

    @exported_function
    def memorylimit(self, s):
        """
        Set the memory limit.

        s (int): memory limit in MB

        """
        self._memorylimit = s

    def latex_memorylimit(self):
        """
        Return the memory limit in LaTeX format.

        return (string): LaTeX string
        """
        return "{}$\,$MB".format(self._memorylimit)

    @exported_function
    def statement(self, s):
        """
        Set the task statement.

        s (string): file name of the (compiled) task statement

        """
        self._statement = os.path.abspath(s)

    @exported_function
    def attachment(self, localname, publicname):
        """
        Add an attachment.

        localname (string): name of the file to add

        publicname (string): file name displayed in CMS

        """
        self.attachments[publicname] = os.path.abspath(localname)

    """
    **Task types**
    """

    @exported_function
    def batch(self, input='', output='', comparator=None, library=False):
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
                        interface.{c,cpp,pas} and, if existent, taskname.h
                        and tasknamelib.pas.

        """
        self.tasktype = "Batch"
        grader_param = "alone"
        if library:
            grader_param = "grader"
            for end in ["c", "cpp", "pas"]:
                self.managers["grader."+end] = \
                    os.path.join(self.wdir, "interface."+end)
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
        self.tasktypeparameters = json.dumps([grader_param,
                                              [input, output],
                                              evaluation_param])

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
        self.tasktypeparameters = json.dumps([evaluation_param])

    @exported_function
    def communication(self, manager):
        """
        Specify this to be a communication task.

        manager (CPPProgram): executable communicating with the contestant
                              submissions
                              (must at least implement get_path() to get
                              the file name of the executable)

        Submissions are linked together with interface.{c,cpp,pas}.

        """
        self.tasktype = "Communication"
        some = False
        all = True
        for end in ["c", "cpp", "pas"]:
            interfacefile = os.path.join(self.wdir, "interface."+end)
            if os.path.exists(interfacefile):
                some = True
                self.managers["stub."+end] = interfacefile
            else:
                all = False
        if some != all:
            print_msg("There are stubs for some but not all languages",
                      warning=True, headerdepth=10)
        self.managers["manager"] = manager.get_path()
        self.tasktypeparameters = json.dumps([])

    @exported_function
    def output_generator(self, s):
        """
        Set the output file generator.

        s (Executable): the output generator
                        (stdin is redirected from the test case input,
                        the expected output should be written to stdout)

        """
        print_msg("Registered global solution {}".format(s), headerdepth=10)
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
        codename = "%.04d" % (len(self.cases)+1)

        with header("Generating test case {}".format(codename), depth=5):
            case = MyCase(self, codename)

            prog(stdout=case.infile)

            if self.output_generator is None:
                raise Exception(
                    "You must specify an output generator before a test case")
            self.output_generator(stdin=case.infile, stdout=case.outfile)
            self.cases.append(case)
            self.cases_by_codename[codename] = case
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
        return self.encapsulate(f)

    @exported_function
    def subtask(self, description, name=None, public=False):
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

        public (bool): whether this subtask is public (displayed to the
                       contestant during the contest without token usage);
                       detailed feedback subtasks should usually be marked
                       public

        return (MySubtask): object representing the created subtask

        """
        if name is None:
            name = "s" + str(len(self.subtasks))

        subtask = MySubtask(self, description, name, public)

        self.subtasks.append(subtask)

        if hasattr(self, name):
            raise Exception("The task already has an attribute "
                            "called '{}'".format(name))
        setattr(self, name, subtask)

        return subtask

    @exported_function
    def group(self, *args, **kwargs):
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
        return self.subtask_stack[-1].group(*args, **kwargs)

    @exported_function
    def checker(self, *args, **kwargs):
        """
        Register a test case checker for the "current" task, subtask or group.

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
    def add_testcase(self, *args, **kwargs):
        """
        Add a test case to the "current" group.

        See
        :py:meth:`cmscontrib.gerpythonformat.TaskConfig.MyGroup.add_testcase`.

        You usually use this function in the following way:
        ::
            with subtask("Subtask 1", "small"):
                with group(50):
                    add_testcase(...)
        """
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
        if len(self.group_stack) == 0:
            raise Exception("testcase() called outside group")
        return self.group_stack[-1].testcase(*args, **kwargs)

    def _check(self, checker, infile, outfile, caseno, check_counter):
        try:
            checker(outfile, stdin=infile, dependencies=[outfile])
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
    def generate_feedback(self, description_suffix=" (Detailed Feedback)",
                          name_suffix="_feedback"):
        """
        Generate detailed feedback subtasks for all subtasks generated
        so far (that contain at least one test case marked for detailed
        feedback).

        description_suffix (string): this string will be appended to the
                                     description of the subtask to obtain the
                                     description of the detailed feedback
                                     subtask

        name_suffix (string): this string will be appended to the
                              name of the subtask to obtain the
                              name of the detailed feedback subtask

        """
        for s in self.subtasks:
            s.put_feedback(s.description + description_suffix,
                           s.name + name_suffix)

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

        score (float): the expected official (private) score

        public_score (float): the expected public score

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
        print_msg("Added test submission {}"
                  .format([self.contest.short_path(s) for s in args]),
                  headerdepth=10)
        self.testsubmissions.append(
            MySubmission(self, [os.path.abspath(s) for s in args], **kwargs))

    def _printresult(self):
        with header("Statistics", depth=3):
            print_msg("Taskname: {}".format(self.name))
            print_msg("Task statement in file {}"
                      .format(self.short_path(self._statement)))
            print_msg("Number of subtasks: {}".format(len(self.subtasks)))
            print_msg("Number of test cases: {}".format(len(self.cases)))

    def _makesavedzip(self):
        """
        Create and add an attachment containing the saved test cases.
        """
        zipname = os.path.join(self.wdir, "savedcases.zip")
        contents = {}
        for i, c in enumerate(self.saved):
            contents["%d.in" % (i+1)] = c.infile
            contents["%d.out" % (i+1)] = c.outfile
        ZipRule(self.rules, zipname, contents).ensure()
        self.attachment(zipname, "%s.zip" % self.name)

    def _makeinputzip(self):
        """
        Create and add an attachment containing the input files (mostly
        for output-only tasks).
        """
        zipname = os.path.join(self.wdir, "inputs.zip")
        contents = {}
        for c in self.cases:
            contents["input_{}.txt".format(c.codename)] = c.outfile
        ZipRule(self.rules, zipname, contents).ensure()
        self.attachment(zipname, "%s_input.zip" % self.name)

    def short_path(self, f):
        """
        Return a (possibly) shorter name for a file (which can be relative
        to the contest build directory).

        f (string): file name to shorten

        return (string): shortened file name

        """
        return self.contest.short_path(f)

    def _makedbobject(self, file_cacher, local_test):
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
        # Automatically make a ZIP file containing the save test cases
        self._makesavedzip()
        if self.tasktype == "OutputOnly":
            self._makeinputzip()
        self.file_cacher = file_cacher
        if self.tasktype is None:
            raise Exception("You have to specify a task type")
        tdb = Task(name=self.name,
                   title=self._title,
                   num=self.num)
        tdb.token_initial = self.token_initial
        tdb.token_max = self.token_max
        tdb.token_total = self.token_total
        tdb.token_min_interval = self.token_min_interval
        tdb.token_gen_time = self.token_gen_time
        tdb.token_gen_number = self.token_gen_number
        tdb.max_submission_number = self.max_submission_number
        tdb.min_submission_interval = self.min_submission_interval
        tdb.max_user_test_number = self.max_user_test_number
        tdb.min_user_test_interval = self.min_user_test_interval

        if self.tasktype == "OutputOnly":
            tdb.submission_format = [
                SubmissionFormatElement("output_%s.txt" % c.codename)
                for c in self.cases]
        else:
            tdb.submission_format = [
                SubmissionFormatElement("%s.%%l" % self.name)]
        tdb.primary_statements = "[\"\"]"
        tdb.attachments = []
        tdb.statements = []
        digest = file_cacher.put_file_from_path(
            self._statement,
            "Statement task %s" % (self.name))
        tdb.statements[""] = Statement(language="", digest=digest)

        # Add attachments
        for name, file in self.attachments.iteritems():
            digest = file_cacher.put_file_from_path(
                file,
                "Attachment %s to task %s" % (name, self.name))
            tdb.attachments[name] = Attachment(filename=name, digest=digest)

        if self.make_datasets:
            ddb = self._makedataset(file_cacher)
            ddb.task = tdb
            tdb.active_dataset = ddb

        # Test submissions
        for s in self.testsubmissions:  # submissions are saved because they
                                        # are referenced through the user
                                        # object
            sdb = self._makesubmission(s, self.upstream.testuser, tdb)
            sdb.task_id = 0  # dummy id, the correct value is inserted by
                             # GerImporter.py

            if s._should_test(local_test):
                sdb.id = 1
                with header("Running solution {}"
                            .format(", ".join(self.short_path(f)
                                              for f in s.filenames)),
                            depth=3):
                    self._do_test_submission(sdb, ddb)

        return tdb

    def _makedataset(self, file_cacher):
        ddb = Dataset(description="imported",
                      task_type=self.tasktype,
                      task_type_parameters=self.tasktypeparameters,
                      score_type="SubtaskGroup",
                      score_type_parameters=json.dumps(
                          [{'name': s.description,
                            'public': s.public,
                            'groups': [{'points': g.points,
                                        'cases': [c.codename for c in g.cases]}
                                       for g in s.groups]}
                           for s in self.subtasks]),
                      time_limit=float(self._timelimit),
                      memory_limit=self._memorylimit
                      )

        # Add test cases
        for c in self.cases:
            input_digest = file_cacher.put_file_from_path(
                os.path.join(self.wdir, c.infile),
                "Input %s for task %s" % (c.codename, self.name))
            output_digest = file_cacher.put_file_from_path(
                os.path.join(self.wdir, c.outfile),
                "Output %s for task %s" % (c.codename, self.name))
            tcdb = None
            tcdb = Testcase(codename=c.codename,
                            input=input_digest,
                            output=output_digest,
                            public=c.public)
            ddb.testcases[c.codename] = tcdb

        # Add managers
        for name, file in self.managers.iteritems():
            digest = file_cacher.put_file_from_path(
                file,
                "Manager %s for task %s" % (name, self.name))
            ddb.managers[name] = Manager(filename=name, digest=digest)

        return ddb

    def _makesubmission(self, submission, user, tdb):
        """
        Create and return a test submission database object.

        submission (MySubmission): configuration object for this submission

        user (User): database object for the test user

        tdb (Task): database object for the task

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
        required = set([sfe.filename for sfe in tdb.submission_format])
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
        def which_language(user_filename):
            """Determine the language of user_filename from its
            extension.

            user_filename (string): the file to test.
            return (string): the extension of user_filename, or None
                             if it is not a recognized language.

            """
            for source_ext, language in SOURCE_EXT_TO_LANGUAGE_MAP.iteritems():
                if user_filename.endswith(source_ext):
                    return language
            return None

        for user_filename in files:
            if len(files) == 1:
                our_filename = list(required)[0]
            else:
                our_filename = user_filename
            if our_filename.find(".%l") != -1:
                lang = which_language(user_filename)
                if lang is None:
                    raise Exception("Cannot recognize submission's language.")
                elif submission_lang is not None and \
                        submission_lang != lang:
                    raise Exception(
                        "All sources must be in the same language.")
                else:
                    submission_lang = lang

        # Create submission object
        sdb = Submission(datetime.utcnow(),
                         submission_lang,
                         user=user)
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
                "Submission file %s sent by %s at %d." %
                (our_filename, user.username,
                    make_timestamp(sdb.timestamp)))
            sdb.files[our_filename] = File(our_filename, digest,
                                           submission=sdb)

        # Unit tests
        def m_abs(rel):
            return max(int(rel * self._memorylimit), 1)

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
             "expected": submission.expected_by_case,
             "expected_score": submission.score,
             "expected_public_score": submission.public_score,
             "task_name": self.name})

        return sdb

    def _do_test_submission(self, sdb, ddb):
        """
        Test the given submission.

        sdb (Submission): database object for the submission

        ddb (Dataset): database object for the data set

        """
        additional_info = json.loads(sdb.additional_info)
        limits = additional_info["limits"]

        submission_result = SubmissionResult(submission=sdb,
                                             dataset=ddb)
        # Compile
        compile_job_group = \
            JobGroup.from_submission_compilation(sdb, ddb)
        self._run_job_group(compile_job_group)
        compile_job_group.to_submission_compilation(submission_result)
        if submission_result.compilation_outcome != "ok":
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
            evaluation_job_group = \
                JobGroup.from_submission_evaluation(sdb,
                                                    ddb,
                                                    submission_result)
            self._run_job_group(evaluation_job_group)
            evaluation_job_group.to_submission_evaluation(submission_result)
            for ev in sorted(submission_result.evaluations,
                             key=lambda ev: ev.testcase.codename):
                with header("Test case {}"
                            .format(
                                self.cases_by_codename[ev.testcase.codename]),
                            depth=4):
                    outcome = float(ev.outcome)
                    verdict = format_status_text(ev.text).strip()
                    if self.tasktype == "OutputOnly":
                        print_msg("Outcome: %.1f   Verdict: %s" %
                                  (outcome,
                                   verdict))
                    else:
                        print_msg("Time: %5.3f   Wall: %5.3f   "
                                  "Memory: %s   Outcome: %.1f   Verdict: %s" %
                                  (ev.execution_time,
                                   ev.execution_wall_clock_time,
                                   mem_human(ev.execution_memory),
                                   outcome,
                                   verdict))
                    expected = \
                        additional_info["expected"][ev.testcase.codename]
                    accepted, result = unit_test_compare(limits, expected, ev)
                    if accepted:
                        print_msg("Accepted (wanted {}, got {})"
                                  .format(expected, "|".join(result)))
                    else:
                        print_msg("Not accepted (wanted {}, got {})"
                                  .format(expected, "|".join(result)),
                                  error=True)
                    for r in result:
                        if r.endswith("?"):
                            print_msg("Warning: Unclear result: {}".format(r),
                                      warning=True)

        # Assign score to the submission.
        score_type = get_score_type(dataset=ddb)
        score, details, public_score, public_details, ranking_details = \
            score_type.compute_score(submission_result)
        print_msg("Score: %.1f" % score)
        print_msg("Public score: %.1f" % public_score)
        expected_score = float(additional_info["expected_score"])
        expected_public_score = float(additional_info["expected_public_score"])
        if score != expected_score:
            print_msg("Wrong score (expected {}, got {})"
                      .format(expected_score, score), error=True)
        if public_score != expected_public_score:
            print_msg("Wrong public score (expected {}, got {})"
                      .format(expected_public_score, public_score), error=True)

    def _run_job_group(self, job_group):
        """
        Run the given job group and save the results to it.

        job_group (JobGroup): the job group

        """
        for k in job_group.jobs.keys():
            job = job_group.jobs[k]
            job._key = k  # Hack for output-only tasks
            r = JobRule(self.rules, job, self.file_cacher).ensure()
            job = r.job
            job_group.jobs[k] = job
            if not job.success:
                job_group.success = False
                break
        else:
            job_group.success = True
