#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
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


def escape_tex_normal(string):
    """Escape a string for use inside latex.

    string (unicode): string to escape
    returns (unicode): escaped string

    """
    rep = {"&": r"\&",
           "%": r"\%",
           "$": r"\$",
           "#": r"\#",
           "_": r"\_",
           "{": r"\{",
           "}": r"\}",
           "~": r"\textasciitilde",
           "^": r"\textasciicircum",
           "\\": r"\textbackslash"}
    res = ""
    for c in string:
        if c in rep:
            res += rep[c]
        else:
            res += c
    return res


def escape_tex_tt(string):
    """Escape a string for use inside latex with \texttt.

    string (unicode): string to escape
    returns (unicode): escaped string

    """
    rep = set("&%$#_{}~^\\")
    res = ""
    for c in string:
        if c in rep:
            res += "\\char\"%02X" % ord(c)
        else:
            res += c
    return res
