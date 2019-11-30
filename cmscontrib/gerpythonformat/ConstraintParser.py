#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2019 Tobias Lenz <t_lenz94@web.de>
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

import string

class TypesetValue(object):
    def __init__(self, val, typeset):
        self.val = val
        self.typeset = typeset

    def __eq__(self, rhs):
        if isinstance(rhs, TypesetValue):
            return self.val == rhs.val
        else:
            return False

    def __hash__(self):
        return self.val.__hash__()


GROUP_CHARACTER = "\""
ANNOTATION_BEGIN = "("
ANNOTATION_END = ")"
CONSTRAINT_BEGIN = "["
CONSTRAINT_END = "]"
SEPARATOR = ","
KEY_VALUE_SEP = ":"

SPECIAL_CHARACTERS = [GROUP_CHARACTER, ANNOTATION_BEGIN, ANNOTATION_END,
                      CONSTRAINT_BEGIN, CONSTRAINT_END, SEPARATOR,
                      KEY_VALUE_SEP]


class ConstraintParser(object):
    def __init__(self, data):
        self.data = data
        self.idx = 0

    def read_normal(self):
        """
        Read until something exciting happens
        """
        r = ""        
        while self.peek(skip_whitespace=True) not in SPECIAL_CHARACTERS and \
              not self.eof(skip_whitespace=True):
            r += self.next(skip_whitespace=(r == ""))
        return r

    def read_group(self):
        """
        Read a group (i.e. something delimited by ")
        """
        assert self.next(skip_whitespace=True) == GROUP_CHARACTER
        
        r = ""
        while self.peek(skip_whitespace=False) != GROUP_CHARACTER:
            r += self.next(skip_whitespace=False)
            assert not self.eof(skip_whitespace=False)
        
        assert self.next(skip_whitespace=False) == GROUP_CHARACTER
        
        return r

    def read_token(self):
        if self.peek(skip_whitespace=True) == GROUP_CHARACTER:
            return self.read_group()
        else:
            return self.read_normal()

    def read_annotation(self):
        assert self.next(skip_whitespace=True) == ANNOTATION_BEGIN
        r = self.read_token()        
        assert self.next(skip_whitespace=True) == ANNOTATION_END

        return r

    def read_single_entry(self):
        a = self.read_token()
        
        if self.peek(skip_whitespace=True) == ANNOTATION_BEGIN:
            b = self.read_annotation()
        else:
            b = None
            
        return TypesetValue(a, b)

    def read_variables(self):
        L = []
        
        while True:
            L.append(self.read_single_entry())

            if self.peek(skip_whitespace=True) == SEPARATOR:
                self.next(skip_whitespace=True)
            else:
                break

        if self.next(skip_whitespace=True) != KEY_VALUE_SEP:
            raise ValueError("malformed constraint string: you have to use '" +
                             KEY_VALUE_SEP + "' to separate variable names "
                             "from constraint bounds")

        return L

    def read_bounds(self):
        if self.peek(skip_whitespace=True) != CONSTRAINT_BEGIN:
            # Special syntax for constraints with lower == upper
            val = self.read_single_entry()
            return val, val

        assert self.next(skip_whitespace=True) == CONSTRAINT_BEGIN

        lower = None
        upper = None

        if self.peek(skip_whitespace=True) != SEPARATOR:
            lower = self.read_single_entry()
        
        if self.peek(skip_whitespace=True) == CONSTRAINT_END:
            upper = lower
        else:
            assert self.peek(skip_whitespace=True) == SEPARATOR
            self.next(skip_whitespace=True)
            
            if self.peek(skip_whitespace=True) != CONSTRAINT_END:
                upper = self.read_single_entry()

        if self.next(skip_whitespace=True) != CONSTRAINT_END:
            raise ValueError("malformed constraint string: constraint bounds "
                             "have to end with '" + CONSTRAINT_END + "'")

        return lower, upper

    def _peek_next(self):
        try:
            return self.data[self.idx]
        except IndexError:
            return '\0'

    def skip_whitespace(self):
        while self._peek_next() in string.whitespace:
            self.idx += 1    

    def next(self, skip_whitespace=False):
        if skip_whitespace:
            self.skip_whitespace()

        result = self._peek_next()
        self.idx += 1
        return result

    def peek(self, skip_whitespace=False):
        old_idx = self.idx
        result = self.next(skip_whitespace)
        self.idx = old_idx
        return result

    def eof(self, skip_whitespace=False):
        return self.peek(skip_whitespace) == "\0"


class Constraint(object):
    def __init__(self, variables, min, max):
        self.variables = variables
        self.min = min
        self.max = max

    def uncompress(self):
        return {v.val: (Constraint.eval(self.min),
                        Constraint.eval(self.max)) for v in self.variables}

    def merge(self, rhs):
        if rhs.min is not None:
            self.min = rhs.min

        if rhs.max is not None:
            self.max = rhs.max

        typesetting = {}
        for v in rhs.variables:
            if v.typeset is not None:
                typesetting[v.val] = v.typeset

        for v in self.variables:
            if v.val in typesetting:
                v.typeset = typesetting[v.val]

    def latex(self):
        s = "$"
        
        typeset_variable_list = list(v.typeset or v.val
                                     for v in self.variables)
        
        if self.max is not None and self.max == self.min:
            s += "=".join(typeset_variable_list)
            s += r"= {}".format(Constraint.pretty(self.min))

        elif self.max is None:
            s += ", ".join(typeset_variable_list)
            s += r"\ge {}".format(Constraint.pretty(self.min))
        else:
            if self.min is not None:
                s += r"{}\le ".format(Constraint.pretty(self.min))
            s += ", ".join(typeset_variable_list)
            s += r"\le {}".format(Constraint.pretty(self.max))
        s += "$"
        return s

    @staticmethod
    def pretty(v):
        if v.typeset is not None:
            return v.typeset
        else:
            return Constraint.prettify(v.val)

    @staticmethod
    def prettify(s):
        """
        Try to apply digit grouping to numbers for TeX display

        This is of course not perfect, for example one can trick it using
        something like 1{}000
        """
        l = []
        curr_token = ""
        num_mode = False

        for c in s:
            if (c in string.digits) != num_mode:
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
    def eval(x):
        if x is None:
            return None

        s = x.val

        coding = {"^": "**",
                  "{": "(",
                  "}": ")",
                  "\\cdot": "*"}

        for old, new in iter(coding.items()):
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

    @classmethod
    def parse(cls, s, silent):
        parser = ConstraintParser(s)

        res = []
        while True:
            if parser.eof(skip_whitespace=True):
                raise ValueError("malformed constraint string: unexpected eof"
                                 "\nprobably this means that your constraint "
                                 "string is either empty or ends with ','")

            res.append(Constraint(parser.read_variables(),
                                  *parser.read_bounds()))

            if parser.eof(skip_whitespace=True):
                break

            if parser.next(skip_whitespace=True) != SEPARATOR:
                raise ValueError("legacy syntax in constraint string: "
                                 "you need to separate your constraints by '" +
                                 SEPARATOR + "'")

        return ConstraintList(res, silent)


#For two constraining intervals, return their intersection, where there
#shall be no boundary that is explicitly specified less strict in the second
#than in the first (e.g., (_,100) in the first and (_,1000) in the second).
def merge(c1, c2, var):
    if c1[0] == None:
        a = c2[0]
    elif c2[0] == None:
        a = c1[0]
    elif c1[0] > c2[0]:
        raise ValueError("Constraint ("+var+">" + str(c2[0]) + ") of subscope "
                         "mustn't be less constraining than of superscope "
                         + "("+var+">" + str(c1[0]) + ").")
    else:
        a = c2[0]

    if c1[1] == None:
        b = c2[1]
    elif c2[1] == None:
        b = c1[1]
    elif c1[1] < c2[1]:
        raise ValueError("Constraint ("+var+"<" + str(c2[1]) + ") of subscope "
                         "mustn't be less constraining than of superscope "
                         + "("+var+"<" + str(c1[1]) + ").")
    else:
        b = c2[1]

    return (a, b)

#For two unpacked constraint lists, return their logical and, where there
#shall be no inequality that is explicitly specified less strict in the second
#than in the first (e.g., (_,100) in the first and (_,1000) in the second).
def merge_constraints(cl1, cl2):
    res = dict(cl1)
    for var, ran in iter(cl2.items()):
        if var in res:
            res[var] = merge(res[var], ran, var)
        else:
            res[var] = ran
    return res

