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
    def __init__(self, d):
        self.tasks = []
        self.dates = {}
        directory = Path(d)

        for d in directory.iterdir():
            if not d.is_dir():
                continue
                
            info_path = d/"info.json"
                    
            if info_path.exists():
                self.tasks.append(SingleTaskInfo(d.parts[-1], info_path))
    
            self.dates.update({e.timestamp(): e.info
                               for e in self.tasks[-1].uses})

    def interesting_dates(self):
        raw = sorted([(key, val) for key, val in self.dates.iteritems()])
        data = []
        
        # Merge multiple entries for the same contest (multiple days,
        # typos in the files etc.):
        #
        # If there are multiple entries with the same description at successive
        # time points, we keep only the last one.
        #
        # This is of course not perfect, but it should work in most cases.
        # Since the selection criteria are just for convenience, this should
        # be fine (and it is certainly much better than having to sanitize all
        # info.json files by hand)
        for key, val in raw:
            if len(data) > 0 and data[-1][1] == val:
                data.pop()
            data.append((key, val))
            
        return json.dumps(data)
    
    def dump(self):
        return json.dumps([t.to_dict() for t in self.tasks])
    
    def __iter__(self):
        for t in self.tasks:
            yield t
    
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
