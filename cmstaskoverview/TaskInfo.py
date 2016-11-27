#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2016 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2016 Simon Bürger <simon.buerger@rwth-aachen.de>
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

import os
import json
import logging

from datetime import datetime
from pathlib import Path
from multiprocessing import Process, Manager
from sys import exc_info
from traceback import format_exception
from time import sleep, time
from copy import deepcopy
from math import sqrt


logger = logging.getLogger(__name__)


class DateEntry:
    def __init__(self, date_code, info):
        self.date = datetime.strptime(date_code, "%Y-%m-%d").date()
        self.info = info + " {}".format(self.date.year)
    
    def timestamp(self):
        return self.date.toordinal()
    
    def to_dict(self):
        return {"timestamp": self.timestamp(),
                "info":      self.info}


class SingleTaskInfo:
    def __init__(self, code, path):
        info = {"code":           code,
                "title":          "???",
                "source":         "N/A",
                "algorithm":      -1,
                "implementation": -1,
                "keywords":       [],
                "uses":           [],
                "remarks":        "",
                "public":         False,
                "old":            None}
                
        if not path.exists():
            i = {"error": "The info.json file is missing."}
        else:
            try:
                i = json.loads(path.open().read())
            except:
                i = {"error": "The info.json file is corrupt."}
            else:
                missing = []
                for e in ["title", "algorithm", "implementation", "public"]:
                    if e not in i:
                        missing.append(e)
                
                if len(missing) > 0:
                    i["error"] = "Some important entries are missing: " + \
                                 ", ".join(missing) + "."
            
        info.update(i)

        if info["old"] is None:
            info["old"] = len(info["uses"]) > 0 or info["public"]
        
        try:
            info["uses"] = [DateEntry(e[0], e[1]) for e in info["uses"]]
        except ValueError:
            info["uses"] = []
            
            if "error" not in info:
                info["error"] = "I couldn't parse the dates for \"(previous) uses\"."
            
        for key, value in info.iteritems():
            setattr(self, key, value)

    def to_dict(self):
        result = {"code":           self.code,
                  "title":          self.title,
                  "source":         self.source,
                  "algorithm":      self.algorithm,
                  "implementation": self.implementation,
                  "keywords":       self.keywords,
                  "uses":           [e.to_dict() for e in self.uses],
                  "remarks":        self.remarks,
                  "public":         self.public,
                  "old":            self.old}
                 
        if hasattr(self, "error"):
            result["error"] = self.error
        
        return result


class TaskInfo:
    tasks = Manager().dict()

    @staticmethod
    def init(repository):
        def main_loop(repository, tasks, waiting_time):
            task_list = []
            directory = Path(repository.path)
        
            while True:
                start = time()
            
                with repository:
                    # Remove tasks that are no longer available
                    for t in task_list:
                        info_path = directory/t
                        
                        if not info_path.exists():
                            del tasks[t]
                    
                    task_list = []
                
                    # Load all available tasks                
                    for d in directory.iterdir():
                        if not d.is_dir():
                            continue
                            
                        # We catch all exceptions since the main loop must go on
                        try:    
                            info_path = d/"info.json"
                            
                            code = d.parts[-1]
                            info = SingleTaskInfo(code, info_path).to_dict()
                                                    
                            old = tasks.get(code, {"timestamp": 0})
                            info["timestamp"] = old["timestamp"]
                            
                            if old != info:
                                info["timestamp"] = time()
                                tasks[code] = info
                            
                            task_list.append(code)

                        except:
                            logger.info("\n".join(
                                            format_exception(*exc_info())))

                logger.info("finished iteration of TaskInfo.main_loop in {}ms".\
                                format(int(1000 * (time() - start))))

                sleep(waiting_time)
        
        TaskInfo.info_process = Process(target=main_loop,
                                        args=(repository, TaskInfo.tasks,
                                              .5 * (1 + sqrt(5))))
        TaskInfo.info_process.daemon = True
        TaskInfo.info_process.start()

    @staticmethod
    def task_list():
        data = deepcopy(TaskInfo.tasks)

        return [{"task": data[t]["code"], "timestamp": data[t]["timestamp"]}
                for t in data]

    @staticmethod
    def get_info(keys):
        data = deepcopy(TaskInfo.tasks)
    
        return {x: data[x] for x in keys if x in data}

    @staticmethod
    def entries():
        return ["code", "title", "source", "algorithm", "implementation",
                "keywords", "uses", "remarks", "public", "download"]

    @staticmethod
    def desc():
        return {"code": "Code",
                "title": "Title",
                "source": "Source",
                "algorithm": "Diff<sub>Alg</sub>",
                "implementation": "Diff<sub>Impl</sub>",
                "keywords": "Keywords",
                "uses": "Previous uses",
                "remarks": "Remarks",
                "public": "Public?",
                "download": "PDF"}
