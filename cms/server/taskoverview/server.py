#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016-2018 Tobias Lenz <t_lenz94@web.de>
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

import importlib.resources
import json
import logging

from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application, MissingArgumentError

from cms import config
from cms.io.TaskInfo import TaskInfo
from cms.io.TaskFetch import TaskFetch
from cms.io.Repository import Repository


logger = logging.getLogger(__name__)


class MainHandler(RequestHandler):
    def get(self):
        self.render("overview.html")


class TaskCompileHandler(RequestHandler):
    def get_language(self):
        language = None
        try:
            language = self.get_argument("language")
        except MissingArgumentError:
            pass
        return language

    def get(self):
        language = self.get_language()
        self.write(
            TaskFetch.query(
                self.get_argument("code"), language, int(self.get_argument("handle"))
            )
        )
        self.flush()

    def post(self):
        language = self.get_language()
        handle = TaskFetch.compile(self.get_argument("code"), language)
        self.write({"handle": handle})


class DownloadHandler(RequestHandler):
    def get_language(self):
        language = None
        try:
            language = self.get_argument("language")
        except MissingArgumentError:
            pass
        return language

    def share(self, statement, code):
        self.set_header("Content-Type", "application/pdf")
        self.set_header(
            "Content-Disposition", 'attachment;filename="statement-{}.pdf"'.format(code)
        )
        self.write(statement)
        self.flush()

    def get(self, code):
        try:
            language = self.get_language()
            statement = TaskFetch.get(code, language)

            if statement is None:
                raise ValueError
        except Exception:
            logger.error("could not download statement for {}".format(code))
            self.render("error.html")
        else:
            self.share(statement, code)


class ListHandler(RequestHandler):
    def get(self):
        self.write(json.dumps(TaskInfo.task_list()))
        self.flush()


class InfoHandler(RequestHandler):
    def get(self):
        t = json.loads(self.get_argument("tasks"))

        self.write(json.dumps(TaskInfo.get_info(t)))
        self.flush()


class TaskOverviewWebServer:
    """Service running a web server that displays an overview of
       all available tasks
    """

    def __init__(self):
        handlers = [(r"/", MainHandler),
                    (r"/list", ListHandler),
                    (r"/info", InfoHandler),
                    (r"/compile", TaskCompileHandler),
                    (r"/download/(.*)", DownloadHandler)]

        params = {
            "template_path": str(
                importlib.resources.files("cms.server") / "taskoverview/templates"
            ),
            "static_path": str(
                importlib.resources.files("cms.server") / "taskoverview/static"
            ),
        }

        repository = Repository(
            config.taskoverview.task_repository,
            config.taskoverview.auto_sync,
            auto_push=True,
        )

        TaskFetch.init(repository, config.taskoverview.max_compilations)
        TaskInfo.init(
            repository,
            config.taskoverview.tasks_folders,
            config.taskoverview.contests_folders,
        )

        self.app = Application(handlers, **params)

    def run(self):
        self.app.listen(
            config.taskoverview.listen_port,
            address=config.taskoverview.listen_address,
        )

        try:
            IOLoop.instance().start()
        except KeyboardInterrupt:
            pass
