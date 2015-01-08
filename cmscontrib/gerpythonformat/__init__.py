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

from __future__ import print_function
from __future__ import unicode_literals

import filecmp
import os
import shutil


def copyifnecessary(source, destination):
    """Copy source to destination if the file contents are different.

    source (string): source file name

    destination (string): destination file name

    """
    necessary = True
    if os.path.exists(destination):
        necessary = not filecmp.cmp(source, destination)
    if necessary:
        shutil.copyfile(source, destination)


def copyrecursivelyifnecessary(source, destination, ignore=set()):
    """Copy the directory or file source to destination recursively.
    Files are only touched if their contents differ.

    source (string): source file/directory name

    destination (string): destination file/directory name

    """
    if source in ignore:
        return
    if os.path.isfile(source):
        copyifnecessary(source, destination)
    elif os.path.isdir(source):
        if not os.path.isdir(destination):
            os.mkdir(destination)
        names = os.listdir(source)
        for name in names:
            copyrecursivelyifnecessary(os.path.join(source, name),
                                       os.path.join(destination, name),
                                       ignore)
    else:
        raise Exception("Node {} cannot be copied (wrong type)".format(source))
