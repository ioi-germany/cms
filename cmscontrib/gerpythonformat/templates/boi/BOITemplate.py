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

from cms import FEEDBACK_LEVEL_RESTRICTED
from cmscommon.constants import SCORE_MODE_MAX_SUBTASK
from cmscontrib.gerpythonformat import copyrecursivelyifnecessary
from cmscontrib.gerpythonformat.templates.lg.LgTemplate \
    import LgTemplate
from cmscontrib.gerpythonformat.LocationStack import chdir
from cmscontrib.gerpythonformat.Supplement import def_latex, input_latex
import os
import shutil
import filecmp
from PyPDF2 import PdfFileMerger


# This is the template for BOI 2021 (an only slightly modified lg template)
class BOITemplate(LgTemplate):
    def __init__(self, contest, short_name):
        super(BOITemplate, self).__init__(contest, short_name)

    def ontask(self, task):
        """ Some additional supplies for the latex format
        """
        super(BOITemplate, self).ontask(task)

        #Provide access to the BOI logo
        shutil.copy(os.path.join(os.path.dirname(__file__), "header.pdf"),
                    os.path.join(task.wdir, "header.pdf"))

        # Copy translation headers
        copyrecursivelyifnecessary(os.path.join(task.wdir, "..", "general"),
                                   os.path.join(task.wdir, "general"))

        # Register contestheader.tex as \taskheader
        shutil.copy(os.path.join(os.path.dirname(__file__),
                                 "contestheader.tex"),
                    os.path.join(task.wdir, "taskheader.tex"))
        task.supply("latex", def_latex("taskheader",
                                       input_latex("taskheader.tex")))

        self.mktestcasetable(task)

    def credentials_supplement(self, user, lang, attach_statements):
        def statements():
            if not attach_statements:
                return ""

            return "".join("\\mycleardoublepage\\includepdf[pages=-]{%s}" %
                               os.path.relpath(t._statements[lang].file_,
                                               os.getcwd())
                           for t in sorted(self.contest.tasks.values(),
                                           key=lambda x: x.name)
                           if lang in t._statements) + \
                   "\\mycleardoublepage"

        return "\\printoverviewpage{%s}{%s, %s}{%s}" % \
               (user.username, user.lastname, user.firstname, user.password) + \
               statements()

    def make_overview_sheets(self, attach_statements=False):
        """
        Print an overview sheet, containing information about all tasks

        attach_statements (bool): whether we should collect all primary
                                  statements for all users and add them to the
                                  resp. PDF right after their overview sheet
        """
        teams = {}

        assert(all(t._feedback_level == FEEDBACK_LEVEL_RESTRICTED
                   for t in self.contest.tasks.values()))
        assert(all(t.score_mode() == SCORE_MODE_MAX_SUBTASK
                   for t in self.contest.tasks.values()))

        for u in self.contest.users.values():
            team_name = u.team

            if team_name not in teams:
                teams[team_name] = []
            teams[team_name].append(u)

        if not os.path.exists("overview"):
            os.mkdir("overview")

        copyrecursivelyifnecessary(os.path.join(self.contest.wdir, "general"),
                                   os.path.join(self.contest.wdir, "overview",
                                                "general"))

        with chdir("overview"):
            self.supply_overview()
            self.contest._build_supplements_for_key("contestoverview")

            shutil.copy(os.path.join(os.path.dirname(__file__), "header.pdf"),
                        os.path.join(os.getcwd(), "header.pdf"))

            def do_supply_language():
                return self.language_supplement(lang_code)

            def do_supply_credentials():
                return self.credentials_supplement(user, lang_code,
                                                   attach_statements)

            self.contest.supply("lang", do_supply_language)
            self.contest.supply("credentials", do_supply_credentials)

            for team,users in teams.items():
                if not os.path.exists(team.code):
                    os.mkdir(team.code)

                outermerger = PdfFileMerger()

                with chdir(team.code):
                    for user in users:
                        innermerger = PdfFileMerger()

                        for lang_code in user.primary_statements:
                            def escape(s):
                                return s.replace(' ', '-')
                            filename = "overview-sheet-" + escape(user.username) + \
                                       "-" + lang_code + ".tex"

                            shutil.copy(os.path.join(os.path.dirname(__file__),
                                                     "overview-template.tex"),
                                        filename)

                            self.contest._build_supplements_for_key("credentials")
                            self.contest._build_supplements_for_key("lang")
                            innermerger.append(self.contest.compile(filename))

                        totalfilename = "overview-sheet-" + \
                                        escape(user.username) + ".pdf"
                        innermerger.write(totalfilename)
                        innermerger.close()
                        outermerger.append(totalfilename)

                outermerger.write("overview-sheet-" + team.code)
                outermerger.close()
