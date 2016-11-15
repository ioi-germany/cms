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

import logging

from threading import Thread
from time import sleep

from cmscontrib.gerpythonformat.GerMakeTask import GerMakeTask


logger = logging.getLogger(__name__)


class TaskCompileJob:
    def __init__(self, base_dir, name):
        logger.info("loading task {} in dir {}".format(name, base_dir))

        self._error = False
        self._done = False
        self.result = None
        
        def do():
            try:
                self.result = GerMakeTask(base_dir, name, True, False).make()
            except:
                self._error = True

            if self.result is None:
                self._error = True
            self._done = True            
            
        self.compile_thread = Thread(target=do)
        self.compile_thread.start()
    
    """ Various methods for the status
    """
    def done(self):
        return self._done
    
    def error(self):
        return self._error
        
    def working(self):
        return not self._done and not self._error
    
    def get(self):
        return self.result


class Loader:
    def __init__(self, base_dir):
        self.jobs = {}
        self.base_dir = base_dir
    
    def compile(self, name):
        # We won't compile the same task twice at the same time
        # (this would probably cause problems with programs overriding each
        # others output -- moreover, its inefficient)
        if self.working(name):
            logger.info("I already have a compile job for task {}".format(name))
            return

        logger.info("Got new compile job: {}".format(name))

        self.jobs[name] = TaskCompileJob(self.base_dir, name)

    """ Status queries for jobs
    """
    def working(self, name):
        try:
            return self.jobs[name].working()
        except:
            return False
    
    def done(self, name):
        try:
            return self.jobs[name].done()
        except:
            return False

    def error(self, name):
        try:
            return self.jobs[name].error()
        except:
            return True

    def get(self, name):
        try:
            return self.jobs[name].get()
        except:
            return None


class TaskFetch:
    loader = None

    @staticmethod
    def init(base_dir):
        if TaskFetch.loader is None:
            logger.info("initializing TaskFetch with base_dir={}".format(base_dir))
            TaskFetch.loader = Loader(base_dir)
        else:
            logger.error("there can be only one (call to TaskFetch.init)!")

    @staticmethod
    def compile(name):
        TaskFetch.loader.compile(name)

    @staticmethod
    def query(name):
        logger.info("querying {}".format(name))
        return { "done":   TaskFetch.loader.done(name),
                 "error":  TaskFetch.loader.error(name) }

    @staticmethod
    def get(name):
        logger.info("downloading statement for {}".format(name))
        return TaskFetch.loader.get(name)
