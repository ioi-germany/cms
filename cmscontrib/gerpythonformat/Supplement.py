#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013 Tobias Lenz <t_lenz94@web.de>
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


def easycall(f):
    """If f is callable, call it and return the result. Otherwise, return f.
    """
    try:
        f.__call__
    except:
        return f
    return f()


def escape_latex(x):
    """Return a function returning the result of x escaped for latex.
    """
    # TODO Do something...
    def f():
        return str(easycall(x))
    return f


def def_latex(name, x):
    """Return a function returning a latex command defining \name to be
    the result of x.
    """
    def f():
        return r"\def\%s{%s}" % (name, easycall(x)) + "\n"
    return f


def input_latex(x):
    """Return a function returning a latex statement \input{result of x}
    to load the file whose path is returned by x.
    """
    def f():
        return r"\input{%s}" % easycall(x)
    return f


__all__ = ["escape_latex", "def_latex", "input_latex"]
