#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016-2018 Tobias Lenz <t_lenz94@web.de>
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
import json

from pkg_resources import resource_filename
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application

from cms import config
from cms.io.TaskTranslateInfo import TaskTranslateInfo
from cms.io.TaskAccess import TaskAccess
from cms.io.Repository import Repository


logger = logging.getLogger(__name__)


class MainHandler(RequestHandler):
    def get(self):
        self.render("overview.html")


class TaskCompileHandler(RequestHandler):
    def get(self):
        self.write(TaskAccess.query(self.get_argument("code"),
                                   int(self.get_argument("handle"))))
        self.flush()

    def post(self):
        handle = TaskAccess.compile(self.get_argument("code"))
        self.write({"handle": handle})


class PDFHandler(RequestHandler):
    def share(self, statement, code):
        self.set_header("Content-Type", "application/pdf")
        self.set_header(
            "Content-Disposition",
            "attachment;filename=\"statement-{}.pdf\"".format(code))
        self.write(statement)
        self.flush()

    def get(self, code):
        try:
            statement = TaskAccess.get(code)

            if statement is None:
                raise ValueError
        except:
            logger.error("could not download statement for {}".format(code))
            self.render("error.html")
        else:
            self.share(statement, code)


class TeXHandler(RequestHandler):
    def share(self, statement, code):
        self.set_header("Content-Type", "text")
        #TODO Do this less ugly.
        logger.error(code)
        srcname = TaskTranslateInfo.tasks[code.split("/")[0]]["filename"]
        if srcname == "statement":
            srcname += "-"
        else:
            srcname = ""
        self.set_header(
            "Content-Disposition",
            "attachment;filename=\""+srcname+"{}.tex\"".format(code))#FIXME This contains a /, which seems to automatically be converted to a _, but fix this.
        self.write(statement)
        self.flush()

    def get(self, code):
        try:
            statement = TaskAccess.getTeX(code)

            if statement is None:
                raise ValueError
        except:
            logger.error("could not download statement TeX file for {}".format(code))
            self.render("error.html")#TODO
        else:
            self.share(statement, code)


class UploadHandler(RequestHandler):
    def post(self, code):
        #TODO Handle Error
        #TODO Check file size
        f = self.request.files['file'][0]['body']
        TaskAccess.receiveTeX(code, f)


class MarkHandler(RequestHandler):
    def post(self, code):
        TaskAccess.mark(code)


class ListHandler(RequestHandler):
    def get(self):
        self.write(json.dumps(TaskTranslateInfo.task_list()))
        self.flush()


class InfoHandler(RequestHandler):
    def get(self):
        t = json.loads(self.get_argument("tasks"))
        self.write(json.dumps(TaskTranslateInfo.get_info(t)))
        self.flush()


class GerTranslateWebServer:
    """Service running a web server that lets you download task statements
    and upload translations
    For a future implementation, there should be something like an nginx configuration with one user
    per language, where all users have access to /, but /it/ is restricted
    to user 'it'.
    """

    def __init__(self):
        handlers = [(r"/", MainHandler),
                    (r"/list", ListHandler),
                    (r"/info", InfoHandler),
                    (r"/compile", TaskCompileHandler),
                    (r"/pdf/(.*)", PDFHandler),
                    (r"/tex/(.*)", TeXHandler),
                    (r"/upload/(.*)", UploadHandler),
                    (r"/mark/(.*)", MarkHandler)]

        params = {"template_path": resource_filename("cms.server",
                                                     "gertranslate/templates"),
                  "static_path": resource_filename("cms.server",
                                                   "gertranslate/static")}

        repository = Repository(config.translate_task_repository, config.translate_auto_sync)

        TaskAccess.init(repository, config.translate_max_compilations)
        TaskTranslateInfo.init(repository)

        self.app = Application(handlers, **params)

    def run(self):
        self.app.listen(config.translate_listen_port,
                        address=config.translate_listen_address)

        try:
            IOLoop.instance().start()
        except KeyboardInterrupt:
            pass
