#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2017 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013 Fabian Gundlach <320pointsguy@gmail.com>
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


class Constraint(object):
    def __init__(self, variables, min, max):
        self.variables = variables
        self.min = min
        self.max = max

    def uncompress(self):
        return {v: [Constraint.eval(self.min),
                    Constraint.eval(self.max)] for v in self.variables}

    def merge(self, rhs):
        if rhs.min is not None:
            self.min = rhs.min

        if rhs.max is not None:
            self.max = rhs.max

    def latex(self):
        s = "$"
        if self.max is not None and self.max == self.min:
            s += ", ".join(self.variables)
            s += r"= {}".format(Constraint.pretty(self.min))

        elif self.max is None:
            s += ", ".join(self.variables)
            s += r"\ge {}".format(Constraint.pretty(self.min))
        else:
            if self.min is not None:
                s += r"{}\le ".format(Constraint.pretty(self.min))
            s += ", ".join(self.variables)
            s += r"\le {}".format(Constraint.pretty(self.max))
        s += "$"
        return s

    @staticmethod
    def pretty(s):
        """
        Try to apply digit grouping to numbers for TeX display

        This is of course not perfect, for example one can trick it using
        something like 1{}000
        """
        l = []
        curr_token = ""
        num_mode = False

        digits = {chr(ord('0') + i) for i in range(0, 10)}

        for c in s:
            if (c in digits) != num_mode:
                l.append(Constraint.grp(curr_token)
                         if num_mode else curr_token)
                curr_token = ""
                num_mode = not num_mode

            curr_token += c

        l.append(Constraint.grp(curr_token) if num_mode else curr_token)

        return "".join(l)

    @staticmethod
    def grp(s):
        """
        Group s into blocks of three characters each, separated by 1/6th quad
        This should be applied to numbers
        """
        m = len(s) % 3

        t = ""
        for i in range(0, len(s)):
            if (i + 3 - m) % 3 == 0 and i != 0:
                t += "\,"
            t += s[i]
        return t

    @staticmethod
    def eval(s):
        if s is None:
            return None

        coding = {"^": "**",
                  "{": "(",
                  "}": ")"}

        for old, new in coding.iteritems():
            s = s.replace(old, new)

        return eval(s)


class ConstraintList(object):
    def __init__(self, constraints, silent):
        self.constraints = constraints
        self.silent = silent

    def uncompress(self):
        res = {}
        for c in self.constraints:
            res.update(c.uncompress())
        return res

    def latex(self):
        return [c.latex() for c in self.constraints]

    @staticmethod
    def tokenize(s):
        tokens = []

        token = ""
        for c in s:
            if c == " " or c == "\n":
                continue
            if c == "[" or c == "]" or c == "," or c == ":":
                if len(token) > 0:
                    tokens.append(token)
                tokens.append(c)
                token = ""
            else:
                token += c
        if len(token) > 0:
            tokens.append(c)

        return tokens

    @classmethod
    def parse(cls, s, silent):
        tokens = cls.tokenize(s)
        # Reverse the token list and use it as a stack from now on.
        tokens.reverse()

        res = []

        while len(tokens) > 0:
            char = ""
            variables = []
            while True:
                variables.append(tokens.pop())
                char = tokens.pop()
                if char != ",":
                    break
            if char != ":":
                raise ValueError("Malformed constraint string.")
            if tokens.pop() != "[":
                raise ValueError("Malformed constraint string.")

            min = tokens.pop()
            if min == ",":
                min = None
            else:
                if tokens.pop() != ",":
                    raise ValueError("Malformed constraint string.")

            max = tokens.pop()
            if max == "]":
                max = None
            else:
                if tokens.pop() != "]":
                    raise ValueError("Malformed constraint string.")

            if min is None and max is None:
                raise ValueError("You have to specify the minimum or the "
                                 "maximum value.")

            res.append(Constraint(variables, min, max))

        return ConstraintList(res, silent)


def merge_constraints(cl1, cl2):
    res = dict(cl1)
    for var, ran in cl2.iteritems():
        if var in res:
            a, b = res[var]
        if ran[0] is not None:
            a = ran[0]
        if ran[1] is not None:
            b = ran[1]
        res[var] = (a, b)
    return res
