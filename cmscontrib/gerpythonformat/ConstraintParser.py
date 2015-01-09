#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2014 Tobias Lenz <t_lenz94@web.de>
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


class Constraint(object):
    def __init__(self, variables, min, max):
        self.variables = variables
        self.min = min
        self.max = max

    def uncompress(self):
        return {v: [self.min, self.max] for v in self.variables}

    def latex(self):
        s = "$"
        if self.max is None:
            s += ", ".join(self.variables)
            s += r"\ge {}".format(self.pretty(self.min))
        else:
            if self.min is not None:
                s += r"{}\le ".format(self.min)
            s += ", ".join(self.variables)
            s += r"\le {}".format(self.pretty(self.max))
        s += "$"
        return s

    def pretty(self, a):
        s = "{}".format(a)
        m = len(s) % 3

        t = ""
        for i in range(0, len(s)):
            if (i + 3 - m) % 3 == 0 and i != 0:
                t += "\,"
            t += s[i]
        return t


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
                min = int(min)
                if tokens.pop() != ",":
                    raise ValueError("Malformed constraint string.")

            max = tokens.pop()
            if max == "]":
                max = None
            else:
                max = int(max)
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
