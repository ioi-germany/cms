#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2016 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2020 Manuel Gundlach <manuel.gundlach@gmail.com>
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

import logging

from multiprocessing import Manager
from subprocess import check_output

from cmscontrib.gerpythonformat.LocationStack import chdir


logger = logging.getLogger(__name__)


class Repository:
    """ Class to synchronize all accesses to our task repository (from
        TaskInfo/TaskTranslateInfo and TaskFetch/TaskAccess and all
        the pulls necessary)

        You have to use one repository object for all of these!
    """

    def __init__(self, path, auto_sync=False):
        self.lock = Manager().Lock()
        self.path = path
        self.auto_sync = auto_sync

    def __enter__(self):
        self.lock.acquire()
        self._sync()

    def __exit__(self, type, value, traceback):
        self.lock.release()

    def _sync(self):
        if self.auto_sync:
            logger.info("Synchronizing {}".format(self.path))

            with chdir(self.path):
                gitout = ""

                try:
                    gitout = check_output(["git", "pull"])
                except:
                    logger.error("Couldn't sync with repository: " +
                                 "{}".format(gitout))
                else:
                    logger.info("Finished synchronization: " +
                                "{}".format(gitout))

                gitout = ""

                try:
                    gitout = check_output(["git", "push"])
                except:
                    logger.error("Couldn't push to repository: " +
                                 "{}".format(gitout))
                else:
                    logger.info("Finished pushing: " +
                                "{}".format(gitout))

    #For GerTranslate
    #TODO Show errors in web overview
    def commit(self, file_path):
        #TODO Only do this if it's a git repository
        #if self.auto_sync:
            logger.info("Committing {} in {}".format(file_path,self.path))

            with chdir(self.path):
                gitout = ""

                try:
                    gitout = check_output(["git", "add",
                                           file_path])
                except:
                    logger.error("Couldn't add file to git repository: " +
                                 "{}".format(gitout))
                else:
                    try:
                        #NOTE file_path is relative to self.path, which isn't
                        #necessarily the root of the git repo. So the commit message
                        #might be confusing.
                        gitout = check_output(["git", "commit",
                                            "-o", file_path,
                                            "-m","Changes to "+file_path+", uploaded via GerTranslate web interface",
                                            #TODO Provide meaningful commit message and author
                                            "--author","\"GerTranslate <GerTranslate@localhost>\""])
                    except:
                        logger.error("Couldn't commit in repository: " +
                                    "{}".format(gitout))
                    else:
                        logger.info("Committed: " +
                                    "{}".format(gitout))
