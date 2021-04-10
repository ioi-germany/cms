#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

""" Plain template
Commands for standard tasks
"""
from cmscontrib.gerpythonformat.templates.Template import Template
from cmscontrib.gerpythonformat.Supplement import def_latex, input_latex
from cmscontrib.gerpythonformat.ConstraintParser import Constraint, merge

from collections import OrderedDict

import functools
import os
import shutil
import copy

from six import iteritems

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

    def get_contestname(self):
        return self.contest._description

    def ontask(self, task):
        super(PlainTemplate, self).ontask(task)
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
        for v, c in iteritems(d):
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
            f = s.max_score()
            i = int(f+.1)
            assert(abs(i - f) < 1e-4)

            return "{}".format(i)

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
                          sep="&"):
        """ Create a customized testcase table
        """
        def tct():
            r = ""
            r += start
            for i in range(1, len(task.saved) + 1):
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
