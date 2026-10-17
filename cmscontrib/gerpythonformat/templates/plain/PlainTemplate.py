#!/usr/bin/env python3

# Programming contest management system
# Copyright © 2013-2021 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2016 Fabian Gundlach <320pointsguy@gmail.com>
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

""" Plain template
Commands for standard tasks
"""
from cmscontrib.gerpythonformat.templates.Template import Template
from cmscontrib.gerpythonformat.Supplement import def_latex, input_latex, \
    typst_raw_strings
from cmscontrib.gerpythonformat.ConstraintParser import Constraint

from collections import OrderedDict

import functools
import io
import os
import shutil
import copy

class PlainTemplate(Template):
    def __init__(self, contest):
        super(PlainTemplate, self).__init__(contest)

    def mk_tex_cases_supp(self, task):
        def tex_cases_supp():
            """ LaTeX supplement containing all testcases created with
            save = True
            """
            inmacro = "\\def\\tcin#1{\\ifcase#1"
            outmacro = "\\def\\tcout#1{\\ifcase#1"
            for c in task.saved:
                # I'm sure about the leading "\or"
                inmacro += "\\or\\verbatiminput{" + \
                    os.path.relpath(c.infile) + "}"
                outmacro += "\\or\\verbatiminput{" + \
                    os.path.relpath(c.outfile) + "}"
            inmacro += "\\else\\fi}"
            outmacro += "\\else\\fi}"

            return inmacro + "\n" + outmacro + "\n"
        return tex_cases_supp

    def supply_cases(self, task):
        """ Actually supply tex_cases_supp for all latex documents
        """
        task.supply("latex", self.mk_tex_cases_supp(task))

    def mk_typst_cases_supp(self, task):
        def typst_cases_supp():
            """ Typst supplement containing all testcases created with
            save = True (as raw blocks).
            """
            def read(path):
                try:
                    with io.open(path, "r", encoding="utf-8") as f:
                        return f.read()
                except OSError:
                    return ""

            ins = [lambda p=c.infile: read(p) for c in task.saved]
            outs = [lambda p=c.outfile: read(p) for c in task.saved]

            out = "#let tc-in = {}\n".format(typst_raw_strings(ins)())
            out += "#let tc-out = {}\n".format(typst_raw_strings(outs)())
            out += "#let numsamples = {}\n".format(len(task.saved))
            return out
        return typst_cases_supp

    def supply_cases_typst(self, task):
        """ Actually supply typst_cases_supp for all typst documents
        """
        task.supply("typst", self.mk_typst_cases_supp(task))

    def get_contestname(self):
        return self.contest._description

    def ontask(self, task):
        super(PlainTemplate, self).ontask(task)

        def si(x, y):
            return "\\SI{" + str(x) + "}{" + str(y) + "}"

        task.latex_timelimit = lambda: si(task._timelimit, "s")
        task.latex_memorylimit = lambda: si(task._memorylimit, "MiB")

        self.supply_cases(task)
        task.supplement_file("latex", "taskinfo.tex")
        shutil.copy(os.path.join(os.path.dirname(__file__), "header.tex"),
                    os.path.join(task.wdir, "header.tex"))
        shutil.copy(os.path.join(os.path.dirname(__file__),
                                 "taskinfo-base.tex"),
                    os.path.join(task.wdir, "taskinfo-base.tex"))
        task.supply("latex", r"\input{taskinfo-base.tex}")
        task.supply("latex", def_latex("basicheader",
                                       input_latex("header.tex")))
        task.supply_latex("taskname", task.simple_query("name"))
        task.supply_latex("contestname", self.get_contestname)
        task.supply_latex("timelimit", task.latex_timelimit)
        task.supply_latex("memlimit", task.latex_memorylimit)
        task.supply_latex("inputwidth",
                          functools.partial(self.inputwidth, task))
        task.supply_latex("outputwidth",
                          functools.partial(self.outputwidth, task))

        self.initconstraint(task)
        self.initsubtaskinfo(task)
        self.mktestcasetable(task)

        # --- typst support (mirror of the latex setup above) ---
        task.supplement_file("typst", "taskinfo.typ")
        shutil.copy(os.path.join(os.path.dirname(__file__), "header.typ"),
                    os.path.join(task.wdir, "header.typ"))
        task.supply("typst", '#import "header.typ": *\n')
        task.supply_typst("taskname", task.simple_query("name"))
        task.supply_typst("contestname", self.get_contestname)
        task.supply("typst", lambda: "#let timelimit = \"{}\"\n".format(
            self.typst_text("{} s".format(task._timelimit), task)))
        task.supply("typst", lambda: "#let memlimit = \"{}\"\n".format(
            self.typst_text("{} MiB".format(task._memorylimit), task)))
        task.supply("typst", lambda: "#let inputwidth = \"{}\"\n".format(
            self.inputwidth(task)))
        task.supply("typst", lambda: "#let outputwidth = \"{}\"\n".format(
            self.outputwidth(task)))

        self.supply_cases_typst(task)
        self.initconstraint_typst(task)
        self.initsubtaskinfo_typst(task)
        self.supply_typst_accessors(task)

    def typst_text(self, s, task):
        """Format a limit like siunitx would render it in the document:
        siunitx's default decimal marker is a comma, independently of the
        language, so always use one (mirrors the latex output exactly).
        """
        return s.replace(".", ",").replace("\\", "\\\\").replace('"', '\\"')

    def inputwidth(self, task):
        try:
            return task.inputwidth
        except AttributeError:
            return "5cm"

    def outputwidth(self, task):
        try:
            return task.outputwidth
        except AttributeError:
            return "5cm"

    def initconstraint(self, task):
        """ Set things up, so that the constraint command can be
        used afterwards
        """

        task.supply("latex", functools.partial(self.latex_constraints, task))

        task.register_supplement("checker", "cpp")
        task.supplement_file("checker", "constraints.h")
        task.supply("checker", task.cpp_constraints)

    def initconstraint_typst(self, task):
        """ Set things up for typst, so that the constraint functions can
        be used afterwards (mirrors initconstraint)
        """

        task.supply("typst",
                    functools.partial(self.typst_constraints, task))

    def find_constraints(self, task):
        res = []
        res += task.constraints
        for s in task.subtasks:
            res += s.constraints
            for g in s.groups:
                res += g.constraints
        return res

    def curr_scope_constraints(self, i, constraint_lists, typesetting):
        l = []
        for cl in constraint_lists:
            for c in cl.constraints:
                for v in c.variables:
                    if v.typeset is not None:
                        typesetting[v.val] = v.typeset

            if not cl.silent:
                l += cl.constraints

        d = {}

        # Two auxiliary generators
        def inj(l):
            yield []

            for i in range(0, len(l)):
                _l = l[:]
                first = _l.pop(i)

                for rest in inj(_l):
                    yield [first] + rest

        def restrictions(c):
            for v in inj(c.variables):
                if v:
                    for var in v:
                        if var.typeset is None:
                            try:
                                var.typeset = typesetting[var.val]
                            except KeyError:
                                pass

                    yield Constraint(v, c.min, c.max)

        for _c in l:
            # For simple user access we "hardcode" all possible
            # reorderings/subsets of the variables
            # TODO: should we use LuaTeX's Lua facilities to implement argument
            # parsing on the TeX side instead?
            for c in restrictions(_c):
                v = ",".join(v.val for v in c.variables)

                if v in d:
                    d[v].merge(c)
                else:
                    d[v] = c

        res = ""
        for v, c in d.items():
            res += r"\makescopedconstraint{" + "{}".format(i) + "}{" + v + \
                   "}{" + c.latex() + "}\n"

        # Collection of all constraints in this scope, as appearing in the
        # input
        res += r"\makescopedconstraint{" + "{}".format(i) + "}{" + "@ll" + "}{"
        keys = OrderedDict.fromkeys(",".join(v.val for v in c.variables) for c in l)
        res += PlainTemplate.constraint_join([d[v].latex() for v in keys])
        res += "}\n"

        # non-fancy version of this that only uses ',' as separator
        res += r"\makescopedconstraint{" + "{}".format(i) + "}{" + "@ll*" + "}{"
        keys = OrderedDict.fromkeys(",".join(v.val for v in c.variables) for c in l)
        res += ", ".join([d[v].latex() for v in keys])
        res += "}\n"
        return res

    def scoped_constraints(self, task):
        r = []
        acc_constraints = {}

        def constraint_values_for_scope(i, scope_list):
            curr_constraints = acc_constraints.copy()

            for cl in scope_list:
                for c in cl.constraints:
                    for var in c.variables:
                        try:
                            curr = curr_constraints[var]
                        except KeyError:
                            curr = (None, None)

                        curr_constraints[var.val] = (c.min or curr[0],
                                                     c.max or curr[1])

            for key, value in curr_constraints.items():
                if value[0] is not None:
                    r.append(r"\makescopedconstraintlower{" + "{}".format(i) +
                             "}{" + key + "}{$" + Constraint.pretty(value[0]) +
                             "$}\n")
                if value[1] is not None:
                    r.append(r"\makescopedconstraintupper{" + "{}".format(i) +
                             "}{" + key + "}{$" + Constraint.pretty(value[1]) +
                             "$}\n")
                if value[0] == value[1] and value[0] is not None:
                    r.append(r"\makescopedconstraintvalue{" + "{}".format(i) +
                             "}{" + key + "}{$" + Constraint.pretty(value[0]) +
                             "$}\n")
            return curr_constraints

        typesetting = {}

        r.append(self.curr_scope_constraints(0, task.constraints, typesetting))
        acc_constraints = constraint_values_for_scope(0, task.constraints)

        for i, s in enumerate([s2 for s2 in task.subtasks if not s2.sample]):
            r.append(self.curr_scope_constraints(i + 1, s.constraints,
                     copy.copy(typesetting)))
            constraint_values_for_scope(i + 1, s.constraints)

        return "".join(r)

    def latex_constraints(self, task):
        # Indexed access to constraints
        res = ""
        nr = 1
        for c in self.find_constraints(task):
            if not c.silent:
                s = PlainTemplate.constraint_join(c.latex())
                res += r"\expandafter\expandafter\def\csname conshelper" \
                    + str(nr) + r"\endcsname{" + s + "}\n"
                nr += 1

        return res + self.scoped_constraints(task)

    def initsubtaskinfo(self, task):
        def points(s):
            return s.scoreinfo()

        def subtaskinfo():
            r = ""
            st = [s for s in task.subtasks if not s.sample]

            for i, s in enumerate(st):
                r += r"\expandafter\def\csname stphelper__" + \
                     "{}".format(i + 1) + r"\endcsname{" + points(s) + "}\n"

            return r

        task.supply("latex", subtaskinfo)

    def supply_case_table(self, task,
                          start="\\begin{tabular}{|p{\\inputwidth}|"
                                "p{\\outputwidth}|}\n\\hline Input & Output "
                                "\\\\\\hline",
                          end="\\end{tabular}",
                          beforeeachcell="\\vspace{-2ex}",
                          aftereachcell="\\vspace{-2ex}",
                          aftereachline="\\\\\\hline",
                          beforeeachline="",
                          sep="&"):
        """ Create a customized testcase table

        beforeeachline is emitted at the start of every body row (before
        the first cell); templates use it to e.g. typeset a case number
        cell as "N&".
        """
        def tct():
            r = ""
            r += start
            for i in range(1, len(task.saved) + 1):
                r += beforeeachline
                r += beforeeachcell + "\\tcin{" + str(i) + "}" + aftereachcell
                r += sep
                r += beforeeachcell + "\\tcout{" + str(i) + "}" + aftereachcell
                r += aftereachline
            r += end
            return r

        def tcn():
            return "\\newcount\\numsamples \\numsamples={}".format(
                len(task.saved))

        task.supply("latex", def_latex("testcasetable", tct))
        task.supply("latex", tcn)

    def mktestcasetable(self, task):
        """ Provide the standard testcase table
        This method can be overriden in other templates to get more "fancy"
        formats
        """
        self.supply_case_table(task)

    @staticmethod
    def constraint_join(L):
        if len(L) == 0:
            return ""
        if len(L) == 1:
            return L[0]

        return ", ".join(L[:-1]) + (r"\tAND/ " if len(L) == 2
                                    else r"\tANDs/ ") + L[-1]

    # ------------------------------------------------------------------
    # typst support: mirrors of the latex constraint/subtask/table machinery
    # ------------------------------------------------------------------

    @staticmethod
    def typst_constraint_join(L):
        """Typst equivalent of constraint_join: joins math strings
        (each already enclosed in $..$) with commas; the result becomes
        an array of items that the renderers join with a localized "and".
        """
        return ", ".join(L)

    def typst_curr_scope_constraints(self, i, constraint_lists, typesetting):
        """Typst version of curr_scope_constraints; returns typst source
        defining entries of the scoped-constraints dict for scope i.
        """
        l = []
        for cl in constraint_lists:
            for c in cl.constraints:
                for v in c.variables:
                    if v.typeset is not None:
                        typesetting[v.val] = v.typeset

            if not cl.silent:
                l += cl.constraints

        d = {}

        # Two auxiliary generators
        def inj(l):
            yield []

            for i in range(0, len(l)):
                _l = l[:]
                first = _l.pop(i)

                for rest in inj(_l):
                    yield [first] + rest

        def restrictions(c):
            for v in inj(c.variables):
                if v:
                    for var in v:
                        if var.typeset is None:
                            try:
                                var.typeset = typesetting[var.val]
                            except KeyError:
                                pass

                    yield Constraint(v, c.min, c.max)

        for _c in l:
            # For simple user access we "hardcode" all possible
            # reorderings/subsets of the variables
            for c in restrictions(_c):
                v = ",".join(v.val for v in c.variables)

                if v in d:
                    d[v].merge(c)
                else:
                    d[v] = c

        res = ""
        for v, c in d.items():
            res += self.typst_constraint_entry(i, v, c.typst())

        # Collection of all constraints in this scope, as appearing in the
        # input
        keys = OrderedDict.fromkeys(
            ",".join(v.val for v in c.variables) for c in l)
        res += self.typst_constraint_entry(
            i, "@ll", PlainTemplate.typst_constraint_join(
                [d[v].typst() for v in keys]))

        # non-fancy version of this that only uses ',' as separator
        res += self.typst_constraint_entry(
            i, "@ll*", ", ".join([d[v].typst() for v in keys]))
        return res

    @staticmethod
    def typst_constraint_entry(i, v, full):
        """One entry of the scoped-constraints dict; `full` is a comma
        separated list of math strings (each including $ delimiters). The
        trailing comma keeps single-element entries arrays in typst. Keys
        encode scope and variable as a single string (typst dict keys must
        be strings).
        """
        if full and not full.rstrip().endswith(","):
            full += ","
        return '"{}:{}": ({}),\n'.format(i, v, full)

    def typst_scoped_constraints(self, task):
        """Typst version of scoped_constraints.

        Produces entries for four dicts (full/upper/lower/value), mirroring
        the four families of scoped constraint macros of the latex version.
        """
        full_entries = []
        acc_constraints = {}

        def constraint_values_for_scope(i, scope_list):
            curr_constraints = acc_constraints.copy()

            for cl in scope_list:
                for c in cl.constraints:
                    for var in c.variables:
                        try:
                            curr = curr_constraints[var]
                        except KeyError:
                            curr = (None, None)

                        curr_constraints[var.val] = (c.min or curr[0],
                                                    c.max or curr[1])

            for key, value in curr_constraints.items():
                if value[0] is not None:
                    lower_entries.append(
                        '"{}:{}": (${}$,),\n'.format(
                            i, key, Constraint.typst_bound(value[0])))
                if value[1] is not None:
                    upper_entries.append(
                        '"{}:{}": (${}$,),\n'.format(
                            i, key, Constraint.typst_bound(value[1])))
                if value[0] == value[1] and value[0] is not None:
                    value_entries.append(
                        '"{}:{}": (${}$,),\n'.format(
                            i, key, Constraint.typst_bound(value[0])))
            return curr_constraints

        lower_entries = []
        upper_entries = []
        value_entries = []

        typesetting = {}

        full_entries.append(self.typst_curr_scope_constraints(
            0, task.constraints, typesetting))
        acc_constraints = constraint_values_for_scope(0, task.constraints)

        for i, s in enumerate([s2 for s2 in task.subtasks if not s2.sample]):
            full_entries.append(self.typst_curr_scope_constraints(
                i + 1, s.constraints, copy.copy(typesetting)))
            constraint_values_for_scope(i + 1, s.constraints)

        def d(entries):
            return "(\n" + "".join(entries) + ")\n"

        return ("#let scoped-constraints = " + d(full_entries)
                + "#let scoped-lower = " + d(lower_entries)
                + "#let scoped-upper = " + d(upper_entries)
                + "#let scoped-value = " + d(value_entries))

    def typst_constraints(self, task):
        """Supply for typst containing all constraints of the task
        (mirrors latex_constraints).
        """
        return self.typst_scoped_constraints(task)

    def supply_typst_accessors(self, task):
        """Supply generic typst accessor functions for constraints,
        subtask points, etc. (mirrors the macros of taskinfo-base.tex
        plus \currconstraint... of the lg contestheader).
        """
        task.supply("typst", TYPST_ACCESSORS)

    def initsubtaskinfo_typst(self, task):
        """Provide the points of all non-sample subtasks (mirrors
        initsubtaskinfo).
        """
        def points(s):
            return s.scoreinfo()

        def subtaskinfo():
            st = [s for s in task.subtasks if not s.sample]
            return "#let subtask-points = ({})\n".format(
                ", ".join('"{}"'.format(points(s)) for s in st))

        task.supply("typst", subtaskinfo)


# Generic typst accessor functions; defined after all data so that they
# can refer to it. Mirrors the LaTeX macros of taskinfo-base.tex and
# contestheader.tex (constraint/subtask access, sample tables, limits).
TYPST_ACCESSORS = r"""
#let sub-counter = counter("subtask-cnt")
#let subtask-count() = sub-counter.get().first()

// Translated join words; rebound by templates that provide translations
#let t-and = [and]
#let t-ands = [and]

// Joins constraint content items like \currconstraints does in latex:
// "a, b and c" (with t-and/t-ands providing the localized "and").
#let join-cons(items, simple: false) = {
  let out = []
  for i in range(items.len()) {
    if i > 0 {
      let last = i == items.len() - 1
      if simple or not last { out += [, #h(0.33em)] }
      else if i == 1 { out += [#h(0.33em)#t-and#h(0.33em)] }
      else { out += [, #h(0.33em)#t-ands#h(0.33em)] }
    }
    out += items.at(i)
  }
  out
}

#let scoped-get(d, i, key) = d.at(str(i) + ":" + key, default: ())

#let currconstraint(name) = context join-cons(scoped-get(scoped-constraints, subtask-count(), name))
#let currconstraints() = context join-cons(scoped-get(scoped-constraints, subtask-count(), "@ll"))
#let currconstraints-simple() = context join-cons(scoped-get(scoped-constraints, subtask-count(), "@ll*"), simple: true)
#let currconstraintupper(name) = context join-cons(scoped-get(scoped-upper, subtask-count(), name))
#let currconstraintlower(name) = context join-cons(scoped-get(scoped-lower, subtask-count(), name))
#let currconstraintvalue(name) = context join-cons(scoped-get(scoped-value, subtask-count(), name))

#let subtaskpoints(n) = {
  if n - 1 < subtask-points.len() { subtask-points.at(n - 1) } else { "" }
}

// Simple default subtask heading (rebound by the lg template)
#let subtask(body) = {
  sub-counter.step()
  context {
    let n = sub-counter.get().first()
    let pts = subtaskpoints(n)
    block(above: 0.7em)[
      #text(weight: "bold")[Subtask #n (#pts points).]#h(0.5em)#body
    ]
  }
}

// Simple testcase table fallback (plain template)
#let plain-testcasetable() = table(
  columns: (length(inputwidth), length(outputwidth)),
  align: (left, left),
  stroke: 0.5pt + black,
  inset: (x: 4pt, y: 2pt),
  [Input], [Output],
  ..for i in range(numsamples) {
    (tc-in.at(i), tc-out.at(i))
  }
)

#let testcasetable() = plain-testcasetable()

#let showcases() = {
  align(center)[#text(weight: "bold", size: 1.14em)[
    #(if numsamples == 1 { [Sample] } else { [Samples] })
  ]]
  block(spacing: 0.7em)[]
  testcasetable()
}

#let showlimits() = {
  heading(level: 2, numbering: none)[Limits]
  grid(
    columns: 1,
    row-gutter: 0pt,
    align(start)[Time: #timelimit],
    align(start)[Memory: #memlimit],
  )
}

#let standardpart() = {
  showcases()
  showlimits()
}
"""
