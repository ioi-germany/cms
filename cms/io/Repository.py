#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2016 Tobias Lenz <t_lenz94@web.de>
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

from multiprocessing import Manager
from subprocess import call

from cmscontrib.gerpythonformat.LocationStack import chdir

class Repository:
    """ Class to synchronize all accesses to our task repository (from TaskInfo
        and TaskFetch and all the pulls necessary)

        You have to use one repository object for all of these!
    """
    def __init__(self, path, auto_sync = False):
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
            print("Synchronizing {}".format(self.path))
        
            with chdir(self.path):
                call(["git", "pull"])