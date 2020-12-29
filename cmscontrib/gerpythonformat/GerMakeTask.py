#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2016 Tobias Lenz <t_lenz94@web.de>
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

from cmscontrib.gerpythonformat.ContestConfig import ContestConfig
from cmscontrib.gerpythonformat.LocationStack import chdir
from cms import utf8_decoder
from cms.db.filecacher import FileCacher
from cmscontrib.gerpythonformat import copyrecursivelyifnecessary, \
    copyifnecessary
import argparse
import os
import resource
import shutil

from psutil import virtual_memory


class GerMakeTask:
    def __init__(self, odir, task, minimal, no_test,
                 submission, no_latex, clean):
        self.odir = odir
        self.task = task
        self.minimal = minimal
        self.local_test = not no_test
        if self.local_test and submission is not None:
            self.local_test = submission
        self.no_latex = no_latex
        self.clean = clean

    def prepare(self):
        # Unset stack size limit
        INFTY = int(.75 * virtual_memory().total)
        resource.setrlimit(resource.RLIMIT_STACK, (INFTY, INFTY))

        self.wdir = os.path.join(self.odir, self.task, "build")

        if self.clean:
            shutil.rmtree(self.wdir)

        if not os.path.exists(self.wdir):
            os.mkdir(self.wdir)

        taskdir = os.path.join(self.odir, self.task)
        wtdir = os.path.join(self.wdir, self.task)

        # We have to avoid copying the folder task/build into itself.
        # For this reason, we ignore all files and directories named "build"
        # when copying recursively.
        copyrecursivelyifnecessary(taskdir, wtdir, set(["build"]))
        self.wdir = os.path.abspath(self.wdir)

    def build(self):
        file_cacher = FileCacher(path=os.path.join(self.wdir, ".cache"))

        with chdir(self.wdir):
            contestconfig = \
                ContestConfig(os.path.join(self.wdir, ".rules"),
                                "hidden contest", minimal=self.minimal)
            copyifnecessary(os.path.join(contestconfig._get_ready_dir(),
                                            "contest-template.py"),
                            os.path.join(self.wdir, "c.py"))
            contestconfig._readconfig("c.py")
            contestconfig._task(
                self.task, contestconfig.full_feedback, None, self.minimal)

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
                    t._make_test_submissions(
                        test_pdb, tdb, self.local_test)

        primary_statements = [s for s in list(list(contestconfig.tasks.values())[
            0]._statements.values()) if s.primary]
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
        description="Prepare a task (generate test cases, statements, test "
                    "test submissions, ...)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("import_directory",
                        help="directory where config.py is located",
                        type=utf8_decoder)
    parser.add_argument("-m", "--minimal", action="store_true",
                        help="attempt to only compile statement (and "
                        "everything required for this, e.g. sample cases)")
    testgroup = parser.add_mutually_exclusive_group()
    testgroup.add_argument("-nt", "--no-test", action="store_true",
                           help="do not run test submissions")
    testgroup.add_argument("-s", "--submission",
                           help="only test submissions whose file names all "
                           "contain this string",
                           type=utf8_decoder)
    parser.add_argument("-nl", "--no-latex", action="store_true",
                        help="do not compile latex documents")
    parser.add_argument("-c", "--clean", action="store_true",
                        help="clean the build directory (forcing a complete "
                        "rebuild)")

    args = parser.parse_args()

    full_dir = os.path.abspath(args.import_directory)
    source_dir, task = os.path.split(full_dir)

    GerMakeTask(source_dir,
                task,
                args.minimal,
                args.no_test,
                args.submission,
                args.no_latex,
                args.clean).make()


if __name__ == "__main__":
    main()
