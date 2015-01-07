#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2014 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2015 Fabian Gundlach <320pointsguy@gmail.com>
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

import os
from sys import platform


def get_terminal_line_length():
    try:
        return int(os.popen('stty size', 'r').read().split()[1])
    except:
        return 1000000000


line_length = min(get_terminal_line_length(), 140)


class MyColors:
    """ Class for coloring output to stdout
    Currently only linux is supported
    """
    red_code = "\033[91m"
    green_code = "\033[92m"
    yellow_code = "\033[93m"
    blue_code = "\033[94m"
    bold_code = "\033[1m"
    end_code = "\033[0m"

    @classmethod
    def colors_enabled(cls):
        return platform == "linux" or platform == "linux2"

    @classmethod
    def _red(cls, s):
        if cls.colors_enabled():
            return cls.red_code + s + cls.end_code
        else:
            return s

    @classmethod
    def red(cls, s):
        r = ""
        for t in s.split(cls.end_code):
            r += cls._red(t)
        return r

    @classmethod
    def _green(cls, s):
        if cls.colors_enabled():
            return cls.green_code + s + cls.end_code
        else:
            return s

    @classmethod
    def green(cls, s):
        r = ""
        for t in s.split(cls.end_code):
            r += cls._green(t)
        return r

    @classmethod
    def _yellow(cls, s):
        if cls.colors_enabled():
            return cls.yellow_code + s + cls.end_code
        else:
            return s

    @classmethod
    def yellow(cls, s):
        r = ""
        for t in s.split(cls.end_code):
            r += cls._yellow(t)
        return r

    @classmethod
    def _blue(cls, s):
        if cls.colors_enabled():
            return cls.blue_code + s + cls.end_code
        else:
            return s

    @classmethod
    def blue(cls, s):
        r = ""
        for t in s.split(cls.end_code):
            r += cls._blue(t)
        return r

    @classmethod
    def _bold(cls, s):
        if cls.colors_enabled():
            return cls.bold_code + s + cls.end_code
        else:
            return s

    @classmethod
    def bold(cls, s):
        r = ""
        for t in s.split(cls.end_code):
            r += cls._bold(t)
        return r

    @classmethod
    def ellipsis(cls):
        return cls.blue(cls.bold("..."))


class IndentManager(object):
    indent = 0

    def start(self):
        IndentManager.indent += 1

    def stop(self):
        IndentManager.indent -= 1

    def __enter__(self):
        self.start()

    def __exit__(self, type, value, traceback):
        self.stop()


def estimate_len(s):
    """Get a better estimate on the length of s
    This functions skips the basic formatting commands,
    but it does not respect Unicode commands
    """
    r = 0
    skip = False

    for c in s:
        if c == '\033':
            skip = True

        if not skip:
            r += 1

        if c == 'm':
            skip = False

    return r


def center_line(l, filler=' ', outer=None, bold=False):
    if outer is None:
        outer = filler

    x = estimate_len(l)
    r = line_length - 2 - x
    s = outer + filler * (r / 2) + l + \
        filler * ((r + 1) / 2) + outer

    if bold:
        s = MyColors.bold(s)

    print s


def box(h, l):
    center_line(h, '-', '+', True)
    center_line(l, ' ', '|', True)
    center_line("", "-", '+', True)


def print_msg_line(l, headerdepth, error, warning,
                   success, hanging_indent,
                   fill_character, extra_width):
    indent = IndentManager.indent * 2
    rem_width = line_length - 5 - indent
    curr_line = " " * indent

    data = {"indent": indent, "rem_width": rem_width,
            "curr_line": curr_line,
            "hanging_indent": hanging_indent,
            "result": [],
            "empty_line": True}

    # We officially give up
    if rem_width <= 10:
        print l
        return

    def flush_line():
        data["result"].append(data["curr_line"])
        data["empty_line"] = True
        data["indent"] += data["hanging_indent"]
        data["hanging_indent"] = 0
        data["rem_width"] = line_length - 5 - data["indent"]
        data["curr_line"] = " " * data["indent"]

    # TODO: This currently ignores '\t' and exotic whitespaces
    L = l.split(" ")

    i = 0
    while i < len(L):
        data["empty_line"] = False
        w = L[i]

        # Too long for the next line?
        if estimate_len(w) > line_length - 5 - data["indent"] - \
           data["hanging_indent"]:
            v = w[:data["rem_width"]]
            data["curr_line"] += v

            flush_line()
            w = w[data["rem_width"]:]
            L[i] = w

            continue

        if estimate_len(w) > data["rem_width"]:
            flush_line()

        data["curr_line"] += w

        if estimate_len(w) < data["rem_width"]:
            data["curr_line"] += " "

        data["rem_width"] -= estimate_len(w) + 1

        if data["rem_width"] <= 0:
            flush_line()

        i += 1

    # Output last line
    if data["empty_line"]:
        data["rem_width"] = 0
    else:
        data["result"].append(data["curr_line"])

    data["rem_width"] += extra_width

    if data["rem_width"] >= 1:
        if data["result"][-1][-1] != ' ':
            data["result"][-1] += " "
            data["rem_width"] -= 1

        data["result"][-1] += fill_character * data["rem_width"]

    for line in data["result"]:
        if headerdepth is not None:
            line = MyColors.bold(line)
        if error:
            line = MyColors.red(line)
        if warning:
            line = MyColors.yellow(line)
        if success:
            line = MyColors.green(line)

        print line


def print_msg_base(message, headerdepth, error,
                   warning, success, hanging_indent,
                   fill_character, extra_width):
    message = message.strip()

    if len(message) > 0:
        for l in message.split("\n"):
            print_msg_line(l, headerdepth, error,
                           warning, success,
                           hanging_indent, fill_character,
                           extra_width)


def print_msg(message, headerdepth=None,
              error=False, warning=False, success=False,
              hanging_indent=0, fill_character=' '):
    symbols = {1: "#", 2: "#", 3: "=", 4: "-"}

    if headerdepth in symbols:
        s = symbols[headerdepth]
        message = s * 3 + " " + message
        hanging_indent = 4
        fill_character = s

    wrapper = "#" * line_length

    if headerdepth is not None:
        wrapper = MyColors.bold(wrapper)
    if error:
        wrapper = MyColors.red(wrapper)
    if warning:
        wrapper = MyColors.yellow(wrapper)
    if success:
        wrapper = MyColors.green(wrapper)

    if headerdepth == 1:
        print wrapper

    print_msg_base(message, headerdepth, error, warning,
                   success, hanging_indent, fill_character,
                   extra_width=5 if headerdepth is not None
                   else 0)

    if headerdepth == 1:
        print wrapper


def print_block(msg):
    print_msg(msg)


def header(message, depth):
    print_msg(message, depth)
    return IndentManager()
