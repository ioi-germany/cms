#!/usr/bin/env python3

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
    """Return a function returning a latex statement \\input{result of x}
    to load the file whose path is returned by x.
    """
    def f():
        return r"\input{%s}" % easycall(x)
    return f


def escape_asy(x):
    """Return a function returning the result of f escaped for asymptote.
    """
    def f():
        return str(easycall(x)).replace("\\", "\\\\").replace("\n", "\\n")
    return f


def def_asy(name, x):
    """Return a function returning an asymptote command defining name to be
    the result of f (where the result of f is a string).
    """
    # TODO automatically guess type of variable
    def f():
        return 'string %s = "%s";\n' % (name, easycall(x))
    return f


def escape_typst(x):
    """Return a function returning the result of x, escaped so that it can
    be embedded in a double-quoted typst string literal.
    """
    def f():
        return str(easycall(x)).replace("\\", "\\\\").replace('"', '\\"')
    return f


def def_typst(name, x):
    """Return a function returning a typst statement defining `name` to be
    the string which is the result of x.
    """
    def f():
        return '#let %s = "%s"\n' % (name, easycall(escape_typst(x)))
    return f


def typst_strings(xs):
    """Return a function returning a typst array of the strings returned
    by the given (easily callable) items.
    """
    def f():
        # Trailing comma: without it, a single element would be parsed as
        # grouping parentheses instead of an array.
        return "(" + "".join('"{}",'
                             .format(easycall(escape_typst(x)))
                             for x in xs) + ")"
    return f


def typst_raw_strings(xs):
    """Return a function returning a typst array of raw blocks containing
    the contents given by the items.
    Suitable for verbatim content such as testcase files.
    """
    import re

    def raw_block(content):
        run = max((len(m.group(0)) for m in re.finditer(r"`+", content)),
                  default=0)
        delim = "`" * max(3, run + 1)
        if not content.endswith("\n"):
            content += "\n"
        return "{}\n{}{}".format(delim, content, delim)

    def f():
        # Trailing comma (see above): keep single samples arrays.
        return "(" + "".join(raw_block(easycall(x)) + "," for x in xs) + ")"
    return f


__all__ = ["escape_latex", "def_latex", "input_latex", "escape_asy",
           "def_asy", "escape_typst", "def_typst", "typst_strings",
           "typst_raw_strings"]
