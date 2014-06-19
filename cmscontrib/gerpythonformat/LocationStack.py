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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os


class WorkingDirectory:
    """Class responsible for maintaining a stack of working directories.
    """
    def __init__(self, path):
        """Change the working directory to path.
        """
        self.previous = os.getcwd()
        os.chdir(path)

    def __enter__(self):
        return self

    def finish(self):
        """Reset the working directory.
        """
        os.chdir(self.previous)

    def __exit__(self, type, value, traceback):
        self.finish()


def chdir(path):
    """Normal use case:

    with chdir(path):  # sets the working directory to path
        do something
    # the working directory is automatically reset to its previous value, here
    do something else

    """
    return WorkingDirectory(path)
