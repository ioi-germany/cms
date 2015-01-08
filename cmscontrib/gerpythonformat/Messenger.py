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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os
from sys import platform


def get_terminal_line_length():
    try:
        return int(os.popen('stty size', 'r').read().split()[1])
    except:
        return 1000000000


line_length = min(get_terminal_line_length(), 140)


# Coloring output to stdout:
# Currently only linux is supported

red_code = "\033[91m"
green_code = "\033[92m"
yellow_code = "\033[93m"
blue_code = "\033[94m"
bold_code = "\033[1m"
end_code = "\033[0m"


def colors_enabled():
    return platform == "linux" or platform == "linux2"


def color_function(start):
    def f(string):
        if not colors_enabled():
            return string
        r = ""
        # Split the string to make nested formatting commands behave as
        # expected.
        for t in string.split(end_code):
            r += start + t + end_code
        return r
    return f


red = color_function(red_code)
green = color_function(green_code)
yellow = color_function(yellow_code)
blue = color_function(blue_code)
bold = color_function(bold_code)


def ellipsis():
    return blue(bold("..."))


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
    """Estimate the length of a string when displayed in a terminal.
    The basic ANSI formatting commands are skipped (but for example \n and \t
    are counted as one character).

    s (unicode): the string

    return (int): its length

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


def pad_center(string, length, filler=' '):
    """Adds the filler on both ends to make the string of the specified length.
    If the string is already longer than the specified length, it is returned
    unchanged.

    string (unicode): the string to pad
    length (int): the length the string is supposed to have
    filler (unicode): the character to fill the space with

    return (unicode): the padded string

    """
    r = length - estimate_len(string)
    if r < 0:
        return string
    return filler*(r/2) + string + filler*((r+1)/2)


def center_line(l, filler=' ', outer=None, make_bold=False):
    if outer is None:
        outer = filler

    r = line_length - 2*estimate_len(outer)
    s = outer + pad_center(l, r, filler) + outer

    if make_bold:
        s = bold(s)

    print(s)


def box(title, content):
    """Prints a box with title on the top border and content in the interior.
    +------title-------+
    |     content      |
    +------------------+

    title (unicode):
    content (unicode):

    """
    center_line(title, '-', '+', True)
    center_line(content, ' ', '|', True)
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
        print(l)
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
            line = bold(line)
        if error:
            line = red(line)
        if warning:
            line = yellow(line)
        if success:
            line = green(line)

        print(line)


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
        wrapper = bold(wrapper)
    if error:
        wrapper = red(wrapper)
    if warning:
        wrapper = yellow(wrapper)
    if success:
        wrapper = green(wrapper)

    if headerdepth == 1:
        print(wrapper)

    print_msg_base(message, headerdepth, error, warning,
                   success, hanging_indent, fill_character,
                   extra_width=5 if headerdepth is not None
                   else 0)

    if headerdepth == 1:
        print(wrapper)


def print_block(msg):
    print_msg(msg)


def header(message, depth):
    print_msg(message, depth)
    return IndentManager()
