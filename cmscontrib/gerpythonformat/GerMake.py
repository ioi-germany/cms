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

from __future__ import print_function
from __future__ import unicode_literals

from ContestConfig import ContestConfig
from LocationStack import chdir
from cms import utf8_decoder
from cms.db.filecacher import FileCacher
from cmscontrib.gerpythonformat import copyrecursivelyifnecessary
import argparse
import os
import shutil


class GerMake:
    def __init__(self, odir, task, no_test, submission, no_latex, clean):
        self.odir = odir
        self.task = task
        self.local_test = not no_test
        if self.local_test and submission is not None:
            self.local_test = submission
        self.no_latex = no_latex
        self.clean = clean

    def make(self):
        if not os.path.exists(os.path.join(self.odir, "contest-config.py")):
            raise Exception("Directory doesn't contain contest-config.py")
        self.wdir = os.path.join(self.odir, "build")
        if self.clean:
            shutil.rmtree(self.wdir)
        if not os.path.exists(self.wdir):
            os.mkdir(self.wdir)
        copyrecursivelyifnecessary(self.odir, self.wdir, set([self.wdir]))
        self.wdir = os.path.abspath(self.wdir)
        filecacher = FileCacher(path=os.path.join(self.wdir, ".cache"))
        try:
            with chdir(self.wdir):
                contestconfig = ContestConfig(
                    os.path.join(self.wdir, ".rules"),
                    os.path.basename(self.odir),
                    ignore_latex=self.no_latex,
                    onlytask=self.task)
                contestconfig._readconfig("contest-config.py")
                if self.task is not None and \
                        not any(True for t in contestconfig.tasks):
                    raise Exception("Task {} not found".format(self.task))
                contestconfig._makecontest()
                for u in contestconfig.users:
                    contestconfig._makeuser(u.username)
                for t in contestconfig.tasks:
                    contestconfig._maketask(filecacher, t.name,
                                            local_test=self.local_test)
        finally:
            filecacher.destroy_cache()


def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(
        description="Prepare a task (generate test cases, statements, test "
                    "test submissions, ...)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("import_directory",
                        help="source directory",
                        type=utf8_decoder)
    parser.add_argument("-t", "--task", action="store",
                        help="omit all tasks except this one",
                        type=utf8_decoder)
    testgroup = parser.add_mutually_exclusive_group()
    testgroup.add_argument("-nt", "--no-test", action="store_true",
                           help="do not run test submissions")
    testgroup.add_argument("-s", "--submission",
                           help="only test submissions whose file names all"
                           "contain this string",
                           type=utf8_decoder)
    parser.add_argument("-nl", "--no-latex", action="store_true",
                        help="do not compile latex documents")
    parser.add_argument("-c", "--clean", action="store_true",
                        help="clean the build directory (forcing a complete"
                        "rebuild)")

    args = parser.parse_args()

    GerMake(os.path.abspath(args.import_directory),
            args.task,
            args.no_test,
            args.submission,
            args.no_latex,
            args.clean).make()


if __name__ == "__main__":
    main()
