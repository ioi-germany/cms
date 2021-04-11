#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""This script creates a new participation for every user in the database.

"""

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()  # noqa

import argparse
import logging
import sys

from sqlalchemy.exc import IntegrityError

from cms import utf8_decoder
from cms.db import Contest, Participation, SessionGen, User, \
    ask_for_contest
from cms.db import Group


logger = logging.getLogger(__name__)


def add_participations(contest_id, groupname):
    with SessionGen() as session:
        users = session.query(User)
        contest = Contest.get_from_id(contest_id, session)
        if contest is None:
            logger.error("No contest with id `%s' found.", contest_id)
            return False
        if groupname is None:
            group = contest.main_group
        else:
            group = \
                session.query(Group) \
                    .filter(Group.contest_id == contest_id,
                            Group.name == groupname).first()
            if group is None:
                logger.error("No group with name `%s' found.", groupname)
                return False

        for user in users:
            if session.query(Participation) \
                    .filter(Participation.contest_id == contest_id,
                            Participation.user_id == user.id).first():
                logger.info("Participation already exists (left untouched; group not verified): '%s'", user.username)
            else:
                participation = Participation(
                    user=user,
                    contest=contest,
                    group=group)
                session.add(participation)
                logger.info("Participation added: '%s'", user.username)

        session.commit()

    return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(description="Add a participation for every user to CMS.")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of the contest the users will be attached to")
    parser.add_argument("-g", "--group", action="store", type=utf8_decoder,
                        help="name of the group to use")

    args = parser.parse_args()

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    success = add_participations(args.contest_id, args.group)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
