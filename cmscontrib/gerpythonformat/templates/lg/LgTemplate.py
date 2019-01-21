#!/usr/bin/env python
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from cmscontrib.gerpythonformat.templates.plain.PlainTemplate \
    import PlainTemplate
from cmscontrib.gerpythonformat.Supplement import def_latex, input_latex
import os
import shutil


class LgTemplate(PlainTemplate):
    def __init__(self, contest):
        super(LgTemplate, self).__init__(contest)
        self.contest = contest

    def ontask(self, task):
        """ Some additional supplies for the latex format
        """
        super(LgTemplate, self).ontask(task)

        # Provide access to our graphdrawing headers
        shutil.copy(os.path.join(os.path.dirname(__file__), "paths.tex"),
                    os.path.join(task.wdir, "paths.tex"))
        shutil.copy(os.path.join(os.path.dirname(__file__), "paths.lua"),
                    os.path.join(task.wdir, "paths.lua"))
        shutil.copy(os.path.join(os.path.dirname(__file__), "graphdrawing.tex"),
                    os.path.join(task.wdir, "graphdrawing.tex"))
        shutil.copy(os.path.join(os.path.dirname(__file__), "graphdrawing.lua"),
                    os.path.join(task.wdir, "graphdrawing.lua"))

        # Register contestheader.tex as \taskheader
        shutil.copy(os.path.join(os.path.dirname(__file__),
                                 "contestheader.tex"),
                    os.path.join(task.wdir, "taskheader.tex"))
        task.supply("latex", def_latex("taskheader",
                                       input_latex("taskheader.tex")))
        # Register translation.tex as \translationheader
        shutil.copyfile(os.path.join(os.path.dirname(__file__),
                                     "translation.tex"),
                        os.path.join(task.wdir, "translation.tex"))
        task.supply("latex", def_latex("translationheader",
                                       input_latex("translation.tex")))
        # Compile bar.asy
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "graphics.cfg"),
                        "graphics.cfg")
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "mystyle.asy"),
                        "mystyle.asy")
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "logo.eps"),
                        "logo.eps")
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "bar.asy"),
                        "bar.asy")
        task.supply_asy("lg", self.contest.simple_query("lg"))
        task.supply_asy("taskname", task.simple_query("name"))
        task.supplement_file("asy", "info.asy")
        task.compile("bar.asy")

        # Tell Latex where bar.pdf can be found
        task.supply("latex", def_latex("barpdf", "bar.pdf"))
        task.supply("latex", def_latex("feedback", task.feedback))

        task.supply("latex", r"\newif\ifrestricted")
        if task._has_restricted_feedback_level():
            task.supply("latex", r"\restrictedtrue")

        self.mktestcasetable(task)

    def mktestcasetable(self, task):
        """ Fancy testcase table
        """
        head = r"""\hline""" \
               r"""\multicolumn{1}{|c}{\sffamily Input} && """ \
               r"""\multicolumn{1}{c|}{\sffamily Output} \\ """ \
               r"""\hline"""
        
        self.supply_case_table(
            task,
            start=r"""\begin{longtable}[l]{p{\inputwidth}@{\hskip0pt}p{.52cm}"""
                  r"""@{\hskip0pt}p{\outputwidth}}""" + head +
                  r"""\noalign{\smallskip}\endfirsthead""" +
                  head + r"""\endhead""",
            end=r"""\end{longtable}""",
            aftereachline=r"\\ \noalign{\smallskip}",
            sep="&&",
            beforeeachcell=r"\cellcolor[gray]{.9}\vspace{-3.5ex}",
            aftereachcell=r"\vspace{-3.8ex}\ \null")
