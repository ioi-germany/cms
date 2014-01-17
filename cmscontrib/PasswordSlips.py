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

"""To create a PDF document containing password slips.

"""

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()

import argparse
import logging
import os
import shutil
import subprocess
import tempfile
from tornado import template

from cms import config
from cms.db import SessionGen, Contest, ask_for_contest
from cms.io.GeventUtils import rmtree


logger = logging.getLogger(__name__)


class PasswordSlips(object):
    def __init__(self, contest_id, output_file):
        self.contest_id = contest_id
        self.output_file = output_file

    def make(self):
        with SessionGen() as session:
            contest = Contest.get_from_id(self.contest_id, session)

            template_dir = os.path.join(os.path.dirname(__file__), "templates")
            template_loader = template.Loader(template_dir, autoescape=None)

            directory = tempfile.mkdtemp(dir=config.temp_dir)
            logger.info("Using temporary directory {}".format(directory))

            tex = os.path.join(directory, "password_slips.tex")
            pdf = os.path.join(directory, "password_slips.pdf")
            with open(tex, "w") as f:
                f.write(template_loader.load("password_slips.tex")
                        .generate(users=sorted(contest.users,
                                               key=lambda u: u.username)))
            cmd = ["pdflatex",
                   "-interaction",
                   "nonstopmode",
                   tex]
            subprocess.check_call(cmd, cwd=directory)
            shutil.move(pdf, self.output_file)
            rmtree(directory)


def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(description="Password slip creator.")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of contest")
    parser.add_argument("output_file",
                        help="pdf file to save password slips to")

    args = parser.parse_args()

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    PasswordSlips(contest_id=args.contest_id,
                  output_file=args.output_file).make()


if __name__ == "__main__":
    main()
