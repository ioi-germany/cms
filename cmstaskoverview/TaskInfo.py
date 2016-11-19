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

from datetime import datetime
from pathlib import Path
from multiprocessing import Process, Queue
from sys import exc_info
from traceback import format_exception
from time import sleep, time

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
    
        try:
            i = json.loads(path.open().read())
        except:
            i = {"remarks": "{} ill-formed or missing".format(path)}
        
        info.update(i)
        
        info["uses"] += info.get("previous uses", [])

        if info["old"] is None:
            info["old"] = len(info["uses"]) > 0 or info["public"]
        
        try:
            info["uses"] = [DateEntry(e[0], e[1]) for e in info["uses"]]
        except ValueError:
            info["uses"] = []
            
        for key, value in info.iteritems():
            setattr(self, key, value)

    def to_dict(self):
        return {"code":           self.code,
                "title":          self.title,
                "source":         self.source,
                "algorithm":      self.algorithm,
                "implementation": self.implementation,
                "keywords":       self.keywords,
                "uses":           [e.to_dict() for e in self.uses],
                "remarks":        self.remarks,
                "public":         self.public,
                "old":            self.old}


class TaskInfo:
    tasks = {}
    queue = Queue()
    timestamps = {}

    @staticmethod
    def init(d):
        def main_loop(directory, queue):
            tasks = []
        
            while True:
                # Remove tasks that are no longer available
                for t in tasks:
                    info_path = directory/t/"info.json"
                    
                    if not info_path.exists():
                        queue.put(("pop", t))
                tasks = []
            
                # Load all available tasks                
                for d in directory.iterdir():
                    if not d.is_dir():
                        continue
                        
                    # We catch all exceptions since the main loop must go on
                    try:    
                        info_path = d/"info.json"
                                
                        if info_path.exists():
                            info = SingleTaskInfo(d.parts[-1], info_path)
                            queue.put(("push", info.to_dict()))
                            tasks.append(info.code)

                    except:
                        # We can't use logger since this would break
                        # multiprocessing...
                        print("\n".join(format_exception(*exc_info())))
                
                sleep(1)
        
        TaskInfo.info_process = Process(target=main_loop,
                                        args=(Path(d), TaskInfo.queue))
        TaskInfo.info_process.daemon = True
        TaskInfo.info_process.start()

    @staticmethod
    def _update():
        while not TaskInfo.queue.empty():
            command, data = TaskInfo.queue.get(False)
            
            if command == "push":
                if TaskInfo.tasks.get(data["code"], {}) != data:
                    TaskInfo.tasks[data["code"]] = data
                    TaskInfo.timestamps[data["code"]] = time()
            if command == "pop":
                del TaskInfo.tasks[data]

    @staticmethod
    def task_list():
        TaskInfo._update()
        
        return [{"task": t, "timestamp": TaskInfo.timestamps[t]}
                for t in TaskInfo.tasks]

    @staticmethod
    def get_info(keys):
        TaskInfo._update()
        
        return {t: TaskInfo.tasks[t] for t in keys if t in TaskInfo.tasks}

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
