#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2014 Fabian Gundlach <320pointsguy@gmail.com>
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

from cmscontrib.gerpythonformat.templates.plain.PlainTemplate \
    import PlainTemplate
from cmscontrib.gerpythonformat.Supplement import def_latex, input_latex
import os
import shutil


class LgTemplate(PlainTemplate):
    def __init__(self, contest):
        super(LgTemplate, self).__init__(contest)
        self.contest = contest

        # Compile bar.asy
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "bar.asy"),
                        "bar.asy")
        contest.supply_asy("lg", contest.simple_query("lg"))
        contest.supplement_file("asy", "info.asy")
        contest.compile("bar.asy")

    def ontask(self, task):
        """ Some additional supplies for the latex format
        """
        super(LgTemplate, self).ontask(task)
        # Register contestheader.tex as \taskheader
        shutil.copy(os.path.join(os.path.dirname(__file__),
                                 "contestheader.tex"),
                    os.path.join(task.wdir, "taskheader.tex"))
        task.supply("latex", def_latex("taskheader",
                                       input_latex("taskheader.tex")))
        # Tell Latex where logopng can be found
        shutil.copy(os.path.join(os.path.dirname(__file__), "logo.png"),
                    os.path.join(task.wdir, "logo.png"))
        task.supply("latex", def_latex("logopng", "logo.png"))
        # Tell Latex where bar.pdf can be found
        shutil.copy(os.path.join(self.contest.wdir, "bar.pdf"),
                    os.path.join(task.wdir, "bar.pdf"))
        task.supply("latex", def_latex("barpdf", "bar.pdf"))
        self.mktestcasetable(task)

    def mktestcasetable(self, task):
        """ Fancy testcase table
        """
        self.supply_case_table(
            task,
            start=r"""\begin{tabular}{p{\inputwidth}@{\hskip0pt}p{.52cm}"""
                  r"""@{\hskip0pt}p{\outputwidth}}\hline"""
                  r"""\multicolumn{1}{|c}{\sffamily Input} && """
                  r"""\multicolumn{1}{c|}{\sffamily Output} \\ """
                  r"""\hline \noalign{\smallskip}""",
            aftereachline=r"\\ \noalign{\smallskip}",
            sep="&&",
            beforeeachcell=r"\cellcolor[gray]{.9}\vspace{-3ex}",
            aftereachcell=r"\vspace{-4.8ex}\ \null")
