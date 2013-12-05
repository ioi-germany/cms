#!/usr/bin/env python2
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

from sys import platform


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
    def red(cls, s):
        if cls.colors_enabled():
            return cls.red_code + s + cls.end_code
        else:
            return s

    @classmethod
    def green(cls, s):
        if cls.colors_enabled():
            return cls.green_code + s + cls.end_code
        else:
            return s

    @classmethod
    def yellow(cls, s):
        if cls.colors_enabled():
            return cls.yellow_code + s + cls.end_code
        else:
            return s

    @classmethod
    def blue(cls, s):
        if cls.colors_enabled():
            return cls.blue_code + s + cls.end_code
        else:
            return s

    @classmethod
    def bold(cls, s):
        if cls.colors_enabled():
            return cls.bold_code + s + cls.end_code
        else:
            return s

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


def print_msg(message, headerdepth=None,
              error=False, warning=False, success=False):
    symbols = {1: "#", 2: "#", 3: "=", 4: "-"}
    if headerdepth in symbols:
        s = symbols[headerdepth]
        rl = max(0, 75-len(message)-IndentManager.indent*2)
        message = s*3 + " " + message + " " + s*rl
    message = " "*(IndentManager.indent*2) + message
    if headerdepth == 1:
        message = "#"*80 + "\n" + message + "\n" + "#"*80
    if headerdepth is not None:
        message = MyColors.bold(message)
    if error:
        message = MyColors.red(message)
    if warning:
        message = MyColors.yellow(message)
    if success:
        message = MyColors.green(message)
    print message


def print_block(message):
    message = message.strip()
    if len(message) > 0:
        for l in message.split("\n"):
            print " "*(IndentManager.indent*2) + l


def header(message, depth):
    print_msg(message, depth)
    return IndentManager()
