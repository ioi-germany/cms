# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2022 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2015 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2022 Manuel Gundlach <manuel.gundlach@gmail.com>
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
from __future__ import division

#import codecs
from functools import wraps
import os
import sys


# sys.stdout = codecs.getwriter("utf8")(sys.stdout)
# sys.stderr = codecs.getwriter("utf8")(sys.stderr)


def get_terminal_line_length():
    try:
        return int(os.popen('stty size', 'r').read().split()[1])
    except:
        return 1000000000


line_length = min(get_terminal_line_length(), 140)


# Coloring output to stdout:
# Currently only linux is supported
highlight_code = "\033[38;5;6m"
purple_code = "\033[01;35m"
red_code = "\033[91m"
green_code = "\033[92m"
lightgreen_code = "\033[38;5;155m"
orange_code = "\033[38;5;208m"
yellow_code = "\033[93m"
gray_code = "\033[90m" # no pun intended
blue_code = "\033[94m"
bold_code = "\033[1m"
invert_code = "\033[7m"
purple_code = "\033[38;5;165m"
end_code = "\033[0m"

_disable_color_switch = False


def disable_colors():
    global _disable_color_switch
    _disable_color_switch = True


def colors_enabled():
    return not _disable_color_switch and (sys.platform == "linux"
                                          or sys.platform == "linux2")


def color_function(start):
    def f(string):
        if not colors_enabled():
            return string
        r = ""
        # Split the string to make nested formatting commands behave as
        # expected.
        for t in (str(string)).split(end_code):
            r += start + t + end_code
        return r
    return f


highlight = color_function(highlight_code)
purple = color_function(purple_code)
red = color_function(red_code)
green = color_function(green_code)
lightgreen = color_function(lightgreen_code)
orange = color_function(orange_code)
yellow = color_function(yellow_code)
gray = color_function(gray_code)
blue = color_function(blue_code)
bold = color_function(bold_code)
invert = color_function(invert_code)
purple = color_function(purple_code)

def ellipsis_symbol():
    return bold(highlight("⤷")) + " "


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


def remaining_line_length():
    return line_length - IndentManager.indent * 2


def generic_split(s, first=0, max_len=-1):
    """Estimate the length of a string when displayed in a terminal.
    The basic ANSI formatting commands are skipped (but for example \n and \t
    are counted as one character).

    s (unicode): the string

    return (int): its length

    """
    r = 0
    t = []
    skip = False

    for i in range(first, len(s)):
        c = s[i]
        t.append(c)

        if c == '\033':
            skip = True

        if not skip:
            r += 1

        if c == 'm' or c == 'K':
            skip = False

        if r > max_len >= 0:
            t = t[:-1]
            break

    return "".join(t), r

def estimate_len(*args, **kwargs):
    return generic_split(*args, **kwargs)[1]

def split(*args, **kwargs):
    return generic_split(*args, **kwargs)[0]

def color_codes(s):
    """ Return all color codes in s
    """
    r = []
    reading = False
    curr = ""

    for c in s:
        if c == '\033':
            reading = True

        if reading:
            curr += c

        if c == 'm':
            reading = False
            r.append(curr)
            curr = ""

        if c == 'K':
            reading = False
            curr = ""

    return r

def apply_to_lines(func):
    """Returns a function that applies func to each line of the first input
    parameter.
    """
    @wraps(func)
    def f(string, *args, **kwargs):
        res = [func(l, *args, **kwargs) for l in string.split("\n")]
        return "\n".join(res)
    return f


@apply_to_lines
def pad_center(string, length, filler=' '):
    """In each line, adds the filler on both ends to make the string of the
    specified length.
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
    return filler * (r // 2) + string + filler * ((r + 1) // 2)


@apply_to_lines
def pad_left(string, length, filler=' '):
    """In each line, adds the filler on the left to make the string of the
    specified length.
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
    return filler * r + string


@apply_to_lines
def pad_right(string, length, filler=' '):
    """In each line, adds the filler on the right to make the string of the
    specified length.
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
    return string + filler * r


@apply_to_lines
def add_left(string, filler=' '):
    """In each line, adds the filler on the left.

    string (unicode): the string to modify
    filler (unicode): the string to add

    return (unicode): the modified string

    """
    return filler + string


@apply_to_lines
def add_right(string, filler=' '):
    """In each line, adds the filler on the right.

    string (unicode): the string to modify
    filler (unicode): the string to add

    return (unicode): the modified string

    """
    return string + filler


@apply_to_lines
def indent(string, filler=' '):
    """Indent each line of the string according to the current indentation
    level.

    string (unicode): the string to indent
    filler (unicode): the character to fill the space with

    return (unicode): the indented string

    """
    return filler * (IndentManager.indent * 2) + string


def center_line(l, filler=' ', outer_left=None,
                outer_right=None, make_bold=False):
    if outer_left is None:
        outer_left = filler
    if outer_right is None:
        outer_right = outer_left

    r = line_length - estimate_len(outer_left) - estimate_len(outer_right)
    s = outer_left + pad_center(l, r, filler) + outer_right

    if make_bold:
        s = bold(s)

    print(s)


def box(title, content, double=False):
    """Prints a box with title on the top border and content in the interior.
    +------title-------+
    |     content      |
    +------------------+

    title (unicode):
    content (unicode):
    double (boolean):

    """
    if double:
        center_line(title, '═', '╔', '╗', True)
        for s in content.split('\n'):
            center_line(s, ' ', '║', None, True)
        center_line("", '═', '╚', '╝', True)
    else:
        center_line(title, '─', '╭', '╮', True)
        for s in content.split('\n'):
            center_line(s, ' ', '│', None, True)
        center_line("", '─', '╰', '╯', True)


def side_by_side(strings, offsets):
    """Puts the lines of the given strings in a table-like layout.

    For example,
    side_by_side(["Column 1", "Column 2\nwith line\nbreaks","Column 3"],
                 [0,12,24]))
    returns:
    Column 1    Column 2    Column 3
                with line
                breaks

    strings ([unicode]): the columns of the table
    offsets ([int]): the positions of the left edges of the columns

    return (unicode): the table

    """
    lines = [s.split("\n") for s in strings]
    num_lines = max([x for x in map(len, lines)])
    res = []
    for iline in range(num_lines):
        line = ""
        for istring, o in zip(range(len(strings)), offsets):
            if len(line) > 0:
                line += " "
            line += " " * max(o - estimate_len(line), 0)
            if iline < len(lines[istring]):
                line += lines[istring][iline]
        res.append(line)
    return "\n".join(res)


def add_line_breaks(l, length, hanging_indent=0, use_ellipsis=True):
    """Add appropriate line breaks to a string.

    l (unicode): the input string (may already consist of multiple lines)
    length (int): the maximum allowed line length
    hanging_indent (int): how much to indent all lines after the first one

    return (unicode): the string with appropriate line breaks

    """
    result = []

    class data:  # workaround to be able to assign to variables in flush_line()
        indent = 0
        rem_width = length
        curr_line = ""
        pre = ""
        color_code = ""
        old_color_code = ""

    next_indent = hanging_indent

    # We officially give up
    if length - next_indent <= 10:
        return l

    def flush_line(ellipsis=use_ellipsis):
        result.append(" " * data.indent + data.pre + data.old_color_code +
                      data.curr_line.rstrip() + (end_code if colors_enabled()
                                                          else ""))
        # print("##" + result[-1].replace("\033", "\\033") + "##")
        data.old_color_code = data.color_code
        data.indent = next_indent
        data.pre = ellipsis_symbol() if ellipsis else ""
        data.rem_width = length - data.indent - estimate_len(data.pre)
        data.curr_line = ""

    def put_word(s):
        data.curr_line += s

        for code in color_codes(s):
            if code == end_code:
                data.color_code = ""
            else:
                data.color_code += code

    def add_word(s):
        cursor = 0

        while cursor < len(s):
            l = estimate_len(s, first=cursor, max_len=length + 10)

            if l <= data.rem_width:
                put_word(s[cursor:])
                data.rem_width -= l
                break

            # Also too long for the next line?
            elif l > length - next_indent - estimate_len(data.pre):
                t = split(s, first=cursor, max_len=data.rem_width)
                put_word(t)
                cursor += len(t)

            flush_line()

    def add_whitespace(s):
        l = estimate_len(s)
        if l <= data.rem_width:
            data.curr_line += s
            data.rem_width -= l
        else:
            flush_line()

    def add_newline(s):
        flush_line(ellipsis=False)

    def classify(c):
        if c == " ":
            return add_whitespace
        elif c == "\n":
            return add_newline
        else:
            return add_word

    def splittable(c):
        return c == '/' or c == '-'

    part = []
    for c in l:
        if len(part) > 0 and (c == "\n" or splittable(c) or
                              classify(part[0]) != classify(c)):
            classify(part[0])("".join(part))
            part = []
        part.append(c)
    if len(part) > 0:
        classify(part[0])("".join(part))
    if len(data.curr_line) > 0:
        flush_line(ellipsis=False)

    return "\n".join(result)


def print_msg(message, headerdepth=None,
              error=False, warning=False, success=False,
              hanging_indent=0, fill_character=' ', use_ellipsis=True):
    """
    If headerdepth==1, all parameters following will be ignored
    """
    if estimate_len(message) == 0:
        return
    symbols = {2: "▰", 3: "═", 4: "─"}

    if headerdepth == 1:
        box('', message, True)
        return

    left = ""
    if headerdepth in symbols:
        s = symbols[headerdepth]
        left = s * 3 + " "
        fill_character = s
    rem_length = remaining_line_length() - estimate_len(left)

    res = add_line_breaks(message, rem_length - 1, hanging_indent, use_ellipsis)
    res = add_right(res, " ")
    res = pad_right(res, rem_length, fill_character)
    res = add_left(res, left)

    res = indent(res)

    if headerdepth is not None:
        res = bold(res)
    if error:
        res = red(res)
    if warning:
        res = yellow(res)
    if success:
        res = green(res)

    print(res)


def print_block(msg):
    print_msg(msg)


def header(message, depth):
    print_msg(message, depth)
    return IndentManager()

def highlight_latex(s, verbose=False):
    """Highlights and shortens LaTeX output.

    TODO There are some off (or missing) newlines in the pruned output.
    """

    to_words = lambda s: [x.strip(":,.;-= ") for x in s.split()]

    if "Errors" in to_words(s):
        verbose = True

    # We silence warnings that contain one of these phrases.
    # Some come from packages and we can't do anything about them,
    # while some may mean we should adjust our header file.
    silenced_warnings = [
        "Class scrartcl Warning: Usage of package `fancyhdr' together "
        "with a KOMA-Script class is not recommended.",
        "LaTeX hooks Warning: Generic hook  is deprecated. "
        "Use hook  instead.",
        "Package fontspec Warning: OpenType feature 'Numbers=Uppercase'  not "
        "available for font 'FiraMathRegular' with script "
        "'Math' and language 'Default'."
        ]
    silenced_warnings = [to_words(phrase) for phrase in silenced_warnings]
    def silenced(w):
        for phrase in silenced_warnings:
            i = 0
            for a in w:
                if phrase[i] == a:
                    i += 1
                if i == len(phrase):
                    return True
        return False

    r = []

    normal = lambda f: f
    warning = yellow

    mode = normal
    # TODO Do we want to remove the loading-files parts of the log?
    # A first attempt at this is implemented below, but commented out.
    loading_segment = False
    #open_brackets = 0

    current_warning = None
    previous_warnings = set()
    after_warning = False

    highlight_error = lambda s: bold(red(s))

    for l in s.split("\n"):
        if mode == green or mode == purple:
            mode = normal

        simplified = l.strip()

        if simplified == "":
            if mode == warning:
                after_warning = True
            else:
                mode = normal
        # We assume the log doesn't end with a warning
        # (if it did, this point wouldn't be reached and
        # the warning not printed.)
        elif after_warning:
            after_warning = False
            current_warning_simplified = current_warning.strip()
            if current_warning_simplified not in previous_warnings and \
                not silenced(to_words(current_warning_simplified)):
                r.append(mode(
                    current_warning.replace("Warning",bold(invert("Warning")))
                    ))
                previous_warnings.add(current_warning_simplified)
            current_warning = None
            mode = normal

        if simplified.startswith("Output written") or \
           simplified.startswith("Transcript written"):
            mode = green
            previous_warnings = set()

        if simplified.startswith("! "):
            mode = highlight_error

        words = to_words(simplified)

        if "Overfull" in words or "Underfull" in words:
            mode = purple

        if "Warning" in words:
            mode = warning

        if "Error" in words or "Errors" in words:
            mode = highlight_error

        #if mode == normal:
            #if simplified.startswith("(./") or simplified.startswith("(/"):
                #loading_segment = True

        if mode == warning:
            current_warning = '\n'.join([current_warning, l])\
                                if current_warning else l
        elif not ( (mode == normal and loading_segment) or
                   (mode == normal and not verbose) ):
            r.append(mode(l))

        #if mode == normal and loading_segment:
            #open_brackets += simplified.count('(') - simplified.count(')')
            #if open_brackets == 0:
                #loading_segment = False

    return "\n".join(r)
