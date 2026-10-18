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

from cmscommon.constants import SCORE_MODE_MAX, SCORE_MODE_MAX_SUBTASK, \
    SCORE_MODE_MAX_TOKENED_LAST
from cmscontrib.gerpythonformat.LocationStack import chdir
from cmscontrib.gerpythonformat.Supplement import def_latex, input_latex
from cmscontrib.gerpythonformat.templates.plain.PlainTemplate \
    import PlainTemplate

import os
import shutil


class IOITemplate(PlainTemplate):
    # How the final score of a task is computed, per score mode.
    scoring_text = {
        SCORE_MODE_MAX_SUBTASK:
            "the sum, over all subtasks, of your best score on that subtask",
        SCORE_MODE_MAX:
            "the best score of all your submissions",
        SCORE_MODE_MAX_TOKENED_LAST:
            "the best score of all your tokened submissions and your last "
            "submission",
    }

    def __init__(self, contest, short_name=None, year="2027"):
        super(IOITemplate, self).__init__(contest)
        self.short_name = short_name
        self.year = year
        self.dirname = os.path.dirname(__file__)

        # Overview sheets (contest level): make_overview_sheets() has to
        # be called explicitly from the contest config.
        self.contest.export_function(self.make_overview_sheets)
        self.contest.supplement_file("contestoverview", "contest-overview.tex")
        self.contest.supplement_file("credentials", "overview-instructions.tex")
        self.contest.supplement_file("lang", "language.tex")

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

    # Overview sheets

    def language_supplement(self, code):
        return "\\def\\TemplateLanguage{%s}" % code

    def task_max_score(self, task):
        # TaskConfig.max_score() is broken (subtasks only carry .points),
        # so sum the points here directly.
        return sum(s.points for s in task.subtasks if not s.sample)

    def supply_overview(self):
        """ Task table and scoring information for the overview sheet.
        """
        task_list = sorted(self.contest.tasks.values(), key=lambda x: x.name)

        table = ["\\subsection*{Tasks}",
                 "\\begin{longtable}{|l|l|c|c|r|}",
                 "\\hline \\textbf{Name} & \\textbf{Type} & \\textbf{Time}"
                 " & \\textbf{Memory} & \\textbf{Points} \\\\ \\hline"]
        for t in task_list:
            table.append("\\texttt{%s} & %s & %s & %s & %d \\\\ \\hline" %
                        (t.name, t.tasktype.capitalize(),
                         t.latex_timelimit(), t.latex_memorylimit(),
                         self.task_max_score(t)))
        table.append("\\end{longtable}")
        self.contest.supply("contestoverview",
                            def_latex("printtaskoverview", "\n".join(table)))

        modes = []
        for t in task_list:
            if t.score_mode() not in modes:
                modes.append(t.score_mode())

        scoring = ["\\subsection*{Scoring}"]
        if len(modes) == 1:
            scoring.append("Your final score for each task is %s." %
                           self.scoring_text[modes[0]])
        else:
            scoring.append("Your final score for a task is computed as "
                           "follows:")
            scoring.append("\\begin{itemize}")
            for m in modes:
                names = ", ".join(sorted(t.name for t in task_list
                                         if t.score_mode() == m))
                scoring.append("\\item For %s: %s." %
                               (names, self.scoring_text[m]))
            scoring.append("\\end{itemize}")
        self.contest.supply("contestoverview",
                            def_latex("printscoring", "\n".join(scoring)))

        self.contest.supply("contestoverview",
                            def_latex("contestname", self.get_contestname))
        self.contest.supply("contestoverview",
                            def_latex("olympiadyear", self.year))

    def credentials_supplement(self, users, lang, attach_statements):
        def statements():
            if not attach_statements:
                return ""
            return "".join(
                "\\clearpage\\includepdf[pages=-]{%s}" %
                os.path.relpath(t._statements[lang].file_, os.getcwd())
                for t in sorted(self.contest.tasks.values(),
                                key=lambda x: x.name)
                if lang in t._statements)

        return "\n".join(
            "\\printoverviewpage{%s}{%s, %s}{%s}%s" %
            (u.username, u.lastname, u.firstname, u.password,
             statements())
            for u in sorted(users, key=lambda x: x.username))

    def make_overview_sheets(self, attach_statements=False):
        """
        Print an overview sheet, containing information about all tasks

        attach_statements (bool): whether we should collect all primary
                                  statements for all users and add them to the
                                  resp. PDF right after their overview sheet
        """
        if self.contest.ignore_latex:
            return

        teams = {}

        for u in self.contest.users.values():
            teams.setdefault(u.team, []).append(u)

        if not os.path.exists("overview"):
            os.mkdir("overview")

        with chdir("overview"):
            self.supply_overview()
            self.contest._build_supplements_for_key("contestoverview")

            lang = "en"
            user_list = []

            self.contest.supply("lang",
                                lambda: self.language_supplement(lang))
            self.contest.supply("credentials",
                                lambda: self.credentials_supplement(
                                    user_list, lang, attach_statements))

            for team, users in sorted(teams.items(), key=lambda kv: kv[0].code):
                team_lang = team.primary_statements[0] \
                    if team.primary_statements else "en"
                if self.contest.relevant_language and \
                        self.contest.relevant_language != team_lang:
                    continue

                filename = "overview-sheet-" + team.code + ".tex"

                shutil.copy(os.path.join(self.dirname,
                                         "overview-template.tex"),
                            filename)

                lang = team_lang
                user_list = users
                self.contest._build_supplements_for_key("credentials")
                self.contest._build_supplements_for_key("lang")
                self.contest.compile(filename)
