#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2021 Tobias Lenz <t_lenz94@web.de>
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
from future.builtins.disabled import *
from future.builtins import *

import argparse
import logging
import os
import resource
import shutil

from cmscontrib.gerpythonformat.ContestConfig import ContestConfig
from cmscontrib.gerpythonformat.LocationStack import chdir
from cms import utf8_decoder, ServiceCoord
from cms.db import Contest, Dataset, Participation, SessionGen, Submission, Task, Team, User
from cms.db.filecacher import FileCacher
from cmscontrib.gerpythonformat import copyrecursivelyifnecessary
from cms.io import Service
from cmscontrib.importing import update_contest, update_task, update_user, update_team, update_participation, _update_list_with_key, _copy, _to_delete

from six import iteritems
from psutil import virtual_memory

logger = logging.getLogger(__name__)


class GerImport(Service):
    def __init__(self, odir, no_test, clean, force):
        self.odir = odir
        self.no_test = no_test
        self.clean = clean
        self.force = force

        Service.__init__(self)

    def make(self):
        self.file_cacher = FileCacher()
        self.make_helper()

    def make_helper(self):
        # Unset stack size limit
        INFTY = int(.75 * virtual_memory().total)
        resource.setrlimit(resource.RLIMIT_STACK, (INFTY, INFTY))

        if not os.path.exists(os.path.join(self.odir, "contest-config.py")):
            raise Exception("Directory doesn't contain contest-config.py")
        self.wdir = os.path.join(self.odir, "build")
        if self.clean:
            shutil.rmtree(self.wdir)
        if not os.path.exists(self.wdir):
            os.mkdir(self.wdir)
        # We have to avoid copying the folder contest/build
        # or contest/task/build into contest/build.
        # For this reason, we ignore all files and directories named "build"
        # when copying recursively.
        copyrecursivelyifnecessary(self.odir, self.wdir, set(["build"]))

        self.wdir = os.path.abspath(self.wdir)
        with chdir(self.wdir):
            contestconfig = ContestConfig(
                os.path.join(self.wdir, ".rules"),
                os.path.basename(self.odir))

            # Read the configuration file and build.
            contestconfig._readconfig("contest-config.py")

            with SessionGen() as session:
                def session_add(k, v):
                    session.add(v)

                # Variables like udbs, teamdbs, cdb, ... contain objects before
                # they've been put into the database.
                # Their counterpars udb1s, teamdb1s, cdb1, ... contain the
                # objects that are actually in the database (which are copies
                # of the objects in udbs, ...).

                # Create users in the database.
                udbs = [contestconfig._makeuser(u) for u in contestconfig.users]
                udb1s = _update_list_with_key(session.query(User).all(),
                                              udbs,
                                              lambda u : u.username,
                                              preserve_old=True,
                                              update_value_fn=update_user,
                                              creator_fn=session_add)
                udbs = {u.username : u for u in udbs}

                # Create teams in the database.
                teamdbs = [contestconfig._maketeam(t) for t in contestconfig.teams]
                teamdb1s = _update_list_with_key(session.query(Team).all(),
                                                 teamdbs,
                                                 lambda t : t.code,
                                                 preserve_old=True,
                                                 update_value_fn=update_team,
                                                 creator_fn=session_add)
                teamdbs = {t.code : t for t in teamdbs}

                # Create contest (including associated user groups) in the database.
                cdb = contestconfig._makecontest()
                cdbs = [cdb]
                cdb1s = _update_list_with_key(session.query(Contest).all(),
                                              cdbs,
                                              lambda c : c.name,
                                              preserve_old=True,
                                              update_value_fn=update_contest,
                                              creator_fn=session_add)
                cdb1 = cdb1s[cdb.name]

                # Set the contest's main group.
                cdb1.main_group = cdb1.get_group(contestconfig.defaultgroup.name)

                # Create participations in the database.

                # Team object for a given user
                def user_team(u):
                    t = contestconfig.users[u].team
                    if t is None:
                        return None
                    else:
                        return teamdbs[t.code]
                # Team object in the database for a given user
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

                pdbs = [make_participation(u) for u in contestconfig.users]
                pdb1s = _update_list_with_key(cdb1.participations,
                                              pdbs,
                                              lambda p : p.user.username,
                                              preserve_old=True,
                                              update_value_fn=update_participation)
                pdbs = {p.user.username : p for p in pdbs}

                for username, u in iteritems(pdb1s):
                    u.user = udb1s[username]
                    u.group = cdb1.get_group(
                        contestconfig.users[username].group.name)
                    u.team = user_team1(username)

                # The test user participation.
                test_pdb = pdbs[contestconfig._mytestuser.username]
                test_pdb1 = pdb1s[contestconfig._mytestuser.username]

                # This is an ugly hack to prevent problems when reordering or
                # adding tasks. Since we delete after adding and updating,
                # there might otherwise at one point be two tasks with the same
                # number.
                for t in cdb1.tasks:
                        t.num += len(contestconfig.tasks) + len(cdb1.tasks)

                tdbs = [t._makedbobject(cdb, self.file_cacher)
                        for t in contestconfig.tasks.values()]
                tdbs_dict = {t.name: t for t in tdbs}
                # We only set the active dataset when importing a new task.
                # Afterwards, the active dataset has to be set using the web
                # interface.

                def task_creator(name, v):
                    tdb = tdbs_dict[name]
                    ddb1 = session.query(Dataset) \
                        .filter(Dataset.task == v) \
                        .filter(Dataset.description ==
                                tdb.active_dataset.description).first()
                    assert ddb1 is not None
                    v.active_dataset = ddb1
                tdb1s = _update_list_with_key(cdb1.tasks,
                                              tdbs,
                                              lambda t : t.name,
                                              preserve_old=False,
                                              update_value_fn=update_task,
                                              creator_fn=task_creator)
                tdbs = {t.name : t for t in tdbs}

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
                            _to_delete.append(sdb1)

                        # Create test submissions in the database.
                        sdbs = contestconfig.tasks[t]._make_test_submissions(
                            test_pdb, tdb, False)
                        sdb1s = []
                        for sdb in sdbs:
                            sdb1 = _copy(sdb)
                            sdb1.task = tdb1
                            sdb1.participation = test_pdb1
                            session.add(sdb1)
                            sdb1s.append(sdb1)
                        sdb1ss[t] = sdb1s

                for v in _to_delete:
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

                ans = input("Proceed? [y/N] ").strip().lower()
                if ans not in ["y", "yes"]:
                    logger.error("Aborting.")
                    return

                # Delete marked objects
                for v in _to_delete:
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

        contestconfig.finish()

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
