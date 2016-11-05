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
from pathlib import Path


class TaskInfo:
    def __init__(self, path):
        info = {"title":          "???",
                "source":         "N/A",
                "algorithm":      -1,
                "implementation": -1,
                "keywords":       [],
                "uses":           [],
                "remarks":        "",
                "public":         False}
    
        try:
            i = json.loads(path.open().read())
        except:
            i = {"remarks": "{} ill-formed or missing".format(path)}
        
        info.update(i)
        
        for key, value in info.iteritems():
            setattr(self, key, value)


def load(d):    
    tasks = []
    directory = Path(d)

    for d in directory.iterdir():
        if not d.is_dir():
            continue
            
        info_path = d/"info.json"
                
        if info_path.exists():
            tasks.append(TaskInfo(info_path))

    return tasks
