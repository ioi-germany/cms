#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2016-2017 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2016 Simon Bürger <simon.buerger@rwth-aachen.de>
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

from six import iteritems
from babel.core import Locale

logger = logging.getLogger(__name__)

#TODO Delete this from this file?
class DateEntry:
    def __init__(self, date_code, info):
        self.date = datetime.strptime(date_code, "%Y-%m-%d").date()
        self.info = info + " {}".format(self.date.year)

    def timestamp(self):
        return self.date.toordinal()

    def to_dict(self):
        return {"timestamp": self.timestamp(),
                "info":      self.info}


class SingleTaskTranslateInfo:
    def __init__(self, code, path):
        info = {"code":           code,
                "title":          "???",
                "keywords":       [],
                "remarks":        "",
                "locked":         [],
                "translated":     [],
                "compile":        True,
                "filename":       None}

        if not path.exists():
            i = {"error": "The info.json file is missing."}
        else:
            try:
                i = json.loads(path.open().read())
            except:
                i = {"error": "The info.json file is corrupt."}
            else:
                missing = []
                for e in ["title"]:
                    if e not in i:
                        missing.append(e)

                if len(missing) > 0:
                    i["error"] = "Some important entries are missing: " + \
                                 ", ".join(missing) + "."

        info.update(i)

        info["locked"] = [l.name[:-5] for l in path.parent.iterdir() if l.is_file() and l.name.endswith(".lock")]
        if info["filename"]==None:
            info["filename"] = "statement"
        info["translated"] = [l.name[len(info["filename"])+1:-4] for l in path.parent.iterdir() if l.is_file() and l.name.endswith(".tex") and l.name.startswith(info["filename"]+"-")]

        for key, value in iteritems(info):
            setattr(self, key, value)

    def to_dict(self):
        result = {"code":           self.code,
                  "title":          self.title,
                  "keywords":       self.keywords,
                  "remarks":        self.remarks,
                  "locked":         self.locked,
                  "translated":     self.translated,
                  "compile":        self.compile,
                  "filename":       self.filename}

        if hasattr(self, "error"):
            result["error"] = self.error

        return result


class TaskTranslateInfo:
    manager = Manager()
    tasks = manager.dict()
    languages = manager.list()

    @staticmethod
    def init(repository):
        def load(directory, tasks, languages):
            # Load list of relevant languages
            languages_path = directory / "languages.json"
            if not languages_path.exists():
                logger.error("The languages.json file is missing.")
                return
            try:
                #TODO Handle this less awkwardly
                languages[:] = list()
                languages.extend( json.loads(open(languages_path).read())["languages"] )
            except:
                logger.error("The languages.json file is corrupt.")
                return
            languages.sort()

            # Load all available tasks
            for d in directory.iterdir():
                if not d.is_dir():
                    continue

                #NOTE Remember to have this in taskoverview, too
                if d.name.startswith('.'):
                    continue

                # We catch all exceptions since the main loop must go on
                try:
                    info_path = d / "info.json"

                    code = d.parts[-1]
                    info = SingleTaskTranslateInfo(code, info_path).to_dict()

                    old = tasks.get(code, {"timestamp": 0})
                    info["timestamp"] = old["timestamp"]

                    if old != info:
                        info["timestamp"] = time()
                        tasks[code] = info

                except:
                    logger.info("\n".join(format_exception(*exc_info())))

        def main_loop(repository, tasks, languages, waiting_time):
            directory = Path(repository.path)

            while True:
                start = time()

                with repository:
                    # Remove tasks that are no longer available
                    for t in tasks.keys():
                        info_path = directory / t

                        if not info_path.exists():
                            del tasks[t]

                    load(directory, tasks, languages)

                logger.info("finished iteration of TaskTranslateInfo.main_loop in {}ms".
                            format(int(1000 * (time() - start))))

                sleep(waiting_time)

        # Load data once on start-up (otherwise tasks might get removed when
        # the server is restarted)
        with repository:
            load(Path(repository.path), TaskTranslateInfo.tasks, TaskTranslateInfo.languages)

        TaskTranslateInfo.info_process = Process(target=main_loop,
                                        args=(repository, TaskTranslateInfo.tasks, TaskTranslateInfo.languages,
                                              .5 * (1 + sqrt(5))))
        TaskTranslateInfo.info_process.daemon = True
        TaskTranslateInfo.info_process.start()

    @staticmethod
    def task_list():
        data = deepcopy(TaskTranslateInfo.tasks)

        return [{"task": data[t]["code"], "timestamp": data[t]["timestamp"]}
                for t in data]

    @staticmethod
    def get_info(keys):
        data = deepcopy(TaskTranslateInfo.tasks)

        return {x: data[x] for x in keys if x in data}

    @staticmethod
    def language_list():
        return deepcopy(TaskTranslateInfo.languages)

    @staticmethod
    def gertranslate_entries():
        return ["code", "title",
                "keywords", "remarks", "download", "tex"] +\
               ["download-"+l for l in TaskTranslateInfo.languages] +\
               ["tex-"+l for l in TaskTranslateInfo.languages] +\
               ["upload-"+l for l in TaskTranslateInfo.languages] +\
               ["mark-"+l for l in TaskTranslateInfo.languages] +\
               ["download-ALL"]

    @staticmethod
    def gertranslate_desc():
        return {
                **{"code": "Code",
                "title": "Title",
                "keywords": "Keywords",
                "remarks": "Remarks",
                "download": "PDF [O]",
                "tex": "TeX [O]",
                "download-ALL": "PDF [ALL]"},
                **{"download-"+l: "PDF ["+l+"]" for l in TaskTranslateInfo.languages},
                **{"tex-"+l: "TeX ["+l+"]" for l in TaskTranslateInfo.languages},
                **{"upload-"+l: "Upload TeX ["+l+"]" for l in TaskTranslateInfo.languages},
                **{"mark-"+l: "Finalize ["+l+"]" for l in TaskTranslateInfo.languages}
               }

    @staticmethod
    def languages_desc():
        return {l: Locale(l).language_name+" ["+l+"]" for l in TaskTranslateInfo.languages}
