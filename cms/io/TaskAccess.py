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
import sys

from pathlib import Path
from PyPDF2 import PdfFileMerger
from sys import exc_info
from traceback import format_exception
from multiprocessing import Process, Manager
from six import StringIO

from cms.io.TaskTranslateInfo import TaskTranslateInfo

from cmscontrib.gerpythonformat.Messenger import disable_colors
from cmscontrib.gerpythonformat.GerMakeTask import GerMakeTask
from cmscontrib.gerpythonformat import copyifnecessary


logger = logging.getLogger(__name__)

def unpack_code(code):
        if "/" in code:
            task,language = code.split("/")
        else:
            task,language = code,None

        if task not in TaskTranslateInfo.tasks:
            raise KeyError("No such task")
        if language not in TaskTranslateInfo.languages and language != "ALL":
            raise KeyError("No such language")

        return task,language

def repository_code(task,language):
        srcname = TaskTranslateInfo.tasks[task]["filename"]
        if language is not None:
            return Path(task) / (srcname+"-"+language+".tex")
        else:
            return Path(task) / srcname+".tex"

def repository_lock_file_code(task,language):
        if language is not None:
            return Path(task) / (language+".lock")
        else:
            return Path(task) / "O.lock"

class TaskCompileJob:
    def __init__(self, repository, name, balancer, language=None):
        self.repository = repository
        self.name = name
        self.balancer = balancer
        self.language = language

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

            # Remove color codes for the log file
            disable_colors()

            with balancer:
                try:
                    #TODO do this right, i.e.: Why copyifnecessary?
                    copyifnecessary(Path(self.repository.path) / "languages.json",
                                    Path(self.repository.path) / self.name / "languages.json")
                    comp = GerMakeTask(repository.path, self.name, True, True,
                                       None, False, self.language, False)

                    with repository:
                        comp.prepare()

                    #If self.language is None, this is the primary statement.
                    #If self.language is ALL, this is _a list_ of all statements.
                    #Else, it's the task statement associated with that language.
                    statement_file = comp.build()

                    if statement_file is None:
                        status["error"] = True
                        status["msg"] = "No statement found"

                    else:
                        result = None

                        if self.language == "ALL":
                            pdfmerger = PdfFileMerger()
                            for s in statement_file:
                                pdfmerger.append(s)
                            statement_file = str(Path(self.repository.path) / self.name / "build" / self.name / "statement-ALL.pdf")
                            pdfmerger.write(statement_file)
                            pdfmerger.close()

                        with open(statement_file, "rb") as f:
                            result = f.read()

                        status["result"] = result

                except Exception:
                    status["error"] = True
                    status["msg"] = "\n".join(format_exception(*exc_info()))

            sys.stdout.flush()
            status["log"] = sys.stdout.getvalue()
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


class TaskTeXYielder:
    def __init__(self, repository, name):
        self.repository = repository
        self.name = name

    def get(self):
        result = None#TODO

        task,language = unpack_code(self.name)
        _repository_code = repository_code(task,language)
        tex_file =  Path(self.repository.path) / _repository_code

        logger.info(str(_repository_code) + " was accessed.")

        if tex_file is None:
            #TODO Handle the error (you should probably implement a info function
            #like above, then implement a query function in TaskAccess
            #and handle the result in download.js
            error = "No statement TeX found"

        else:
            with open(tex_file, "rb") as f:
                result = f.read()

        return result


class TaskTeXReceiver:
    def __init__(self, repository, name):
        self.repository = repository
        self.name = name

    def receive(self, f):
        result = None

        task,language = unpack_code(self.name)
        _repository_code = repository_code(task,language)
        tex_file = Path(self.repository.path) / _repository_code

        _repository_lock_file_code = repository_lock_file_code(task,language)
        lock_file =  Path(self.repository.path) / _repository_lock_file_code
        if lock_file.is_file():
            #TODO Handle error
            error = "Translation already locked; currently, you can't change"\
            "this translation. Please contact an administrator."
            return

        logger.info(str(_repository_code) + " is written to.")

        if f is None:
            #TODO Handle the error (via result?)
            error = "No file received"

        else:
            with open(tex_file, "wb") as target_file:
                target_file.write(f)
            self.repository.commit(str(_repository_code))

        return result


class TaskMarker:
    def __init__(self, repository, name):
        self.repository = repository
        self.name = name

    def mark(self):
        task,language = unpack_code(self.name)
        _repository_lock_file_code = repository_lock_file_code(task,language)
        lock_file =  Path(self.repository.path) / _repository_lock_file_code

        logger.info(str(_repository_lock_file_code) + " is created.")

        with open(lock_file, "wb") as target_file:
            pass
        self.repository.commit(str(_repository_lock_file_code))


class TaskAccess:
    jobs = {}
    repository = None
    balancer = None

    @staticmethod
    def init(repository, max_compilations):
        logger.info("initializing task compilation in directory {}.".
                    format(repository.path))

        TaskAccess.repository = repository
        TaskAccess.balancer = Manager().BoundedSemaphore(max_compilations)

    @staticmethod
    def compile(name):
        task,language = unpack_code(name)

        if name not in TaskAccess.jobs:
            TaskAccess.jobs[name] = TaskCompileJob(TaskAccess.repository, task,
                                                  TaskAccess.balancer, language)
        return TaskAccess.jobs[name].join()

    @staticmethod
    def query(name, handle):
        if name not in TaskAccess.jobs:
            return {"error": True,
                    "done":  True,
                    "msg":   "I couldn't find your compile job. Usually this "
                             "means that the server has been restarted in the "
                             "meantime. Please try again.",
                    "log":   ""}

        return TaskAccess.jobs[name].info(handle)

    @staticmethod
    def get(name):
        return TaskAccess.jobs[name].get()

    @staticmethod
    def getTeX(name):
        return TaskTeXYielder(TaskAccess.repository, name).get()

    @staticmethod
    def receiveTeX(name, f):
        return TaskTeXReceiver(TaskAccess.repository, name).receive(f)

    @staticmethod
    def mark(name):
        return TaskMarker(TaskAccess.repository, name).mark()
