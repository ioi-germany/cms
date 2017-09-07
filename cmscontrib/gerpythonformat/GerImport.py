#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013 Tobias Lenz <t_lenz94@web.de>
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
from .CommonConfig import DatabaseProxyContest
from .LocationStack import chdir
from cms import utf8_decoder
from cms.db import SessionGen, Contest
from cms.db.filecacher import FileCacher
from cmscontrib.gerpythonformat import copyrecursivelyifnecessary
from cmscontrib import BaseImporter
import argparse
import os
import resource
import shutil
import logging

logger = logging.getLogger(__name__)


class GerImport(BaseImporter):
    def __init__(self, odir, clean):
        self.odir = odir
        self.clean = clean
        self.file_cacher = FileCacher()

    def make(self):
        # Unset stack size limit
        resource.setrlimit(resource.RLIMIT_STACK, (resource.RLIM_INFINITY,
                                                   resource.RLIM_INFINITY))

        if not os.path.exists(os.path.join(self.odir, "contest-config.py")):
            raise Exception("Directory doesn't contain contest-config.py")
        self.wdir = os.path.join(self.odir, "build")
        if self.clean:
            shutil.rmtree(self.wdir)
        if not os.path.exists(self.wdir):
            os.mkdir(self.wdir)
        copyrecursivelyifnecessary(self.odir, self.wdir, set([self.wdir]))
        self.wdir = os.path.abspath(self.wdir)
        with chdir(self.wdir):
            contestconfig = ContestConfig(
                os.path.join(self.wdir, ".rules"),
                os.path.basename(self.odir))
            contestconfig._readconfig("contest-config.py")
            #users = {}
            #participations = {}
            #tasks = {}
            #for u in contestconfig.users:
                #users[u.username], participations[u.username] = contestconfig._makeuser(u.username)
                #participations[u.username].contest = contest
            #for t in contestconfig.tasks:
                #tasks[t.name] = contestconfig._maketask(self.file_cacher, t.name)

            with SessionGen() as session:
                # Check whether the contest already exists
                old_contest = session.query(Contest) \
                                    .filter(Contest.name == contestconfig.contestname).first()
                if old_contest is not None:
                    old_contest = DatabaseProxyContest(old_contest)
                    logger.warning("Contest already exists")
                    #return

                contest = contestconfig._makecontest(old_contest)
                session.add(contest)

                session.commit()
                logger.info("Import finished (new contest id: %s).", contest.id)


def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(
        description="Import a contest (generate test cases, statements, test "
                    "test submissions, ...)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("import_directory",
                        help="source directory",
                        type=utf8_decoder)
    parser.add_argument("-c", "--clean", action="store_true",
                        help="clean the build directory (forcing a complete"
                        "rebuild)")

    args = parser.parse_args()

    GerImport(os.path.abspath(args.import_directory),
              args.clean).make()


if __name__ == "__main__":
    main()
