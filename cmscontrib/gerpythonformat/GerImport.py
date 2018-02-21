#!/usr/bin/env python
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

import argparse
import logging
import os
import resource
import shutil
import sys

from cmscontrib.gerpythonformat.ContestConfig import ContestConfig
from cmscontrib.gerpythonformat.LocationStack import chdir
from cms import utf8_decoder, ServiceCoord
from cms.db import Attachment, Contest, Dataset, Group, Manager, \
    Participation, SessionGen, Statement, Submission, \
    SubmissionFormatElement, Task, Team, Testcase, User
from cms.db.filecacher import FileCacher
from cmscontrib.gerpythonformat import copyrecursivelyifnecessary
from cmscontrib import BaseImporter, _is_rel
from cms.io import Service

from six import iteritems

logger = logging.getLogger(__name__)


class GerImport(BaseImporter, Service):
    def __init__(self, odir, no_test, clean, force):
        self.odir = odir
        self.no_test = no_test
        self.clean = clean
        self.force = force

        self.to_delete = []

        self.update_prefix = []

        Service.__init__(self)

    def attrstr(self, a):
        return ".".join(self.update_prefix + [a])

    def _update_columns(self, old_object, new_object, ignore=None):
        ignore = ignore if ignore is not None else set()
        for prp in old_object._col_props:
            if prp.key in ignore:
                continue
            if hasattr(new_object, prp.key):
                old_value = getattr(old_object, prp.key)
                new_value = getattr(new_object, prp.key)
                if old_value != new_value:
                    logger.info("Changing {} from {} to {}".format(
                        self.attrstr(prp.key), old_value, new_value))
                    setattr(old_object, prp.key, getattr(new_object, prp.key))

    # Create a recursive copy of a database object.
    # Subobjects contained in a dict or list relation are copied recursively.
    def _copy(self, new_object):
        # Copy scalar properties.
        di = {prp.key: getattr(new_object, prp.key)
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

    def _update_dict(self, old_value, new_value, delete=True,
                     creator_function=None):
        old_keys = set(old_value.keys())
        new_keys = set(new_value.keys())
        # delete
        if delete:
            for key in sorted(old_keys - new_keys):
                logger.info("Deleting {}".format(
                    self.attrstr("{}({})".format(type(old_value[key]).__name__, key))))
                self.to_delete.append(old_value[key])
        # create
        for key in sorted(new_keys - old_keys):
            logger.info("Creating {}".format(
                self.attrstr("{}({})".format(type(new_value[key]).__name__, key))))
            v = self._copy(new_value[key])
            old_value[key] = v
            if creator_function is not None:
                creator_function(key, v)
        # update
        for key in sorted(new_keys & old_keys):
            self.update_prefix.append("{}({})".format(type(old_value[key]).__name__, key))
            self._update_dispatcher(old_value[key], new_value[key])
            self.update_prefix.pop()
        return {key: old_value[key] for key in new_value}

    def _update_list(self, old_value, new_value):
        old_len = len(old_value)
        new_len = len(new_value)
        # update
        for i in xrange(min(old_len, new_len)):
            self._update_dispatcher(old_value[i], new_value[i])
        if old_len > new_len:
            # delete
            for v in old_value[new_len:]:
                self.to_delete.append(v)
        elif new_len > old_len:
            # create
            for v in new_value[old_len:]:
                old_value.append(self._copy(v))

    def _update_dispatcher(self, old_value, new_value):
        bla = {
            # Custom update
            User: self._update_user,
            Group: self._update_group,
            Contest: self._update_contest,
            Participation: self._update_participation,
            Task: self._update_task,
            Dataset: self._update_dataset,
            Team: self._update_team,
            # Default update
            Testcase: self._update_object,
            Manager: self._update_object,
            Attachment: self._update_object,
            SubmissionFormatElement: self._update_object,
            Statement: self._update_object,
        }
        bla[type(old_value)](old_value, new_value)

    def _update_user(self, old_object, new_object):
        self._update_columns(old_object, new_object)

        for prp in old_object._rel_props:
            if _is_rel(prp, User.participations):
                pass
            else:
                raise RuntimeError(
                    "Unknown type of relationship for %s.%s." %
                    (prp.parent.class_.__name__, prp.key))

    def _update_group(self, old_object, new_object):
        self._update_columns(old_object, new_object)

        for prp in old_object._rel_props:
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
            if _is_rel(prp, Contest.announcements):
                pass
            elif _is_rel(prp, Contest.tasks):
                pass
            elif _is_rel(prp, Contest.participations):
                pass
            elif _is_rel(prp, Contest.groups):
                pass
            elif _is_rel(prp, Contest.main_group):
                pass
            else:
                raise RuntimeError(
                    "Unknown type of relationship for %s.%s." %
                    (prp.parent.class_.__name__, prp.key))

        old_groups = {g.name: g for g in old_object.groups}
        new_groups = {g.name: g for g in new_object.groups}
        self._update_dict(old_groups, new_groups, delete=True,
                          creator_function=lambda _, v:
                              old_object.groups.append(v))

        if old_object.main_group is None or \
                old_object.main_group.name != new_object.main_group.name:
            old_object.main_group = old_object.get_group(
                new_object.main_group.name)

    def _update_participation(self, old_object, new_object):
        self._update_columns(old_object, new_object)

        for prp in old_object._rel_props:
            if _is_rel(prp, Participation.contest):
                pass
            elif _is_rel(prp, Participation.user):
                pass
            elif _is_rel(prp, Participation.group):
                pass
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
        old_object.group = old_object.contest.get_group(new_object.group.name)

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
                pass
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

        old_datasets = {g.description: g for g in old_object.datasets}
        new_datasets = {g.description: g for g in new_object.datasets}
        assert len(new_datasets) == 1
        self._update_dict(old_datasets, new_datasets, delete=False,
                          creator_function=lambda _, v:
                              old_object.datasets.append(v))

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
            if _is_rel(prp, Team.participations):
                pass
            else:
                raise RuntimeError(
                    "Unknown type of relationship for %s.%s." %
                    (prp.parent.class_.__name__, prp.key))

    def make(self):
        self.file_cacher = FileCacher()
        try:
            self.make_helper()
        finally:
            self.file_cacher.destroy_cache()

    def make_helper(self):
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
                # FIXME This has running time proportional to the total number
                # of users, not just the number of users for this contest.
                udbs = {u: contestconfig._makeuser(
                    u) for u in contestconfig.users}
                udb1s = {u.username: u for u in session.query(User).all()}
                self._update_dict(udb1s, udbs, delete=False,
                                  creator_function=lambda _, v: session.add(v))

                # Create teams in the database.
                teamdbs = {t: contestconfig._maketeam(
                    t) for t in contestconfig.teams}
                teamdb1s = {t.code: t for t in session.query(Team)}
                self._update_dict(teamdb1s, teamdbs, delete=False,
                                  creator_function=lambda _, v: session.add(v))

                # Create contest in the database.
                cdb = contestconfig._makecontest()
                cdbs = {cdb.name: cdb}
                cdb1s = {c.name: c for c in session.query(Contest).all()}
                self._update_dict(cdb1s, cdbs, delete=False,
                                  creator_function=lambda _, v: session.add(v))
                cdb1 = cdb1s[cdb.name]
                cdb1.main_group = cdb1.get_group(cdb.main_group.name)

                # Create participations in the database.
                def user_team(u):
                    t = contestconfig.users[u].team
                    if t is None:
                        return None
                    else:
                        return teamdbs[t.code]

                def user_team1(u):
                    t = contestconfig.users[u].team
                    if t is None:
                        return None
                    else:
                        return teamdb1s[t.code]

                def make_participation(u):
                    gdb = cdb.get_group(contestconfig.users[u].group.name)
                    return contestconfig._makeparticipation(u, cdb, udbs[u],
                                                            gdb, user_team(u))

                pdbs = {u: make_participation(u) for u in contestconfig.users}
                pdb1s = {p.user.username: p for p in cdb1.participations}
                pdb1s = self._update_dict(pdb1s, pdbs, delete=True,
                                          creator_function=lambda _, v:
                                              cdb1.participations.append(v))
                for username, u in iteritems(pdb1s):
                    u.user = udb1s[username]
                    u.group = cdb1.get_group(
                        contestconfig.users[username].group.name)
                    u.team = user_team1(username)

                # The test user participation.
                test_pdb = pdbs[contestconfig._mytestuser.username]
                test_pdb1 = pdb1s[contestconfig._mytestuser.username]

                # FIXME
                # This is an ugly hack to prevent problems when reordering or
                # adding tasks. Since we delete after adding and updating,
                # there might otherwise at one point be two tasks with the same
                # number.
                for t in cdb1.tasks:
                    t.num += len(contestconfig.tasks) + len(cdb1.tasks)

                tdbs = {n: t._makedbobject(cdb, self.file_cacher)
                        for n, t in iteritems(contestconfig.tasks)}
                tdb1s = {t.name: t for t in cdb1.tasks}
                # We only set the active dataset when importing a new task.
                # Afterwards, the active dataset has to be set using the web
                # interface.

                def task_creator(name, v):
                    tdb = tdbs[name]
                    cdb1.tasks.append(v)
                    ddb1 = session.query(Dataset) \
                        .filter(Dataset.task == v) \
                        .filter(Dataset.description ==
                                tdb.active_dataset.description).first()
                    assert ddb1 is not None
                    v.active_dataset = ddb1
                self._update_dict(tdb1s, tdbs, delete=True,
                                  creator_function=task_creator)

                sdb1ss = {}
                if not self.no_test:
                    logger.warning("Replacing test submissions")
                    for t in contestconfig.tasks:
                        tdb = tdbs[t]
                        tdb1 = tdb1s[t]
                        # Mark old test submissions for deletion.
                        sdb1s = session.query(Submission) \
                            .filter(Submission.participation == test_pdb1) \
                            .filter(Submission.task == tdb1) \
                            .filter(Submission.additional_info != None).all()
                        for sdb1 in sdb1s:
                            assert sdb1.is_unit_test()
                            self.to_delete.append(sdb1)

                        # Create test submissions in the database.
                        sdbs = contestconfig.tasks[t]._make_test_submissions(
                            test_pdb, tdb, False)
                        sdb1s = []
                        for sdb in sdbs:
                            sdb1 = self._copy(sdb)
                            sdb1.task = tdb1
                            sdb1.participation = test_pdb1
                            session.add(sdb1)
                            sdb1s.append(sdb1)
                        sdb1ss[t] = sdb1s

                for v in self.to_delete:
                    if isinstance(v, Task):
                        logger.warning("Removing task {}"
                                       .format(v.name))
                        if any(not s.is_unit_test() for s in v.submissions):
                            logger.warning(
                                "There are submissions for task {}."
                                .format(v.name))
                            if not self.force:
                                logger.error("Aborting. Run with -f to force "
                                             "deletion.")
                                return
                    elif isinstance(v, Participation):
                        logger.warning("Removing participation {}"
                                       .format(v.user.username))
                        if any(not s.is_unit_test() for s in v.submissions):
                            logger.warning(
                                "There are submissions for participation {}."
                                .format(v.user.username))
                            if not self.force:
                                logger.error("Aborting. Run with -f to force "
                                             "deletion.")
                                return

                if self.force:
                    logger.warning("Force flace -f set.")

                print("Proceed? [y/N] ", end='')
                ans = sys.stdin.readline().strip().lower()
                if ans not in ["y", "yes"]:
                    logger.error("Aborting.")
                    return

                # Delete marked objects
                for v in self.to_delete:
                    session.delete(v)

                session.commit()

                if not self.no_test:
                    evaluation_service = self.connect_to(
                        ServiceCoord("EvaluationService", 0))
                    for t in contestconfig.tasks:
                        sdb1s = sdb1ss[t]
                        # Notify EvaluationService of the new test submissions.
                        for sdb1 in sdb1s:
                            evaluation_service.new_submission(
                                submission_id=sdb1.id)
                    evaluation_service.disconnect()

                logger.info("Import finished (new contest id: %s).",
                            cdb.id if cdb1 is None else cdb1.id)


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
    parser.add_argument("-f", "--force", action="store_true",
                        help="force deletion of tasks and participations with "
                        "submissions")

    args = parser.parse_args()

    GerImport(os.path.abspath(args.import_directory),
              args.no_test,
              args.clean,
              args.force).make()


if __name__ == "__main__":
    main()
