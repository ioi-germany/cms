#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2016-2021 Tobias Lenz <t_lenz94@web.de>
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
from multiprocessing import Process, Manager
from six import StringIO
from ansi2html import Ansi2HTMLConverter

from cms.io.TaskInfo import TaskInfo

from cmscontrib.gerpythonformat.GerMakeTask import GerMakeTask


logger = logging.getLogger(__name__)


class TaskCompileJob:
    def __init__(self, repository, name, balancer):
        self.repository = repository
        self.name = name
        self.balancer = balancer

        self.current_handle = 1
        self.backup_handle = 0
        self.backup = None
        self.idle = False

        self._compile()

    def join(self):
        self._update()

        if self.idle:
            self.current_handle += 1
            self._compile()
        return self.current_handle

    def _compile(self):
        self._reset_status()
        logger.info("loading task {} in {}".format(self.name,
                                                   self.repository.path))

        def do(status, repository, balancer):
            # stdout is process local in Python, so we can simply use this
            # to redirect all output from GerMakeTask to a string
            sys.stdout = StringIO()

            C = Ansi2HTMLConverter()

            with balancer:
                try:
                    comp = GerMakeTask(repository.path, self.name, True, True,
                                       None, False, None, False)

                    with repository:
                        comp.prepare()

                    statement_file = comp.build()

                    if statement_file is None:
                        status["error"] = True
                        status["msg"] = "No statement found"

                    else:
                        result = None

                        with open(statement_file, "rb") as f:
                            result = f.read()

                        status["result"] = result

                except Exception:
                    status["error"] = True
                    status["msg"] = \
                        C.convert("\n".join(format_exception(*exc_info())))

            sys.stdout.flush()
            status["log"] = C.convert(sys.stdout.getvalue())
            status["done"] = True

        self.compilation_process = Process(target=do, args=(self.status,
                                                            self.repository,
                                                            self.balancer))
        self.compilation_process.daemon = True
        self.compilation_process.start()

    def _update(self):
        if self.status["done"]:
            logger.info("Finished compilation of task {}:\n\n{}".
                        format(self.name, self.status["log"]))

            self.backup = {}
            self.backup.update(self.status)
            self.backup_handle = self.current_handle

            # Release Manager subprocess for status
            self.compilation_process.join()
            del self.compilation_process

            del self.status
            self.status = {"error":  False,
                           "done":   False,
                           "result": None,
                           "msg":    "Okay",
                           "log":    ""}
            self.idle = True

    def _reset_status(self):
        self.status = Manager().dict()
        self.status.update({"error":  False,
                            "done":   False,
                            "result": None,
                            "msg":    "Okay",
                            "log":    ""})
        self.idle = False

    def info(self, handle):
        self._update()

        if handle > self.current_handle:
            return {"error": True,
                    "done":  True,
                    "msg":   "I couldn't find your compile job. Usually this "
                             "means that the server has been restarted in the"
                             "meantime. Please try again.",
                    "log":   ""}

        return {"error": self._choose(handle, "error"),
                "done":  self._choose(handle, "done"),
                "msg":   self._choose(handle, "msg"),
                "log":   self._choose(handle, "log")}

    def _choose(self, handle, key):
        return self.backup[key] if handle <= self.backup_handle else \
            self.status[key]

    def get(self):
        self._update()
        # this will always be the most current one
        return self.backup["result"]


class TaskFetch:
    jobs = {}
    repository = None
    balancer = None

    @staticmethod
    def init(repository, max_compilations):
        logger.info("initializing task compilation in directory {}.".
                    format(repository.path))

        TaskFetch.repository = repository
        TaskFetch.balancer = Manager().BoundedSemaphore(max_compilations)

    @staticmethod
    def compile(name):
        if name not in TaskInfo.tasks:
            raise KeyError("No such task")
        if name not in TaskFetch.jobs:
            TaskFetch.jobs[name] = TaskCompileJob(TaskFetch.repository, name,
                                                  TaskFetch.balancer)
        return TaskFetch.jobs[name].join()

    @staticmethod
    def query(name, handle):
        if name not in TaskFetch.jobs:
            return {"error": True,
                    "done":  True,
                    "msg":   "I couldn't find your compile job. Usually this "
                             "means that the server has been restarted in the "
                             "meantime. Please try again.",
                    "log":   ""}

        return TaskFetch.jobs[name].info(handle)

    @staticmethod
    def get(name):
        return TaskFetch.jobs[name].get()
