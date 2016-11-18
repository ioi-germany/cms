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
import sys

from sys import exc_info
from traceback import format_exception
from multiprocessing import Process, Queue
from StringIO import StringIO
from copy import deepcopy

from cmscontrib.gerpythonformat.Messenger import disable_colors
from cmscontrib.gerpythonformat.GerMakeTask import GerMakeTask


logger = logging.getLogger(__name__)


class TaskCompileJob:
    def __init__(self, base_dir, name):
        self.status = { "error":  False,
                        "done":   False,
                        "result": None,
                        "msg":    "Okay",
                        "log":    "" };

        self.base_dir = base_dir
        self.name = name

        self.queue = Queue()
        self.current_handle = 1
        self.backup_handle = 0
        self.backup = None
        
        self._compile()
        
    def join(self):
        self._update()
    
        if self.status["done"]:
            self.current_handle += 1
            self._compile()
        return self.current_handle
            
    def _compile(self):
        logger.info("loading task {} in {}".format(self.name, self.base_dir))
        
        def do(queue):
            # stdout is process local in Python, so we can simply use this
            # to redirect all output from GerMakeTask to a string
            sys.stdout = StringIO()
                   
            # Remove color codes for the log file
            disable_colors()
                   
            try:
                statement_file = GerMakeTask(self.base_dir, self.name, True,
                                             False).make()
                
                if statement_file is None:
                    queue.put({ "error": True,
                                "msg":   "No statement found" })

                else:
                    result = None
                
                    with open(statement_file, "rb") as f:
                        result = f.read()
                    
                    queue.put({ "result": result })

            except Exception as error:
                queue.put({ "error": True,
                            "msg": "\n".join(format_exception(*exc_info())) })

            sys.stdout.flush()
            queue.put({ "log": sys.stdout.getvalue() })
            queue.put({ "done": True })
            queue.close()
            
        self.compilation_process = Process(target=do, args = (self.queue,))
        self.compilation_process.daemon = True
        self.compilation_process.start()
    
    def _update(self):
        while not self.queue.empty():
            self.status.update(self.queue.get(False))
        
        if self.status["done"]:
            self.backup = deepcopy(self.status)
            self.backup_handle = self.current_handle

    """ Various query methods for the status
    """
    def done(self, handle):
        self._update()
        return self._choose(handle, "done")
    
    def error(self, handle):
        self._update()
        return self._choose(handle, "error")
        
    def working(self, handle):
        return not self.done(handle)
    
    def msg(self, handle):
        self._update()
        return self._choose(handle, "msg")

    def log(self, handle):
        self._update()
        return self._choose(handle, "log")

    def get(self):
        self._update()
        return self.backup["result"] # this will always be the most current one
    
    def _choose(self, handle, key):
        return self.backup[key] if handle <= self.backup_handle else \
               self.status[key]


class TaskFetch:
    jobs = {}
    base_dir = None

    @staticmethod
    def init(base_dir):
        logger.info("initializing TaskFetch with base_dir={}".format(base_dir))
        TaskFetch.base_dir = base_dir

    @staticmethod
    def compile(name):
        if not name in TaskFetch.jobs:
            TaskFetch.jobs[name] = TaskCompileJob(TaskFetch.base_dir, name)
        return TaskFetch.jobs[name].join()

    @staticmethod
    def query(name, handle):
        return { "done":   TaskFetch.jobs[name].done(handle),
                 "error":  TaskFetch.jobs[name].error(handle),
                 "msg":    TaskFetch.jobs[name].msg(handle),
                 "log":    TaskFetch.jobs[name].log(handle) }

    @staticmethod
    def get(name):
        return TaskFetch.jobs[name].get()
