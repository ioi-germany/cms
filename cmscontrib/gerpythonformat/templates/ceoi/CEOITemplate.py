#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2023 Tobias Lenz <t_lenz94@web.de>
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


from cmscontrib.gerpythonformat.templates.boi.BOITemplate \
    import BOITemplate

import os


# This is the template for CEOI 2023 (identical with BOI template)
class CEOITemplate(BOITemplate):
    def __init__(self, contest, short_name, year):
        super(CEOITemplate, self).__init__(contest, short_name, year,
                                           "header", "png",
                                           os.path.dirname(__file__))