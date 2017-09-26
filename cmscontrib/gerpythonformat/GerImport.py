#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2016 Fabian Gundlach <320pointsguy@gmail.com>
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

from .ContestConfig import ContestConfig
from .CommonConfig import DatabaseProxyContest, DatabaseProxy
from .LocationStack import chdir
from cms import utf8_decoder, ServiceCoord
from cms.db import SessionGen, Contest, User, Participation, Group, Task, Dataset, Submission, Team
from cms.db.filecacher import FileCacher
from cmscontrib.gerpythonformat import copyrecursivelyifnecessary
from cmscontrib import BaseImporter, _is_rel
from cms.io import Service
import argparse
import os
import resource
import shutil
import logging

logger = logging.getLogger(__name__)


class GerImport(BaseImporter, Service):
    def __init__(self, odir, no_test, clean):
        self.odir = odir
        self.no_test = no_test
        self.clean = clean
        self.file_cacher = FileCacher()

        self.to_delete = []

        Service.__init__(self)

    # Copy scalar properties from new_object to old_object.
    def _update_columns(self, old_object, new_object):
        for prp in old_object._col_props:
            if hasattr(new_object, prp.key):
                setattr(old_object, prp.key, getattr(new_object, prp.key))

    # Create a recursive copy of a database object.
    # Subobjects contained in a dict or list relation are copied recursively.
    def _copy(self, new_object):
        # Copy scalar properties.
        di = {prp.key : getattr(new_object, prp.key)
              for prp in new_object._col_props}
        old_object = type(new_object)(**di)

        for prp in old_object._rel_props:
            old_value = getattr(old_object, prp.key)
            new_value = getattr(new_object, prp.key)

            # Copy relational dict properties.
            if isinstance(old_value, dict):
                assert len(old_value) == 0
                for key, value in new_value.items():
                    old_value[key] = self._copy(value)

            # Copy relational list properties.
            elif isinstance(old_value, list):
                assert len(old_value) == 0
                for value in new_value:
                    old_value.append(self._copy(value))

        return old_object

    def _update_dict(self, old_value, new_value):
        old_keys = set(old_value.keys())
        new_keys = set(new_value.keys())
        # delete
        for key in old_keys - new_keys:
            self.to_delete.append(old_value[key])
        # create
        for key in new_keys - old_keys:
            old_value[key] = self._copy(new_value[key])
        # update
        for key in new_keys & old_keys:
            self._update_object(old_value[key], new_value[key])  # TODO Do we always want default behavior?

    def _update_list(self, old_value, new_value):
        old_len = len(old_value)
        new_len = len(new_value)
        # update
        for i in xrange(min(old_len, new_len)):
            self._update_object(old_value[i], new_value[i])  # TODO Do we always want default behavior?
        if old_len > new_len:
            # delete
            for v in old_value[new_len:]:
                self.to_delete.append(v)
        elif new_len > old_len:
            # create
            for v in new_value[old_len:]:
                old_value.append(self._copy(v))

    def _update_user(self, old_object, new_object):
        self._update_columns(old_object, new_object)

        for prp in old_object._rel_props:
            old_value = getattr(old_object, prp.key)
            new_value = getattr(new_object, prp.key)

            if _is_rel(prp, User.participations):
                pass
            else:
                raise RuntimeError(
                    "Unknown type of relationship for %s.%s." %
                    (prp.parent.class_.__name__, prp.key))

    def _update_group(self, old_object, new_object):
        self._update_columns(old_object, new_object)

        for prp in old_object._rel_props:
            old_value = getattr(old_object, prp.key)
            new_value = getattr(new_object, prp.key)

            if _is_rel(prp, Group.contest):
                pass
            elif _is_rel(prp, Group.participations):
                pass
            else:
                raise RuntimeError(
                    "Unknown type of relationship for %s.%s." %
                    (prp.parent.class_.__name__, prp.key))

    def _update_contest(self, old_object, new_object):
        self._update_columns(old_object, new_object)

        for prp in old_object._rel_props:
            old_value = getattr(old_object, prp.key)
            new_value = getattr(new_object, prp.key)

            if _is_rel(prp, Contest.announcements):
                pass
            elif _is_rel(prp, Contest.tasks):
                pass
            elif _is_rel(prp, Contest.participations):
                pass
            elif _is_rel(prp, Contest.groups):
                old_groups = {g.name : g for g in old_value}
                new_groups = {g.name : g for g in new_value}
                delete = set(old_groups.keys()) - set(new_groups.keys())
                if len(delete) > 0:
                    logger.warning("Deleting groups {}".format(", ".join(delete)))
                    for key in delete:
                        self.to_delete.append(old_groups[key])
                add = set(new_groups.keys()) - set(old_groups.keys())
                if len(add) > 0:
                    logger.info("Adding groups {}".format(", ".join(add)))
                    for key in add:
                        old_groups[key] = self._copy(new_groups[key])
                change = set(old_groups.keys()) & set(new_groups.keys())
                for key in change:
                    self._update_group(old_groups[key], new_groups[key])
                old_object.groups = old_groups.values()
            elif _is_rel(prp, Contest.main_group):
                pass
            else:
                raise RuntimeError(
                    "Unknown type of relationship for %s.%s." %
                    (prp.parent.class_.__name__, prp.key))

        if old_object.main_group is None or old_object.main_group.name != new_object.main_group.name:
            old_object.main_group = old_object.get_group(new_object.main_group.name)

    def _update_participation(self, old_object, new_object):
        self._update_columns(old_object, new_object)

        for prp in old_object._rel_props:
            old_value = getattr(old_object, prp.key)
            new_value = getattr(new_object, prp.key)

            if _is_rel(prp, Participation.contest):
                pass
            elif _is_rel(prp, Participation.user):
                pass
            elif _is_rel(prp, Participation.group):
                old_object.group = old_object.contest.get_group(new_object.group.name)
            elif _is_rel(prp, Participation.team):
                pass
            elif _is_rel(prp, Participation.messages):
                pass
            elif _is_rel(prp, Participation.questions):
                pass
            elif _is_rel(prp, Participation.submissions):
                pass
            elif _is_rel(prp, Participation.user_tests):
                pass
            elif _is_rel(prp, Participation.printjobs):
                pass
            else:
                raise RuntimeError(
                    "Unknown type of relationship for %s.%s." %
                    (prp.parent.class_.__name__, prp.key))

    def _update_task(self, old_object, new_object):
        self._update_columns(old_object, new_object)

        for prp in old_object._rel_props:
            old_value = getattr(old_object, prp.key)
            new_value = getattr(new_object, prp.key)

            if _is_rel(prp, Task.contest):
                pass
            elif _is_rel(prp, Task.active_dataset):
                pass
            elif _is_rel(prp, Task.submissions):
                pass
            elif _is_rel(prp, Task.user_tests):
                pass
            elif _is_rel(prp, Task.datasets):
                assert len(new_object.datasets) == 1
                new_dataset = new_object.datasets[0]
                found = False
                for d in old_object.datasets:
                    if d.description == new_dataset.description:
                        logger.info("Updating dataset {}".format(new_dataset.description))
                        self._update_dataset(d, new_dataset)
                        found = True
                if not found:
                    logger.info("Creating dataset {}".format(new_dataset.description))
                    old_object.datasets.append(new_dataset)
            elif _is_rel(prp, Task.statements):
                self._update_dict(old_value, new_value)
            elif _is_rel(prp, Task.attachments):
                self._update_dict(old_value, new_value)
            elif _is_rel(prp, Task.submission_format):
                self._update_list(old_value, new_value)
            else:
                raise RuntimeError(
                    "Unknown type of relationship for %s.%s." %
                    (prp.parent.class_.__name__, prp.key))

    def _update_dataset(self, old_object, new_object):
        self._update_columns(old_object, new_object)

        for prp in old_object._rel_props:
            old_value = getattr(old_object, prp.key)
            new_value = getattr(new_object, prp.key)

            if _is_rel(prp, Dataset.task):
                pass
            elif _is_rel(prp, Dataset.managers):
                self._update_dict(old_value, new_value)
            elif _is_rel(prp, Dataset.testcases):
                self._update_dict(old_value, new_value)
            else:
                raise RuntimeError(
                    "Unknown type of relationship for %s.%s." %
                    (prp.parent.class_.__name__, prp.key))

    def _update_team(self, old_object, new_object):
        self._update_columns(old_object, new_object)

        for prp in old_object._rel_props:
            old_value = getattr(old_object, prp.key)
            new_value = getattr(new_object, prp.key)

            if _is_rel(prp, Team.participations):
                pass
            else:
                raise RuntimeError(
                    "Unknown type of relationship for %s.%s." %
                    (prp.parent.class_.__name__, prp.key))

    def make(self):
        # Unset stack size limit
        resource.setrlimit(resource.RLIMIT_STACK, (resource.RLIM_INFINITY,
                                                   resource.RLIM_INFINITY))

        if not os.path.exists(os.path.join(self.odir, "contest-config.py")):
            raise Exception("Directory doesn't contain contest-config.py")
        self.wdir = os.path.join(self.odir, "build")
        if self.clean:
            shutil.rmtree(self.wdir)
        if not os.path.exists(self.wdir):
            os.mkdir(self.wdir)
        copyrecursivelyifnecessary(self.odir, self.wdir, set([self.wdir]))

        self.wdir = os.path.abspath(self.wdir)
        with chdir(self.wdir):
            contestconfig = ContestConfig(
                os.path.join(self.wdir, ".rules"),
                os.path.basename(self.odir))

            # Read the configuration file and build.
            contestconfig._readconfig("contest-config.py")

            with SessionGen() as session:
                # Create users in the database.
                udbs = {}
                udb1s = {}
                for u in contestconfig.users:
                    udb = contestconfig._makeuser(u)

                    udb1 = session.query(User) \
                        .filter(User.username == udb.username).first()
                    if udb1 is not None:
                        logger.info("Updating user {}".format(u))
                        self._update_user(udb1, udb)
                    else:
                        logger.info("Creating user {}".format(u))
                        udb1 = self._copy(udb)
                        session.add(udb1)
                    udbs[u] = udb
                    udb1s[u] = udb1

                # Create contest in the database.
                cdb = contestconfig._makecontest()

                cdb1 = session.query(Contest) \
                    .filter(Contest.name == cdb.name).first()
                if cdb1 is not None:
                    logger.info("Updating contest {}".format(cdb.name))
                    self._update_contest(cdb1, cdb)
                else:
                    logger.info("Creating contest {}".format(cdb.name))
                    cdb1 = self._copy(cdb)
                    cdb1.main_group = cdb1.get_group(cdb.main_group.name)
                    session.add(cdb1)

                # Create teams in the database.
                teamdbs = {}
                teamdb1s = {}
                for t in contestconfig.teams:
                    teamdb = contestconfig._maketeam(t)

                    teamdb1 = session.query(Team) \
                        .filter(Team.code == teamdb.code).first()
                    if teamdb1 is not None:
                        logger.info("Updating team {}".format(t))
                        self._update_team(teamdb1, teamdb)
                    else:
                        logger.info("Creating team {}".format(t))
                        teamdb1 = self._copy(teamdb)
                        session.add(teamdb1)
                    teamdbs[t] = teamdb
                    teamdb1s[t] = teamdb1

                # Create participations in the database.
                pdbs = {}
                pdb1s = {}
                for u in contestconfig.users:
                    udb = udbs[u]
                    udb1 = udb1s[u]

                    teamcode = None if contestconfig.users[u].team is None else contestconfig.users[u].team.code
                    pdb = contestconfig._makeparticipation(u, cdb, udb, cdb.get_group(contestconfig.users[u].group.name), None if teamcode is None else teamdbs[teamcode])

                    pdb1 = None if cdb1 is None or udb1 is None else session.query(Participation) \
                        .filter(Participation.contest == cdb1) \
                        .filter(Participation.user == udb1).first()
                    if pdb1 is not None:
                        logger.info("Updating participation {}".format(u))
                        self._update_participation(pdb1, pdb)
                        pdb1.team = None if teamcode is None else teamdb1s[teamcode]
                    else:
                        logger.info("Creating participation {}".format(u))
                        pdb1 = self._copy(pdb)
                        pdb1.contest = cdb1
                        pdb1.user = udb1
                        pdb1.group = cdb1.get_group(pdb.group.name)
                        pdb1.team = None if teamcode is None else teamdb1s[teamcode]
                        session.add(pdb1)

                    pdbs[u] = pdb
                    pdb1s[u] = pdb1

                # The test user participation.
                test_pdb = pdbs[contestconfig._mytestuser.username]
                test_pdb1 = pdb1s[contestconfig._mytestuser.username]

                # TODO Remove tasks, participations, ...
                for t in contestconfig.tasks:
                    # Create task in the database.
                    tdb = contestconfig.tasks[t]._makedbobject(cdb, self.file_cacher)

                    tdb1 = session.query(Task) \
                        .filter(Task.name == tdb.name).first()
                    if tdb1 is not None:
                        if cdb1 is None or tdb1.contest != cdb1:
                            raise Exception("Task {} already exists, but is not assigned to this contest".format(t))
                        logger.info("Updating task {}".format(t))
                        self._update_task(tdb1, tdb)
                        ddb1 = session.query(Dataset) \
                            .filter(Dataset.task == tdb1) \
                                .filter(Dataset.description == tdb.active_dataset.description).first()
                        assert ddb1 is not None
                        tdb1.active_dataset = ddb1
                    else:
                        logger.info("Creating task {}".format(t))
                        tdb2 = self._copy(tdb)
                        tdb2.contest = cdb1
                        session.add(tdb2)

                    if not self.no_test:
                        # Mark old test submissions for deletion.
                        sdb1s = session.query(Submission) \
                            .filter(Submission.participation == test_pdb1) \
                            .filter(Submission.task == tdb1) \
                            .filter(Submission.additional_info != None).all()
                        for sdb1 in sdb1s:
                            self.to_delete.append(sdb1)

                        # Create test submissions in the database.
                        sdbs = contestconfig.tasks[t]._make_test_submissions(test_pdb, tdb, False)
                        sdb1s = []
                        for sdb in sdbs:
                            sdb1 = self._copy(sdb)
                            sdb1.task = tdb1
                            sdb1.participation = test_pdb1
                            session.add(sdb1)
                            sdb1s.append(sdb1)

                # Delete marked objects
                for v in self.to_delete:
                    session.delete(v)

                session.commit()

                if not self.no_test:
                    # Notify EvaluationService of the new test submissions.
                    evaluation_service = self.connect_to(
                        ServiceCoord("EvaluationService", 0))
                    for sdb1 in sdb1s:
                        evaluation_service.new_submission(
                            submission_id=sdb1.id)

                logger.info("Import finished (new contest id: %s).", cdb.id if cdb1 is None else cdb1.id)


def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(
        description="Import a contest (generate test cases, statements, test "
                    "test submissions, ...)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("import_directory",
                        help="source directory",
                        type=utf8_decoder)
    parser.add_argument("-nt", "--no-test", action="store_true",
                        help="don't change test submissions; without this "
                        "flag, all test submissions are deleted and the re-"
                        "added.")
    parser.add_argument("-c", "--clean", action="store_true",
                        help="clean the build directory (forcing a complete "
                        "rebuild)")

    args = parser.parse_args()

    GerImport(os.path.abspath(args.import_directory),
              args.no_test,
              args.clean).make()


if __name__ == "__main__":
    main()
