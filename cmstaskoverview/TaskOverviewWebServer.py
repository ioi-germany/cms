#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
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
import json

from pkg_resources import resource_filename
from tornado import template
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application, asynchronous

from .Config import config
from .TaskInfo import TaskInfo
from .TaskFetch import TaskFetch


logger = logging.getLogger(__name__)


class TaskOverviewHandler(RequestHandler):
    def get(self):  
        try:
            tasks = TaskInfo(config.task_repository)
        except:
            logger.warning("couldn't load tasks")
            tasks = []
            raise
        
        self.render("overview.html", tasks=tasks)


class TaskCompileHandler(RequestHandler):
    def get(self):        
        self.write(TaskFetch.query(self.get_argument("code")))
        self.flush()

    def post(self):
        TaskFetch.compile(self.get_argument("code"))


class DownloadHandler(RequestHandler):
    def share(self, url, code):
        try:
            f = open(url, "rb")
            content = f.read()
            
            self.set_header("Content-Type", "application/pdf");
            self.set_header("Content-Disposition",
                            "attachment;filename=\"statement-{}.pdf\"".
                                format(code))
            self.write(content)
            
        except:
            logger.error("could not download statement")
            
        finally:
            f.close()

    def get(self, code):
        url = TaskFetch.get(code)

        if url is None:
            logger.error("could not download statement")
        else:
            self.share(url, code)

class TaskOverviewWebServer:
    """Service running a web server that displays an overview of
       all available tasks
    """

    def __init__(self):
        handlers = [(r"/", TaskOverviewHandler),
                    (r"/compile", TaskCompileHandler),
                    (r"/download/(.*)", DownloadHandler)]
    
        base = "cmstaskoverview"
        params = {"template_path": resource_filename(base, "templates"),
                  "static_path":   resource_filename(base, "static")}
    
        TaskFetch.init(config.task_repository)
    
        self.app = Application(handlers, **params)

    def run(self):    
        self.app.listen(config.http_port)
        
        try:
            IOLoop.instance().start()
        except KeyboardInterrupt:
            pass
