#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2014 Fabian Gundlach <320pointsguy@gmail.com>
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

from cmscontrib.gerpythonformat.templates.plain.PlainTemplate \
    import PlainTemplate
from cmscontrib.gerpythonformat.Supplement import def_latex, input_latex
from cmscommon.constants import SCORE_MODE_MAX_TOKENED_LAST, \
    SCORE_MODE_MAX, SCORE_MODE_MAX_SUBTASK
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

        # Provide access to our logo
        shutil.copy(os.path.join(os.path.dirname(__file__), "logo.eps"),
                    os.path.join(task.wdir, "logo.eps"))

        # Register contestheader.tex as \taskheader
        shutil.copy(os.path.join(os.path.dirname(__file__),
                                 "contestheader.tex"),
                    os.path.join(task.wdir, "taskheader.tex"))
        task.supply("latex", def_latex("taskheader",
                                       input_latex("taskheader.tex")))
        # Register translation.tex as \translationheader
        shutil.copy(os.path.join(os.path.dirname(__file__),
                                     "translation.tex"),
                        os.path.join(task.wdir, "translation.tex"))
        task.supply("latex", def_latex("translationheader",
                                       input_latex("translation.tex")))

        # Provide common asy files
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "graphics.cfg"),
                        "graphics.cfg")
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "mystyle.asy"),
                        "mystyle.asy")

        task.supply("latex", def_latex("feedback", task.feedback))

        # Provide the scoring mode
        # We translate the internal constants for the different modes
        # to the years they were first used at the IOI
        # (note that we can't use the constants as they are because they contain
        # underscores)
        score_mode = task.score_mode()
        if score_mode == SCORE_MODE_MAX_SUBTASK:
            score_mode_year = "IOIXVII"
        elif score_mode == SCORE_MODE_MAX:
            score_mode_year = "IOIXIII"
        elif score_mode == SCORE_MODE_MAX_TOKENED_LAST:
            score_mode_year = "IOIX"
        task.supply("latex", def_latex("scoring", score_mode_year))

        task.supply("latex", r"\newcount\numsubtasks ")
        task.supply("latex", lambda: r"\numsubtasks={}".\
                                         format(len(task.subtasks) - 1))

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
                  r"""@{\hskip0pt}p{\outputwidth}}""" +
                  r"""\caption*{\ifnum\numsamples=1{\tSample}"""
                  r"""\else{\tSamples}\fi}\\""" + head +
                  r"""\noalign{\smallskip}\endfirsthead""" +
                  head + r"""\endhead""",
            end=r"""\end{longtable}""",
            aftereachline=r"\\ \noalign{\smallskip}",
            sep="&&",
            beforeeachcell=r"\cellcolor[gray]{.9}\vspace{-3.5ex}",
            aftereachcell=r"\vspace{-3.8ex}\ \null")
