#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013 Fabian Gundlach <320pointsguy@gmail.com>
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

import os
import os.path

from cmscontrib.BaseLoader import Loader
from cmscontrib.gerpythonformat import copyrecusivelyifnecessary
from LocationStack import chdir
from ContestConfig import ContestConfig


class GerLoader(Loader):
    """Load a contest stored using the German IOI format.

    Given the filesystem location of a contest saved in the German IOI
    format, parse those files and directories to produce data that can
    be consumed by CMS, i.e. a hierarchical collection of instances of
    the DB classes, headed by a Contest object, and completed with all
    needed (and available) child objects.

    """

    short_name = 'german'
    description = 'German format'

    def __init__(self, path, file_cacher):
        super(GerLoader, self).__init__(path, file_cacher)

    @classmethod
    def detect(cls, path):
        """See docstring in class Loader.

        """
        # TODO - Not really refined...
        return os.path.exists(os.path.join(path, "contest-config.py"))

    def get_contest(self):
        """See docstring in class Loader.

        """
        self.buildpath = os.path.join(os.path.dirname(self.path),
                                      os.path.basename(self.path), "build")
        copyrecusivelyifnecessary(self.path, self.buildpath,
                                  set([self.buildpath]))
        with chdir(self.buildpath):
            rules = ".rules"
            if not os.path.exists(rules):
                os.mkdir(rules)
            rules = os.path.abspath(rules)
            self.contestconfig = ContestConfig(rules,
                                               os.path.basename(self.path))
            self.contestconfig._readconfig("contest-config.py")
            tasknames = [t.name for t in self.contestconfig.tasks]
            usernames = [u.username for u in self.contestconfig.users]
            return self.contestconfig._makecontest(), tasknames, usernames

    def has_changed(self, name):
        """See docstring in class Loader

        """
        # TODO Do something here
        return True

    def get_user(self, username):
        """See docstring in class Loader.

        """
        return self.contestconfig._makeuser(username)

    def get_task(self, name):
        """See docstring in class Loader.

        """
        return self.contestconfig._maketask(self.file_cacher, name)
