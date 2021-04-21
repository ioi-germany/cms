#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2021 Manuel Gundlach <manuel.gundlach@gmail.com>
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

"""Captchas for CWS.

"""

import logging
import os
from pkg_resources import resource_filename

import cairosvg
from random import randint, uniform


logger = logging.getLogger(__name__)


class Captcha():
    """A class for providing random captchas.

    """

    split = "/>"

    def __init__(self):
        static_path = resource_filename("cms.server", "captcha/static")
        with open(os.path.join(static_path, "frame.svg" ), 'r') as framefile:
                self.frame  = framefile.read() .split("<!--Anchor-->")
        with open(os.path.join(static_path, "digits.svg"), 'r') as digitsfile:
                self.digits = digitsfile.read().split(self.split)[:-1]
        with open(os.path.join(static_path, "line.svg"  ), 'r') as linefile:
                self.line   = linefile.read()  .split(self.split)[0]

    def captcha(self):
        """Returns a random string of 6 digits (0-9) and an
        associated captcha image (png) in the form of a bytestring.

        """
        riddle_len = 6
        h_off = 7
        v_off = 10

        def h_uniform(r):
                return h_off+uniform(-r,+r)

        def v_uniform(r):
                return v_off+uniform(-r,+r)

        def warp(i):
                return "transform=\""+\
                                "translate("+ str(4*i+h_uniform(1)) + "," + str(v_uniform(1)) + ") " +\
                                "skewX(" + str(uniform(-30,30)) + ") " +\
                                "skewY(" + str(uniform(-30,30)) + ")\""

        riddle = [ randint(0,9) for i in range(riddle_len) ]

        svg_rand_digits = [ self.digits[riddle[i]] + warp(i) + self.split for i in range(riddle_len) ]
        svg_rand_line = self.line + "d=\"M 3," + str(v_uniform(3)) + " C 13," + str(v_uniform(6)) + " 22," + str(v_uniform(6)) + " 32," + str(v_uniform(3)) + "\"" + self.split
        svg = self.frame[0] + ''.join(svg_rand_digits) + svg_rand_line + self.frame[1]

        svg_bs = svg.encode('utf-8')
        output_bs = cairosvg.svg2png(bytestring=svg_bs)

        return (riddle,output_bs)
