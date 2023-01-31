#!/usr/bin/env python2
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import json

from pkg_resources import resource_filename
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application

from cms import config
from cms.io.TaskInfo import TaskInfo
from cms.io.TaskFetch import TaskFetch
from cms.io.Repository import Repository


logger = logging.getLogger(__name__)


class MainHandler(RequestHandler):
    def get(self):
        self.render("overview.html")


class TaskCompileHandler(RequestHandler):
    def get(self):
        self.write(TaskFetch.query(self.get_argument("code"),
                                   int(self.get_argument("handle"))))
        self.flush()

    def post(self):
        handle = TaskFetch.compile(self.get_argument("code"))
        self.write({"handle": handle})


class DownloadHandler(RequestHandler):
    def share(self, statement, code):
        self.set_header("Content-Type", "application/pdf")
        self.set_header(
            "Content-Disposition",
            "attachment;filename=\"statement-{}.pdf\"".format(code))
        self.write(statement)
        self.flush()

    def get(self, code):
        try:
            statement = TaskFetch.get(code)

            if statement is None:
                raise ValueError
        except:
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

        params = {"template_path": resource_filename("cms.server",
                                                     "taskoverview/templates"),
                  "static_path": resource_filename("cms.server",
                                                   "taskoverview/static")}

        repository = Repository(config.taskoverview.task_repository,
                                config.taskoverview.auto_sync)

        TaskFetch.init(repository, config.taskoverview.max_compilations)
        TaskInfo.init(repository)

        self.app = Application(handlers, **params)

    def run(self):
        self.app.listen(config.taskoverview.listen_port,
                        address=config.taskoverview.listen_address)

        try:
            IOLoop.instance().start()
        except KeyboardInterrupt:
            pass
