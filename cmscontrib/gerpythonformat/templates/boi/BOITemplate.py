#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2021 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2020-2021 Manuel Gundlach <manuel.gundlach@gmail.com>
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
from cmscontrib.gerpythonformat.LocationStack import chdir
from cmscontrib.gerpythonformat.Supplement import def_latex, input_latex
from cmscontrib.gerpythonformat.ContestConfig import MyTeam
from cmscommon.constants import SCORE_MODE_MAX_TOKENED_LAST, \
    SCORE_MODE_MAX, SCORE_MODE_MAX_SUBTASK
import os
import shutil


class BOITemplate(PlainTemplate):
    def __init__(self, contest, short_name):
        super(BOITemplate, self).__init__(contest)
        self.short_name = short_name

        self.contest.export_function(self.make_overview_sheets)
        self.contest.supplement_file("contestoverview", "contest-overview.tex")
        self.contest.supplement_file("credentials", "overview-instructions.tex")
        self.contest.supplement_file("lang", "language.tex")

    def get_contestname(self):
        # we do not simply use self.short_name or self.contest._description
        # as we might want to allow the empty string as self.short_name
        if self.short_name is not None:
            return self.short_name
        else:
            return self.contest._description

    def ontask(self, task):
        """ Some additional supplies for the latex format
        """
        super(BOITemplate, self).ontask(task)

        # Provide access to our graphdrawing headers
        shutil.copy(os.path.join(os.path.dirname(__file__), "paths.tex"),
                    os.path.join(task.wdir, "paths.tex"))
        shutil.copy(os.path.join(os.path.dirname(__file__), "paths.lua"),
                    os.path.join(task.wdir, "paths.lua"))
        shutil.copy(os.path.join(os.path.dirname(__file__), "graphdrawing.tex"),
                    os.path.join(task.wdir, "graphdrawing.tex"))
        shutil.copy(os.path.join(os.path.dirname(__file__), "graphdrawing.lua"),
                    os.path.join(task.wdir, "graphdrawing.lua"))

        # Provide access to the BOI logo TODO
        #shutil.copy(os.path.join(os.path.dirname(__file__), "logo.eps"),
                    #os.path.join(task.wdir, "logo.eps"))

        # Register contestheader.tex as \taskheader
        shutil.copy(os.path.join(os.path.dirname(__file__),
                                 "contestheader.tex"),
                    os.path.join(task.wdir, "taskheader.tex"))
        task.supply("latex", def_latex("taskheader",
                                       input_latex("taskheader.tex")))

        task.supply("latex", def_latex("feedback", task.feedback))

        score_mode = task.score_mode()
        task.supply("latex", def_latex("scoring",
                                       self.score_mode_year(score_mode)))

        task.supply("latex", r"\newcount\numsubtasks ")
        task.supply("latex", lambda: r"\numsubtasks={}".\
                                         format(len(task.subtasks) - 1))

        task.supply("latex", r"\newif\ifrestricted")
        if task._has_restricted_feedback_level():
            task.supply("latex", r"\restrictedtrue")

        self.mktestcasetable(task)

    def score_mode_year(self, score_mode):
        """
        Provide the scoring mode
        We translate the internal constants for the different modes to the years
        they were first used at the IOI
        (note that we can't use the constants as they are because they contain
        underscores)
        """
        if score_mode == SCORE_MODE_MAX_SUBTASK:
            return "IOIXVII"
        elif score_mode == SCORE_MODE_MAX:
            return "IOIXIII"
        elif score_mode == SCORE_MODE_MAX_TOKENED_LAST:
            return "IOIX"

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

    def supply_overview(self):
        # Task information
        task_list = sorted(self.contest.tasks.values(), key=lambda x: x.name)

        thead = ["\\tName", "\\tTaskType", "\\tTimeLimit", "\\tMemoryLimit"]
        tbody = []

        show_score_mode_col = len(set(t.score_mode() for t in task_list)) > 1
        score_map = {}
        score_list = []

        if show_score_mode_col:
            thead.append("\\tScoring")

        show_max_score_col = len(set(t.max_score() for t in task_list)) > 1

        if show_max_score_col:
            thead.append("\\tMaxScore")

        for t in task_list:
            tbody.append(["\\ttfamily " + t.name, "\\tTT" + t.tasktype,
                          t.latex_timelimit(), t.latex_memorylimit()])

            scm = t.score_mode()

            if scm not in score_map:
                score_map[scm] = len(score_map) + 1
                score_list.append("\\tScoringFrom" + self.score_mode_year(scm))

            if show_score_mode_col:
                tbody[-1].append("(%d)" % score_map[scm])

            if show_max_score_col:
                tbody[-1].append("$%d$" % t.max_score())

        def mcol(i, h):
            coltype = "c"
            colentry = h
            colsep = "&&"

            if i == 0:
                coltype = "|" + coltype
                colentry = "\\kern4pt" + colentry

            if i == len(thead) - 1:
                coltype = coltype + "|"
                colentry = colentry + "\\kern4pt"
                colsep = ""

            return "\\multicolumn{1}{%s}{%s}%s" % (coltype, colentry, colsep)

        thead_string = "\\begin{tabular}{" + \
            "@{\\hskip0pt}p{.52cm}@{\\hskip0pt}".join(["c"] * len(thead)) + \
            "}\\noalign{\\hrule}" + "".join(mcol(i,h) for i,h
                                                      in enumerate(thead)) + \
            "\\\\" + "\\noalign{\\hrule}"

        def trow(l):
            return "\\noalign{\\smallskip}" + \
                   "&&".join("\\cellcolor[gray]{.9}\\hbox{\\vrule height 14pt "
                             "depth 9.2pt width 0pt}" + x for x in l) + "\\\\"
        tbody_string = "\n".join(trow(l) for l in tbody)

        task_overview = "\\subsection*{\\tTasks}" + thead_string + \
                        tbody_string + "\\end{tabular}"

        if not show_max_score_col:
            task_overview += "\\par\\medskip\\tMaxScoreGeneral{$%d$}" % \
                                 task_list[0].max_score()

        self.contest.supply("contestoverview", def_latex("printtaskoverview",
                                                         task_overview))

        # Scoring information
        if len(score_list) == 1:
            score_info = score_list[0] + "general"
        else:
            score_info = "\\tScoringIntroduction\n\\begin{enumerate}" + \
                         "\n".join("\\item " + scm for scm in score_list) + \
                         "\\end{enumerate}"
        score_info = "\\subsection*{\\tScoring}\n" + score_info

        self.contest.supply("contestoverview", def_latex("printscoring",
                                                         score_info))
        self.contest.supply("contestoverview",
                            def_latex("contestname", self.get_contestname))

    def credentials_supplement(self, users, attach_statements):
        def for_user(u):
            return "\n".join(documents(u, l) for l in u.primary_statements)

        def documents(u, l):
            return "\\def\TemplateLanguage{%s}" % l + \
                   "\\printoverviewpage{%s}{%s, %s}{%s}" % \
                       (u.username, u.lastname, u.firstname, u.password) + \
                   statements(u, l)

        def statements(u, l):
            if not attach_statements:
                return ""

            return "".join("\\mycleardoublepage\\includepdf[pages=-]{%s}" %
                               t._statements[l].file_
                           for t in sorted(self.contest.tasks.values(),
                                           key=lambda x: x.name)
                           if l in t._statements) + \
                   "\\mycleardoublepage"

        return "\n".join(for_user(u) for u in users)

    def language_supplement(self, code):
        return "\\def\\TemplateLanguage{%s}" % code

    def make_overview_sheets(self, attach_statements=False):
        """
        Print an overview sheet, containing information about all tasks

        attach_statements (bool): whether we should collect all primary
                                  statements for all users and add them to the
                                  resp. PDF right after their overview sheet
        """
        teams = {}

        for u in self.contest.users.values():
            #TODO Rename team_name to team (as this actually seems to be a team object)
            team_name = u.team

            if self.contest.relevant_language and self.contest.relevant_language not in team_name.primary_statements:
                continue

            if team_name not in teams:
                teams[team_name] = []
            teams[team_name].append(u)

        if not os.path.exists("overview"):
            os.mkdir("overview")

        with chdir("overview"):
            self.supply_overview()
            self.contest._build_supplements_for_key("contestoverview")

            #TODO
            #shutil.copy(os.path.join(os.path.dirname(__file__), "logo.eps"),
                        #os.path.join(os.getcwd(), "logo.eps"))

            lang_code = ""
            user_list = []

            def do_supply_language():
                return self.language_supplement(lang_code)

            def do_supply_credentials():
                return self.credentials_supplement(user_list, attach_statements)

            self.contest.supply("lang", do_supply_language)
            self.contest.supply("credentials", do_supply_credentials)

            for team,users in teams.items():
                filename = "overview-sheet-" + team.name + ".tex"

                shutil.copy(os.path.join(os.path.dirname(__file__),
                                             "overview-template.tex"),
                            filename)

                lang_code = str.lower(team.code)
                if lang_code == "unaffiliated":
                    lang_code = "en"

                user_list = users
                self.contest._build_supplements_for_key("credentials")
                self.contest._build_supplements_for_key("lang")
                self.contest.compile(filename)
