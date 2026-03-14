#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2016 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2020-2021 Manuel Gundlach <manuel.gundlach@gmail.com>
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
from typing import Optional

from cmscontrib.gerpythonformat.LocationStack import chdir


logger = logging.getLogger(__name__)


class Repository:
    """Class to synchronize all accesses to our task repository (from
    TaskInfo/TaskTranslateInfo and TaskFetch/TaskAccess and all
    the pulls necessary)

    You have to use one repository object for all of these!
    """

    def __init__(self, path, auto_sync=False, auto_push=False):
        self.lock = Manager().Lock()
        self.path = path
        self.pending_commits = False
        self.auto_sync = auto_sync
        self.auto_push = auto_push

    def __enter__(self):
        self.lock.acquire()
        if self.auto_sync:
            self._pull()

    def __exit__(self, type, value, traceback):
        if self.pending_commits and self.auto_push:
            self._push()
            self.pending_commits = False
        self.lock.release()

    def _pull(self):
        logger.info("Pulling {}".format(self.path))

        with chdir(self.path):
            gitout = ""

            try:
                gitout = check_output(["git", "pull"])
            except Exception as e:
                logger.error("Couldn't pull from repository ({})".format(e))
            else:
                logger.info("Finished pulling: {}".format(gitout))

    def _push(self):
        logger.info("Pushing {}".format(self.path))

        with chdir(self.path):
            gitout = ""

            try:
                gitout = check_output(["git", "push"])
            except Exception as e:
                logger.error("Couldn't push to repository ({})".format(e))
            else:
                logger.info("Finished pushing: {}".format(gitout))

    # For GerTranslate/cmsTaskOverview
    # TODO Show errors in web overview
    def commit(self, file_path, commit_message="", author="") -> Optional[str]:
        """Commits the changes in file_path as `author` with given `commit_message`.
        If an error occurs, the error message will be returned.

        """
        if commit_message == "" or author == "":
            raise Exception("Missing commit message or author")
        # TODO Only do this if it's a git repository
        # if self.auto_sync:
        logger.info("Committing {} in {}".format(file_path, self.path))

        with chdir(self.path):
            gitout = ""
            try:
                gitout = check_output(["git", "add", file_path])
            except Exception as e:
                logger.error("Couldn't add file to git staging area: {}".format(e))
                return str(e)
            try:
                gitout = ""
                # NOTE file_path is relative to self.path, which isn't
                # necessarily the root of the git repo. So the commit
                # message might be confusing.
                gitout = check_output(
                    [
                        "git",
                        "commit",
                        "-o",
                        file_path,
                        "-m",
                        commit_message,
                        "--author",
                        author,
                    ]
                )
                self.pending_commits = True
            except Exception as e:
                logger.error("Couldn't commit in repository: {}".format(e))
                try:
                    # try to unstage files if committing failed
                    check_output(["git", "restore", "--staged", file_path])
                except Exception as e:
                    logger.warning("unable to unstage files: {}".format(e))
                return str(e)
            logger.info("Committed: {}".format(gitout))

    # For GerTranslate
    # TODO Show errors in web overview
    def getlog(self, file_path):
        # TODO Only do this if it's a git repository
        # if self.auto_sync:
        with chdir(self.path):
            gitout = ""

            try:
                # TODO Remove diff info lines
                gitout = check_output(
                    [
                        "git",
                        "log",
                        "--pretty=format:Date:   %ci%n%n    %s%n",
                        "-p",
                        "--word-diff=color",
                        file_path,
                    ]
                )
            except Exception as e:
                logger.error("Couldn't get log: {}".format(e))
            else:
                gitout = gitout.decode("utf-8")
                return gitout
