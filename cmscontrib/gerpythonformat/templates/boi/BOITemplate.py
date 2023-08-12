#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2021 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2020-2022 Manuel Gundlach <manuel.gundlach@gmail.com>
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
from cms.rules.Rule import ZipRule
from cmscommon.constants import SCORE_MODE_MAX_SUBTASK
from cmscontrib.gerpythonformat import copyrecursivelyifnecessary
from cmscontrib.gerpythonformat.templates.lg.LgTemplate \
    import LgTemplate
from cmscontrib.gerpythonformat.LocationStack import chdir
from cmscontrib.gerpythonformat.Supplement import def_latex, input_latex
from cmscontrib.gerpythonformat.Messenger import print_msg
import os
import shutil
import filecmp
from PyPDF2 import PdfFileMerger, PdfFileReader, PdfFileWriter


# This is the template for BOI 2021 and 2022 (an only slightly modified lg template)
class BOITemplate(LgTemplate):
    def __init__(self, contest, short_name, year, header = None, hformat="pdf",
                 dirname = None):
        super(BOITemplate, self).__init__(contest, short_name)
        self.year = year
        self.header = header or f"header{self.year}"
        self.hformat = hformat
        self.dirname = dirname or os.path.dirname(__file__)

    def ontask(self, task):
        """ Some additional supplies for the latex format
        """
        super(BOITemplate, self).ontask(task)

        #Provide access to the BOI logo
        shutil.copy(os.path.join(self.dirname, self.header + "." + self.hformat),
                    os.path.join(os.getcwd(), "header." + self.hformat))

        # Copy translation headers
        copyrecursivelyifnecessary(os.path.join(task.wdir, "..", "general"),
                                   os.path.join(task.wdir, "general"))

        # Register contestheader.tex as \taskheader
        shutil.copy(os.path.join(self.dirname, "contestheader.tex"),
                    os.path.join(task.wdir, "taskheader.tex"))
        task.supply("latex", def_latex("taskheader",
                                       input_latex("taskheader.tex")))

        task.supply("latex", def_latex("olympiadyear", self.year))

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

    def _escape(self, s):
        return s.replace(' ', '-')

    def make_overview_sheets(self):
        """
        Print overview sheets in two versions (with tasks and all contestants
        of any individual team in one file OR without tasks and all contestants
        separately) and ZIP them together
        """
        if self.contest.ignore_latex:
            return

        teams = {}
        contestants_with_language = {}
        overview_sheets_for = {}

        assert(all(t._feedback_level == FEEDBACK_LEVEL_RESTRICTED
                   for t in self.contest.tasks.values()))
        assert(all(t.score_mode() == SCORE_MODE_MAX_SUBTASK
                   for t in self.contest.tasks.values()))

        prefix = "overview-sheets-for"

        for u in self.contest.users.values():
            team = u.team

            if team not in teams:
                teams[team] = []
            teams[team].append(u)

            for l in u.primary_statements:
                if l not in contestants_with_language:
                    contestants_with_language[l] = []
                contestants_with_language[l].append(u)

        if not os.path.exists("overview"):
            os.mkdir("overview")

        copyrecursivelyifnecessary(os.path.join(self.contest.wdir, "general"),
                                   os.path.join(self.contest.wdir, "overview",
                                                "general"))

        self.contest.supply("contestoverview",
                            def_latex("olympiadyear", self.year))

        import csv
        printingunwanted = dict()
        requestsfile = "printingrequested.csv"
        if os.path.exists(requestsfile):
            with open(requestsfile, encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=',', quotechar='"')
                for row in reader:
                    c, l = row["Country"], row["Language"]
                    if c not in printingunwanted:
                        printingunwanted[c] = dict()
                    printingunwanted[c]["en"] = row["English"] == "No"
                    printingunwanted[c][l] = row["Own"] == "No"

        with chdir("overview"):
            if not os.path.exists(".overviews-per-language"):
                os.mkdir(".overviews-per-language")

            with chdir(".overviews-per-language"):
                for l, users in contestants_with_language.items():
                    if self.contest.relevant_language and \
                        self.contest.relevant_language != l:
                        continue

                    self.supply_overview()
                    self.contest._build_supplements_for_key("contestoverview")

                    #Provide access to the BOI logo
                    shutil.copy(os.path.join(self.dirname,
                                             self.header + "." + self.hformat),
                                os.path.join(os.getcwd(),
                                             "header." + self.hformat))


                    def do_supply_language():
                        return self.language_supplement(l)

                    def do_supply_credentials():
                        return "\n".join("\\printoverviewpage{%s}{%s, %s}{%s}" % \
                            (u.username, u.lastname, u.firstname, u.password)
                            for u in users)

                    self.contest.supply("lang", do_supply_language)
                    self.contest.supply("credentials", do_supply_credentials)

                    filename = prefix + "-" + l + ".tex"

                    shutil.copy(os.path.join(self.dirname,
                                             "overview-template.tex"),
                                filename)
                    self.contest._build_supplements_for_key("credentials")
                    self.contest._build_supplements_for_key("lang")

                    pdf = PdfFileReader(self.contest.compile(filename))
                    assert(pdf.getNumPages() == len(users))

                    for i, u in enumerate(users):
                        overview_sheets_for[(u.username,l)] = pdf.getPage(i)

                    self.contest.supplements["lang"].parts.clear()
                    self.contest.supplements["credentials"].parts.clear()

            def cleardoublepage(stream):
                if stream.getNumPages() % 2 == 1:
                    stream.addBlankPage()

            for team, users in teams.items():
                if not os.path.exists(team.code):
                    os.mkdir(team.code)

                with chdir(team.code):
                    hw = PdfFileWriter()

                    for u in users:
                        # Overview sheets
                        ow = PdfFileWriter()

                        for l in u.primary_statements:
                            if self.contest.relevant_language and \
                                self.contest.relevant_language != l:
                                continue
                            ow.addPage(overview_sheets_for[(u.username,l)])
                        with open("overview-" + u.username + ".pdf", "wb") as f:
                            ow.write(f)

                        # handout
                        for l in u.primary_statements:
                            if self.contest.relevant_language and \
                                self.contest.relevant_language != l:
                                continue
                            if printingunwanted \
                                .get(team.name, dict()) \
                                .get(l, False):
                                print_msg(
                                    "Not adding translation to language "
                                    "{} for user {} to the handout "
                                    "as requested by team {}"
                                    .format(l, u.username, team.code))
                                hw.addPage(overview_sheets_for[(u.username,l)])
                                cleardoublepage(hw)
                                continue
                            hw.addPage(overview_sheets_for[(u.username,l)])
                            cleardoublepage(hw)

                            for t in sorted(self.contest.tasks.values(),
                                            key=lambda x: x.name):
                                if l in t._statements:
                                    st = PdfFileReader(t._statements[l].file_)
                                    hw.appendPagesFromReader(st)
                                    cleardoublepage(hw)

                    with open("handout.pdf", "wb") as f:
                        hw.write(f)

                job = {"overview-" + u.username + ".pdf":
                       os.path.join(team.code, "overview-" + u.username + ".pdf")
                       for u in users }
                job["handout.pdf"] = os.path.join(team.code, "handout.pdf")

                r = ZipRule(os.path.join("..", ".rules"),
                            team.code + "-all.zip",
                            job).ensure()
