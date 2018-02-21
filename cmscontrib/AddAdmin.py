#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2018 Tobias Lenz <t_lenz94@web.de>
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

"""This script creates a new admin in the database.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()

import argparse
import logging
import sys

from cms import utf8_decoder
from cms.db import Admin, SessionGen
from cmscommon.crypto import generate_random_password, hash_password

from sqlalchemy.exc import IntegrityError


logger = logging.getLogger(__name__)


def add_admin(username, password=None, real_name=None):
    logger.info("Creating the admin on the database.")
    if password is None:
        password = generate_random_password()
    admin = Admin(username=username,
                  authentication=hash_password(password.encode("utf-8")),
                  name=real_name or username,
                  permission_all=True)
    try:
        with SessionGen() as session:
            session.add(admin)
            session.commit()
    except IntegrityError:
        logger.error("An admin with the given username already exists.")
        return False

    logger.info("Admin '%s' with complete access added. ", username)
    return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(description="Add an admin to CMS.")
    parser.add_argument("username", action="store", type=utf8_decoder,
                        nargs=1)
    parser.add_argument("-p", "--password", action="store", type=utf8_decoder)

    args = parser.parse_args()

    success = add_admin(args.username[0], args.password)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
