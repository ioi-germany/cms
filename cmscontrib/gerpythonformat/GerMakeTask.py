#!/usr/bin/env python2
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

from .ContestConfig import ContestConfig
from .LocationStack import chdir
from cms import utf8_decoder
from cms.db.filecacher import FileCacher
from cmscontrib.gerpythonformat import copyrecursivelyifnecessary, \
                                       copyifnecessary
import argparse
import os
import resource
import shutil


class GerMakeTask:
    def __init__(self, odir, task, minimal, submission, clean):
        self.odir = odir
        self.task = task
        self.minimal = minimal
        self.submission = submission
        self.clean = clean

    def make(self):
        # Unset stack size limit
        resource.setrlimit(resource.RLIMIT_STACK, (resource.RLIM_INFINITY,
                                                   resource.RLIM_INFINITY))

        self.wdir = os.path.join(self.odir, "build")

        if self.clean:
            shutil.rmtree(self.wdir)

        if not os.path.exists(self.wdir):
            os.mkdir(self.wdir)
        
        taskdir = os.path.join(self.odir, self.task)
        wtdir = os.path.join(self.wdir, self.task)
        
        copyrecursivelyifnecessary(taskdir, wtdir, set([self.wdir]))
        self.wdir = os.path.abspath(self.wdir)
        filecacher = FileCacher(path=os.path.join(self.wdir, ".cache"))
        
        try:
            with chdir(self.wdir):
                cc = ContestConfig(os.path.join(self.wdir, ".rules"),
                                   "hidden contest", minimal=self.minimal)
                copyifnecessary(os.path.join(cc._get_ready_dir(),
                                             "contest-template.py"),
                                os.path.join(self.wdir, "c.py"))
                cc._readconfig("c.py")
                cc._task(self.task, cc._dummy_feedback, self.minimal)

                if not self.minimal:
                    cc._makecontest()
                    for u in cc.users: cc._makeuser(u.username)
                    cc._maketask(filecacher, self.task, local_test=(True if self.submission is None else self.submission))

        finally:
            filecacher.destroy_cache()

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
    parser.add_argument("-s", "--submission",
                           help="only test submissions whose file names all"
                           "contain this string",
                           type=utf8_decoder)
    parser.add_argument("-c", "--clean", action="store_true",
                        help="clean the build directory (forcing a complete "
                        "rebuild)")

    args = parser.parse_args()

    full_dir = os.path.abspath(args.import_directory)
    source_dir, task = os.path.split(full_dir)

    GerMakeTask(source_dir, task, args.minimal, args.submission, args.clean).make()


if __name__ == "__main__":
    main()
