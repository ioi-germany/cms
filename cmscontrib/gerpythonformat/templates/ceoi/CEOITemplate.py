#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2014 Tobias Lenz <t_lenz94@web.de>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from cmscontrib.gerpythonformat.templates.plain.PlainTemplate \
    import PlainTemplate
from cmscontrib.gerpythonformat.Supplement import def_latex, input_latex
import os
import shutil


class CEOITemplate(PlainTemplate):
    def __init__(self, contest):
        super(CEOITemplate, self).__init__(contest)
        self.contest = contest

        # Compile bar.asy
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "bar.asy"),
                        "bar.asy")

        contest.supply("latex", def_latex("contestday",
                                          contest.simple_query("day")))
        contest.supplement_file("asy", "info.asy")
        contest.compile("bar.asy")

    def ontask(self, task):
        """ Some additional supplies for the latex format
        """
        super(CEOITemplate, self).ontask(task)
        # Register contestheader.tex as \taskheader
        shutil.copyfile(os.path.join(os.path.dirname(__file__),
                                     "contestheader.tex"),
                        os.path.join(task.wdir, "contestheader.tex"))
        task.supply("latex", def_latex("taskheader",
                                       input_latex("contestheader.tex")))

        # Register translation.tex as \translationheader
        shutil.copyfile(os.path.join(os.path.dirname(__file__),
                                     "translation.tex"),
                        os.path.join(task.wdir, "translation.tex"))
        task.supply("latex", def_latex("translationheader",
                                       input_latex("translation.tex")))

        # Tell LaTeX where watermark can be found
        shutil.copyfile(os.path.join(os.path.dirname(__file__),
                                     "ceoi-watermark.png"),
                        os.path.join(task.wdir, "ceoi-watermark.png"))
        task.supply("latex", def_latex("watermark", "ceoi-watermark.png"))

        # Tell Latex where bar.pdf can be found
        shutil.copy(os.path.join(self.contest.wdir, "bar.pdf"),
                    os.path.join(task.wdir, "bar.pdf"))
        task.supply("latex", def_latex("barpdf", "bar.pdf"))

        shutil.copyfile(os.path.join(os.path.dirname(__file__),
                                     "ceoistyle.asy"),
                        os.path.join(task.wdir, "ceoistyle.asy"))

        self.mktestcasetable(task)

    def mktestcasetable(self, task):
        """ Fancy testcase table
        """
        self.supply_case_table(
            task,
            start=r"""\begin{tabular}{p{\inputwidth}@{\hskip0pt}p{.52cm}"""
                  r"""@{\hskip0pt}p{\outputwidth}}\hline"""
                  r"""\multicolumn{1}{|c}{\sffamily\tInput} && """
                  r"""\multicolumn{1}{c|}{\sffamily\tOutput} \\ """
                  r"""\hline \noalign{\smallskip}""",
            aftereachline=r"\\ \noalign{\smallskip}",
            sep="&&",
            beforeeachcell=r"\cellcolor{bgblue}\vspace{-3ex}",
            aftereachcell=r"\vspace{-4.8ex}\ \null")
