#!/usr/bin/env python3

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

from cmscontrib.gerpythonformat.templates.plain.PlainTemplate \
    import PlainTemplate
from cmscontrib.gerpythonformat.LocationStack import chdir
from cmscontrib.gerpythonformat.Supplement import def_latex, input_latex
from cmscommon.constants import SCORE_MODE_MAX_TOKENED_LAST, \
    SCORE_MODE_MAX, SCORE_MODE_MAX_SUBTASK
import os
import shutil


class LgTemplate(PlainTemplate):
    def __init__(self, contest, short_name):
        super(LgTemplate, self).__init__(contest)
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

        # Provide translation-{de,en}.tex
        shutil.copy(os.path.join(os.path.dirname(__file__),
                                     "translation-de.tex"),
                        os.path.join(task.wdir, "translation-de.tex"))
        shutil.copy(os.path.join(os.path.dirname(__file__),
                                     "translation-en.tex"),
                        os.path.join(task.wdir, "translation-en.tex"))

        # Provide common asy files
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "graphics.cfg"),
                        "graphics.cfg")
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "mystyle.asy"),
                        "mystyle.asy")

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

        # --- typst support (mirror of the latex setup above) ---
        self.supply_typst_translations(task)

        def lg_logo():
            # Compiled by compiletypst from logo.eps using ghostscript
            if os.path.isfile(os.path.join(task.wdir, "logo-typst.pdf")):
                return '#let lg-logo = scale(45%)[#image("logo-typst.pdf")]\n'
            return "#let lg-logo = none\n"

        task.supply("typst", lg_logo)
        task.supply("typst", lambda: "#let ifrestricted = {}\n".format(
            "true" if task._has_restricted_feedback_level() else "false"))
        task.supply("typst", LG_TYPST)
        task.supply("typst", TMR_TYPST)

    def typst_language(self, task):
        # Language is set by compiletypst from the statement file name
        # suffix; the contestheader defaults to German, so we do too.
        lang = getattr(task, "typst_language", None) or "de"
        if lang in LG_TRANSLATIONS:
            return lang
        # variant language tags (e.g. "en-isc") reuse the base language's
        # translated strings
        base = lang.split("-")[0]
        return base if base in LG_TRANSLATIONS else "de"

    def supply_typst_translations(self, task):
        """Provide the translated strings (mirroring translation-{de,en}.tex)
        as typst definitions for the current document language.
        """
        def translations():
            lang = self.typst_language(task)
            table = LG_TRANSLATIONS.get(lang, LG_TRANSLATIONS["de"])
            out = ""
            for name, text in table.items():
                out += '#let t-{} = "{}"\n'.format(
                    name, text.replace("\\", "\\\\").replace('"', '\\"'))
            return out

        task.supply("typst", translations)

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
               r"""\multicolumn{1}{|c}{\sffamily\tInput} && """ \
               r"""\multicolumn{1}{c|}{\sffamily\tOutput} \\ """ \
               r"""\hline"""

        # NOTE the "Samples" heading is emitted by \showcases (in
        # contestheader.tex) just before \testcasetable — outside the
        # longtable, exactly like \showlimits emits its \sheading{Limits} —
        # so the space above both headings comes from the same beforeskip.
        # (\noalign skips inside longtable are unreliable: the negative
        # \vskip before the heading had no measurable effect.)
        self.supply_case_table(
            task,
            start=r"""\begin{longtable}[l]{p{\inputwidth}@{\hskip0pt}p{.52cm}"""
                  r"""@{\hskip0pt}p{\outputwidth}}""" +
                  head +
                  r"""\noalign{\smallskip}\endfirsthead""" +
                  head + r"""\endhead""",
            end=r"""\noalign{\vskip-\smallskipamount}\end{longtable}""",
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

        if not show_max_score_col and len(task_list) > 0:
            task_overview += "\\par\\medskip\\tMaxScoreGeneral{$%d$}" % \
                                     task_list[0].max_score()

        self.contest.supply("contestoverview", def_latex("printtaskoverview",
                                                         task_overview))

        # Scoring information
        if len(score_list) == 1:
            score_info = score_list[0] + "general"
        elif len(score_list) > 1:
            score_info = "\\tScoringIntroduction\n\\begin{enumerate}" + \
                         "\n".join("\\item " + scm for scm in score_list) + \
                         "\\end{enumerate}"
        else:
            score_info = ""
        score_info = "\\subsection*{\\tScoring}\n" + score_info

        self.contest.supply("contestoverview", def_latex("printscoring",
                                                         score_info))
        self.contest.supply("contestoverview",
                            def_latex("contestname", self.get_contestname))

    def credentials_supplement(self, users, attach_statements):
        def for_user(u):
            return "\n".join(documents(u, l) for l in u.primary_statements)

        def documents(u, l):
            return "\\def\\TemplateLanguage{%s}" % l + \
                   "\\printoverviewpage{%s}{%s, %s}{%s}" % \
                       (u.username, u.lastname, u.firstname, u.password) + \
                   statements(u, l)

        def statements(u, l):
            if not attach_statements:
                return ""

            return "".join("\\mycleardoublepage\\includepdf[pages=-]{%s}" %
                               os.path.relpath(t._statements[l].file_,
                                               os.getcwd())
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
        if self.contest.ignore_latex:
            return

        teams = {}

        for u in self.contest.users.values():
            team_name = u.team

            if team_name not in teams:
                teams[team_name] = []
            teams[team_name].append(u)

        if not os.path.exists("overview"):
            os.mkdir("overview")

        with chdir("overview"):
            self.supply_overview()
            self.contest._build_supplements_for_key("contestoverview")

            shutil.copy(os.path.join(os.path.dirname(__file__), "logo.eps"),
                        os.path.join(os.getcwd(), "logo.eps"))

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
                # Provide translation-{de,en}.tex
                shutil.copy(os.path.join(os.path.dirname(__file__),
                                            "translation-de.tex"),
                                            "translation-de.tex")
                shutil.copy(os.path.join(os.path.dirname(__file__),
                                            "translation-en.tex"),
                                            "translation-en.tex")

                lang_code = str.lower(team.code)
                if lang_code == "unaffiliated":
                    lang_code = "en"
                user_list = users
                self.contest._build_supplements_for_key("credentials")
                self.contest._build_supplements_for_key("lang")
                self.contest.compile(filename)


# Translated strings, mirroring translation-{en,de}.tex (only the subset
# that the typst contestheader currently uses).
LG_TRANSLATIONS = {
    "en": {
        "task": "Task",
        "subtask": "Subtask",
        "point": "point",
        "points": "points",
        "sample": "Sample",
        "samples": "Samples",
        "program": "Your program",
        "return": "Return value",
        "explanation": "Explanation",
        "limits": "Limits",
        "time": "Time",
        "memory": "Memory",
        "input": "Input",
        "output": "Output",
        "constraints": "Constraints",
        "and": " and",
        "ands": ", and",
        "implementation": "Implementation",
        "scoring": "Scoring",
        "samplegrader": "Sample grader",
    },
    "de": {
        "task": "Aufgabe",
        "subtask": "Teilaufgabe",
        "point": "Punkt",
        "points": "Punkte",
        "sample": "Beispiel",
        "samples": "Beispiele",
        "program": "Dein Programm",
        "return": "Rückgabewert",
        "explanation": "Erläuterung",
        "limits": "Limits",
        "time": "Zeit",
        "memory": "Speicher",
        "input": "Eingabe",
        "output": "Ausgabe",
        "constraints": "Beschränkungen",
        "and": " und",
        "ands": " und",
        "implementation": "Implementierung",
        "scoring": "Bewertung",
        "samplegrader": "Testprogramm",
    },
}


# Typst functions of the lg template; supplied after all data so that the
# closures can refer to taskinfo's definitions (mirrors contestheader.tex).
LG_TYPST = r"""
#let highlightcolor = rgb("#c20e1a")

// Semantic helpers so statements stay free of styling numbers (mirrors the
// official IOI typst template's philosophy: statements are pure semantics).
// TeX statements write `{\LARGE\bfseries \taskname}` and an explicit
// `\vspace{1em}` on top of `\parskip=\smallskipamount`; typst has no
// additive par glue, so the absorbed total is defined once here and
// statements only call `#tasktitle[...]` / `#sep`.
#let tasktitle(body) = text(size: 1.4em, weight: "bold")[#body]
#let sep = v(1.45em)

#let taskheader(body) = {
  // Fira Sans text + Fira Math, mirroring the latex template.
  set text(font: "Fira Sans", size: 10pt)
  // NOTE: `set math(font:)` inside a function body is rejected by the
  // trimmed typst binary ("expected function, found module"); setting the
  // text font on equations achieves the same (math picks up the family's
  // OpenType MATH table).
  show math.equation: set text(font: "Fira Math")
  set par(spacing: 0.5em, justify: true)
  set par(first-line-indent: 0em)
  set heading(numbering: none, supplement: none)
  // NOTE: the trimmed binary rejects heading above/below overrides; the
  // heading's built-in spacing is used as-is (same for every heading,
  // including Samples and Limits, so their above-gaps match by structure).
  // The trimmed typst binary ignores above/below spacing on blocks around
  // headings; explicit v() skips restore the latex template's rhythm.
  show heading: it => {
    v(if it.level == 1 { 1.2em } else { 0.9em })
    it
    v(0.45em)
  }
  show raw: set text(font: "Fira Mono", size: 9pt)
  set page(
    paper: "a4",
    margin: (left: 2.5cm, right: 2.5cm, top: 3.25cm, bottom: 1.5cm),
    header: context align(right)[
      // Fixed-height box pins the header bottom to match the TeX
      // reference (ink bottom ~74pt from page top); v(1fr) pushes the
      // grid down inside it (grid align inside the header is unreliable
      // in the trimmed binary).
      #box(height: 65pt)[
        #v(1fr)
        #grid(
          columns: (auto, 1pt, auto),
          // gaps measured from the TeX render: logo->bar ~13pt,
          // bar->text ~1em (tikz outer xsep)
          column-gutter: (13pt, 1em),
          inset: 0pt,
          align: horizon,
          // NOTE: scale() inside a header grid cell gets applied twice
          // (image is fitted to the cell first); set the width directly.
          if lg-logo != none { image("logo-typst.pdf", width: 44.1pt) },
          box(width: 100%, height: 2.9em, fill: highlightcolor),
          text(fill: luma(102), size: 10pt)[
            // paragraph line breaks give the same leading as TeX's \\
            #align(start)[
              #text(weight: "bold")[#contestname]\
              #t-task:#h(0.5em)#text(weight: "bold")[#taskname]
            ]
          ],
        )
      ]
    ],
    footer: context {
      // NOTE: do not raise the footer with v() — negative skips here
      // overflow the footer box and collide with full pages (e.g. the
      // sample table reaching the bottom margin).
      align(center)[
        #counter(page).at(here()).first()/#counter(page).final().first()
      ]
    },
  )
  set list(marker: box(width: 4pt, height: 4pt, fill: highlightcolor))
  body
}

// Fancy testcase table: the box wraps ONLY the header row (like TeX's
// \hline above/below the header with | at the outer column edges), an
// empty spacer column between Input and Output, and gray-filled sample
// cells (mirrors mktestcasetable / \cellcolor[gray]{.9}). The trimmed
// typst binary draws stroke dicts on table cells as FULL outlines, so
// the header rules are strokes on the header cell blocks themselves.
#let testcasetable() = {
  // raw blocks have their own padding by default; drop it so the cell
  // inset alone controls the text padding (like verbatim in latex).
  show raw: set block(inset: 0pt)
  table(
    // gray cells fill to the margins, gap between them == vertical
    // row gutter (3.3pt), centered by the symmetric 1fr columns
    columns: (1fr, 3.3pt, 1fr),
    inset: 0pt,
    row-gutter: 3.3pt,
    stroke: none,
    fill: (x, y) => if y > 0 and x != 1 { luma(229) },
    table.header(
      block(width: 100%, inset: (x: 4pt, y: 3pt),
            stroke: (top: 0.5pt + black, bottom: 0.5pt + black,
                    left: 0.5pt + black))[#align(center)[#text(font: "Fira Sans", weight: "regular")[#t-input]]],
      // spacer header cell: nbsp keeps its height in sync with the labels
      block(width: 100%, inset: (x: 4pt, y: 3pt),
            stroke: (top: 0.5pt + black, bottom: 0.5pt + black))[#text(size: 10pt)[#sym.space.nobreak]],
      block(width: 100%, inset: (x: 4pt, y: 3pt),
            stroke: (top: 0.5pt + black, bottom: 0.5pt + black,
                    right: 0.5pt + black))[#align(center)[#text(font: "Fira Sans", weight: "regular")[#t-output]]],
    ),
    ..{
      for i in range(numsamples) {
        (
          // box() makes the cell atomic so an input/output pair never
          // splits across pages (the trimmed binary rejects block
          // breakable:/blocked: arguments)
          box(block(width: 100%, inset: (x: 4pt, y: 5pt))[#{tc-in.at(i)}]),
          [],
          box(block(width: 100%, inset: (x: 4pt, y: 5pt))[#{tc-out.at(i)}]),
        )
      }
    },
  )
}

#let showcases() = {
  // TeX: caption is a \subsection* in the longtable firsthead with
  // LTpre=0pt and no \bigskip in \showcases, so the space above
  // "Samples" equals the space above any other heading (e.g. Limits).
  heading(level: 2, numbering: none)[
    #(if numsamples == 1 { t-sample } else { t-samples })
  ]
  testcasetable()
}

#let showlimits() = {
  heading(level: 2, numbering: none)[#t-limits]
  // paragraph line breaks (natural leading) match TeX's \\
  align(start)[
    #t-time: #timelimit\
    #t-memory: #memlimit
  ]
}

#let standardpart() = {
  showcases()
  showlimits()
}

// Subtask headings with hanging layout (mirrors \subtask/\sthelper)
#let subtask(body) = {
  sub-counter.step()
  context {
    let n = sub-counter.get().first()
    let pts = subtaskpoints(n)
    let unit = if pts == "1" { t-point } else { t-points }
    // Run-in label, like \st@sk in the lg template: bold label, then body;
    // continuation lines get a hanging indent so they align under the body.
    // (block above/below spacing is ignored by the trimmed binary -> v())
    v(0.7em)
    block({
      set par(hanging-indent: 4.2em, first-line-indent: 0em)
      text(weight: "bold", [#t-subtask #n (#pts #unit).])
      h(0.5em)
      body
    })
  }
}
"""


# task-maker-rust statement API aliases (see the tmr docs
# ioi-task-format.typ); supplied after LG_TYPST so they can wrap it.
# tmr takes this data from gen.toml/task.toml; here it comes from our
# taskinfo instead, so tmr arguments that carry such data are accepted
# and ignored (noted per alias). The statement content itself (titles,
# constraint values) still uses our taskinfo accessors.
TMR_TYPST = r"""
// tmr wraps the statement body in `#statement[...]`; that is our
// taskheader.
#let statement(body) = taskheader(body)

// Localized section headings. tmr uses bare content values (#constraints,
// not #constraints()); the heading elements are created at definition
// time, i.e. before taskheader's `set heading(numbering: none)` applies,
// so numbering is disabled explicitly here.
#let implementation = heading(level: 2, numbering: none)[#t-implementation]
#let constraints = heading(level: 2, numbering: none)[#t-constraints]
#let scoring = heading(level: 2, numbering: none)[#t-scoring]
#let explanation = heading(level: 2, numbering: none)[#t-explanation]
#let samplegrader = heading(level: 2, numbering: none)[#t-samplegrader]

// tmr renders a format line under "Input format"/"Output format"; we
// mirror the lg section headings and place the body underneath.
#let inputformat(body) = {
  heading(level: 2, numbering: none)[#t-input]
  body
}
#let outputformat(body) = {
  heading(level: 2, numbering: none)[#t-output]
  body
}

// Highlight boxes (plain typst stand-ins for the tmr template boxes).
#let note(body) = {
  v(0.5em)
  block(width: 100%, inset: (x: 8pt, y: 6pt), fill: luma(245),
        stroke: 0.5pt + luma(180))[#body]
  v(0.5em)
}
#let warn(body) = {
  v(0.5em)
  block(width: 100%, inset: (x: 8pt, y: 6pt), fill: rgb("#fff4f4"),
        stroke: 0.8pt + highlightcolor)[#body]
  v(0.5em)
}

// tmr reads the sample count from gen.toml; here it is numsamples, so
// any argument is accepted and ignored.
#let examples(..args) = showcases()

// tmr passes each subtask's gen.toml constants to its lambda; there are
// no named constants here, so the lambda gets an empty dict and reads
// values via currconstraints()/currconstraint(name). index-start is
// accepted but ignored: lg numbers subtasks from 1.
#let subtasks(fs, index-start: 0) = {
  for f in fs {
    subtask(f((:)))
  }
}

// OIS-style subtasks with explicit points; the points come from the task
// config here, so the second argument is ignored.
#let ois-subtasks(fs, points) = subtasks(fs)

// Grader function signatures: one boxed raw line per (lang, signature).
#let signatures(sigs) = {
  v(0.5em)
  for s in sigs {
    block(width: 100%, inset: (x: 6pt, y: 3pt),
          stroke: 0.5pt + luma(180))[#raw(s.at(1))]
    v(0.3em)
  }
}

// tmr hides the editorial unless show_solutions=true is passed; we have
// no such switch here, so it is always shown.
#let editorial(body) = {
  heading(level: 1, numbering: none)[Editorial]
  body
}
"""
