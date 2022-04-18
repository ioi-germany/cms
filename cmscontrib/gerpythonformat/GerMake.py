#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2021 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2016 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2021 Manuel Gundlach <manuel.gundlach@gmail.com>
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

from cmscontrib.gerpythonformat.ContestConfig import ContestConfig
from cmscontrib.gerpythonformat.LocationStack import chdir
from cms import utf8_decoder
from cms.db.filecacher import FileCacher
from cmscontrib.gerpythonformat import copyrecursivelyifnecessary
import argparse
import os
import resource
import shutil

from psutil import virtual_memory

class GerMake:
    def __init__(self, odir, task, minimal, no_test,
                 submission, no_latex, safe_latex, language, clean):
        self.odir = odir
        self.task = task
        self.minimal = minimal
        self.local_test = not no_test
        if self.local_test and submission is not None:
            self.local_test = submission
        self.no_latex = no_latex
        self.safe_latex = safe_latex
        self.language = language
        self.clean = clean

    def prepare(self):
        # Unset stack size limit
        INFTY = int(.75 * virtual_memory().total)
        resource.setrlimit(resource.RLIMIT_STACK, (INFTY, INFTY))

        if not os.path.exists(os.path.join(self.odir, "contest-config.py")):
            raise Exception("Directory doesn't contain contest-config.py")
        self.wdir = os.path.join(self.odir, "build")
        if self.clean:
            shutil.rmtree(self.wdir)
        if not os.path.exists(self.wdir):
            os.mkdir(self.wdir)
        # We have to avoid copying the folder contest/build
        # or contest/task/build into contest/build.
        # For this reason, we ignore all files and directories named "build"
        # when copying recursively.
        copyrecursivelyifnecessary(self.odir, self.wdir, set(["build"]))
        self.wdir = os.path.abspath(self.wdir)

    def build(self, extra_conf_f=None):
        file_cacher = FileCacher(path=os.path.join(self.wdir, ".cache"))
        with chdir(self.wdir):
            contestconfig = ContestConfig(
                os.path.join(self.wdir, ".rules"),
                os.path.basename(self.odir),
                relevant_language=(self.language if self.language!="ALL" else None),
                ignore_latex=self.no_latex,
                onlytask=self.task,
                safe_latex=self.safe_latex,
                minimal=self.minimal)

            if extra_conf_f:
                extra_conf_f(contestconfig)
            print(contestconfig.users)

            contestconfig._readconfig("contest-config.py")
            if self.task not in (None, "NO_TASK") and len(contestconfig.tasks) == 0:
                raise Exception("Task {} not found".format(self.task))

            if not self.minimal:
                cdb = contestconfig._makecontest()
                test_udb = contestconfig._makeuser(
                    contestconfig._mytestuser.username)
                test_gdb = contestconfig._makegroup(
                    contestconfig._mytestuser.group.name, cdb)
                # We're not putting the test user on any team for testing
                # (shouldn't be needed).
                test_pdb = contestconfig._makeparticipation(
                    contestconfig._mytestuser.username, cdb,
                    test_udb, test_gdb, None)
                for t in contestconfig.tasks.values():
                    tdb = t._makedbobject(cdb, file_cacher)
                    t._make_test_submissions(test_pdb, tdb, self.local_test)

        contestconfig.finish()

        taskvalues = list(contestconfig.tasks.values())
        if not taskvalues:
            return None
        statements = taskvalues[0]._statements

        if self.language == "ALL":
            return [os.path.abspath(s.file_) for s in list(statements.values())]

        if self.language is not None:
            if self.language in statements:
                return os.path.abspath(statements[self.language].file_)
            else:
                return None

        primary_statements = [s for s in list(statements.values()) if s.primary]
        if len(primary_statements) == 0:
            return None
        elif len(primary_statements) == 1:
            return os.path.abspath(primary_statements[0].file_)
        else:
            raise Exception("More than one primary statement")

    def make(self):
        self.prepare()
        self.build()

def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(
        description="Prepare a contest (generate test cases, statements, test "
                    "test submissions, ...)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("import_directory",
                        help="source directory",
                        type=utf8_decoder)
    parser.add_argument("-m", "--minimal", action="store_true",
                        help="attempt to only compile statement(s) (and "
                        "everything required for this, e.g. sample cases)")
    parser.add_argument("-t", "--task", action="store",
                        help="omit all tasks except this one",
                        type=utf8_decoder)
    testgroup = parser.add_mutually_exclusive_group()
    testgroup.add_argument("-nt", "--no-test", action="store_true",
                           help="do not run test submissions")
    testgroup.add_argument("-s", "--submission",
                           help="only test submissions whose file names all "
                           "contain this string",
                           type=utf8_decoder)
    parser.add_argument("-nl", "--no-latex", action="store_true",
                        help="do not compile latex documents")
    parser.add_argument("-sl", "--safe-latex", action="store_true",
                        help="Safely compile latex documents in a sandbox")
    parser.add_argument("-l", "--language",
                        help="only compile latex files that end in this string",
                        type=utf8_decoder)
    parser.add_argument("-c", "--clean", action="store_true",
                        help="clean the build directory (forcing a complete "
                        "rebuild)")

    args = parser.parse_args()

    GerMake(os.path.abspath(args.import_directory),
            args.task,
            args.minimal,
            args.no_test,
            args.submission,
            args.no_latex,
            args.safe_latex,
            args.language,
            args.clean).make()


if __name__ == "__main__":
    main()
