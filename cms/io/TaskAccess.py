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

import json
import logging
import sys

from pathlib import Path
from PyPDF2 import PdfFileMerger
from sys import exc_info
from traceback import format_exception
from multiprocessing import Process, Manager
from six import StringIO
from ansi2html import Ansi2HTMLConverter

from cms.io.TaskTranslateInfo import TaskTranslateInfo

from cmscontrib.gerpythonformat.ContestConfig import MyGroup
from cmscontrib.gerpythonformat.GerMake import GerMake
from cmscontrib.gerpythonformat import copyifnecessary


logger = logging.getLogger(__name__)


def unpack_code(code):
    if code.count("/") >= 2:
        contest, task, language = code.split("/")
    else:
        contest, task, language = [""] + code.split("/")

    if contest != "" and contest not in TaskTranslateInfo.contests:
        raise KeyError("No such contest")
    if task not in TaskTranslateInfo.tasks:
        raise KeyError("No such task")
    if language not in TaskTranslateInfo.languages and language != "ALL":
        raise KeyError("No such language")

    return contest, task, language


def repository_code(contest, task, language):
    srcname = TaskTranslateInfo.tasks[task]["filename"]
    p = Path(contest, task) if contest else Path(task)
    if language is not None:
        return p / (srcname+"-"+language+".tex")
    else:
        return p / srcname+".tex"


def repository_lock_file_code(contest, task, language):
    p = Path(contest, task) if contest else Path(task)
    if language is not None:
        return p / (language+".lock")
    else:
        return p / "O.lock"


class TaskCompileJob:
    def __init__(self, repository, contest, name, balancer, language=None):
        self.repository = repository
        self.contest = contest
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
            # to redirect all output from GerMake to a string
            sys.stdout = StringIO()

            C = Ansi2HTMLConverter()

            with balancer:
                try:
                    is_overview = self.name.endswith("overview")

                    lan_path = Path(self.repository.path) / "languages.json"

                    if not lan_path.exists():
                        i = {"error": "The languages.json file is missing."}
                    else:
                        try:
                            i = json.loads(lan_path.open().read())
                        except:
                            i = {
                                "error": "The languages.json file is corrupt."
                            }
                        else:
                            missing = []
                            for e in ["languages"]:
                                if e not in i:
                                    missing.append(e)

                            if len(missing) > 0:
                                i["error"] = \
                                    "Some important entries are missing: " + \
                                    ", ".join(missing) + "."

                    # TODO do this right, i.e.: Why copyifnecessary?
                    if is_overview:
                        copyifnecessary(lan_path,
                                        Path(self.repository.path) /
                                        self.contest /
                                        "languages.json"
                                        )

                    comp = \
                        GerMake(
                            repository.path + "/" + self.contest,
                            task=self.name if not is_overview else "NO_TASK",
                            no_test=True,
                            submission=None,
                            no_latex=False,
                            verbose_latex=True,
                            safe_latex=True,
                            language=self.language,
                            clean=False,
                            minimal=True,
                            ntcimp=True
                        )

                    with repository:
                        comp.prepare()

                        # TODO Kommentieren!
                        credentials_file = (Path(repository.path) /
                                            self.contest /
                                            "build" /
                                            "users.py"
                                            )
                        credentials_file.write_text('')
                        f = None
                        if is_overview:
                            if self.language == "ALL":
                                languages = i["languages"]
                            elif self.language is None:
                                raise NotImplementedError
                            else:
                                languages = [self.language]
                            print(languages)

                            def f(contestconfig):
                                for l in languages:
                                    contestconfig.user(
                                        "[user-{}]".format(l),
                                        "[password]",
                                        "Jane", "Doe",
                                        group=MyGroup(
                                            "dummy", 0, 0, 0, 0, None),
                                        primary_statements=[l]
                                    )

                    # If self.language is None, this is the primary statement.
                    # If self.language is ALL, this is _a list_ of all statements.
                    # Else, it's the task statement associated with that language.
                    pdf_file = comp.build(extra_conf_f=f)

                    if is_overview:
                        filename = \
                            "overview-sheets-for-{}.pdf".format(self.language)
                        pdf_file = str(Path(self.repository.path) /
                                       self.contest /
                                       "build" /
                                       "overview" /
                                       ".overviews-per-language" /
                                       filename
                                       )

                    if pdf_file is None:
                        status["error"] = True
                        status["msg"] = "No statement found"

                    else:
                        result = None

                        if self.language == "ALL":
                            pdfmerger = PdfFileMerger()
                            for s in pdf_file:
                                pdfmerger.append(s)
                            pdf_file = str(Path(self.repository.path) /
                                           self.contest /
                                           "build" /
                                           self.name /
                                           "statement-ALL.pdf"
                                           )
                            pdfmerger.write(pdf_file)
                            pdfmerger.close()

                        with open(pdf_file, "rb") as f:
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


class TaskTeXYielder:
    def __init__(self, repository, name):
        self.repository = repository
        self.name = name

    def get(self):
        result = None  # TODO

        contest, task, language = unpack_code(self.name)
        _repository_code = repository_code(contest, task, language)
        tex_file = Path(self.repository.path) / _repository_code

        logger.info(str(_repository_code) + " is accessed.")

        if tex_file is None:
            # TODO Handle the error (you should probably implement an info
            # function like above, then implement a query function in
            # TaskAccess and handle the result in download.js
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

        contest, task, language = unpack_code(self.name)
        _repository_code = repository_code(contest, task, language)
        tex_file = Path(self.repository.path) / _repository_code

        _repository_lock_file_code = repository_lock_file_code(
            contest, task, language)
        lock_file = Path(self.repository.path) / _repository_lock_file_code
        if lock_file.is_file():
            # TODO Handle error
            error = "Translation already locked; currently, you can't change"\
                "this translation. Please contact an administrator."

        else:
            logger.info(str(_repository_code) + " is written to.")

            if f is None:
                # TODO Handle the error (via result?)
                error = "No file received"

            elif len(f) > 1048576:  # 1MB
                error = "File too big"

            else:
                with open(tex_file, "wb") as target_file:
                    target_file.write(f)
                self.repository.commit(
                    str(tex_file.resolve()), str(_repository_code))

        return result


class TaskMarker:
    def __init__(self, repository, name):
        self.repository = repository
        self.name = name

    def mark(self):
        contest, task, language = unpack_code(self.name)
        _repository_lock_file_code = repository_lock_file_code(
            contest, task, language)
        lock_file = Path(self.repository.path) / _repository_lock_file_code

        logger.info(str(_repository_lock_file_code) + " is created.")

        with open(lock_file, "w") as target_file:
            target_file.write("The translation in this language is locked.")
        self.repository.commit(str(lock_file.resolve()),
                               str(_repository_lock_file_code))


class TaskGitLog:
    def __init__(self, repository, name):
        self.repository = repository
        self.name = name

    def get(self):
        result = None  # TODO

        contest, task, language = unpack_code(self.name)
        _repository_code = repository_code(contest, task, language)
        tex_file = Path(self.repository.path) / _repository_code

        logger.info("Git log for " + str(_repository_code) + " is accessed.")

        if tex_file is None:
            # TODO Handle the error (you should probably implement an info
            # function like above, then implement a query function in
            # TaskAccess and handle the result in download.js
            error = "No statement TeX found"

        else:
            result = self.repository.getlog(str(tex_file.resolve()))

        return result


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
        contest, task, language = unpack_code(name)

        if name not in TaskAccess.jobs:
            TaskAccess.jobs[name] = TaskCompileJob(TaskAccess.repository,
                                                   contest,
                                                   task,
                                                   TaskAccess.balancer,
                                                   language)
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

    @staticmethod
    def getGitLog(name):
        C = Ansi2HTMLConverter()
        return {
            "log": C.convert(TaskGitLog(TaskAccess.repository, name).get())
        }
