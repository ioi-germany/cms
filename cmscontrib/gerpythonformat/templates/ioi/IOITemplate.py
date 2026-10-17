#!/usr/bin/env python3

# Programming contest management system
# Copyright © 2013-2021 Tobias Lenz <t_lenz94@web.de>
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

""" Template for IOI 2027.

Deliberately derived straight from PlainTemplate: everything beyond the
plain statement machinery (logos, translations, overview sheets) is left
out to keep this template small and easy to adapt.
"""

from cmscontrib.gerpythonformat.templates.plain.PlainTemplate \
    import PlainTemplate
from cmscontrib.gerpythonformat.Supplement import def_latex, input_latex

import os
import shutil


class IOITemplate(PlainTemplate):
    def __init__(self, contest, short_name=None, year="2027"):
        super(IOITemplate, self).__init__(contest)
        self.short_name = short_name
        self.year = year
        self.dirname = os.path.dirname(__file__)

    def get_contestname(self):
        # An explicitly given short name wins; the contest description is
        # only a fallback (the empty string stays meaningful).
        if self.short_name is not None:
            return self.short_name
        return self.contest._description

    def ontask(self, task):
        super(IOITemplate, self).ontask(task)

        # Register contestheader.tex as \taskheader
        shutil.copy(os.path.join(self.dirname, "contestheader.tex"),
                    os.path.join(task.wdir, "taskheader.tex"))
        task.supply("latex", def_latex("taskheader",
                                        input_latex("taskheader.tex")))

        task.supply("latex", def_latex("olympiadyear", self.year))

        # How many subtasks the statement has to mention (the sample
        # subtask does not count); checked again at the end of the document.
        task.supply("latex", r"\newcount\numsubtasks ")
        task.supply("latex", lambda: r"\numsubtasks={}".
                                         format(len(task.subtasks) - 1))
