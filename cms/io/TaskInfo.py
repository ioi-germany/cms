#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2016-2017 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2016 Simon Bürger <simon.buerger@rwth-aachen.de>
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

import contextlib
import json
import logging
import re

from datetime import datetime
from pathlib import Path
from multiprocessing import Process, Manager
from subprocess import check_output
from sys import exc_info
from traceback import format_exception
from time import time
from copy import deepcopy
from math import sqrt
from typing import Collection

from six import iteritems

from cms.io.BackgroundScheduler import BackgroundScheduler
from cms.io.Repository import Repository
from cmscontrib.gerpythonformat.ContestConfig import ContestConfig
from cmscontrib.gerpythonformat.LocationStack import chdir

logger = logging.getLogger(__name__)


class DateEntry:
    def __init__(self, date_code, info):
        self.date = datetime.strptime(date_code, "%Y-%m-%d").date()
        self.info = info + " {}".format(self.date.year)

    def timestamp(self):
        return self.date.toordinal()

    def to_dict(self):
        return {"timestamp": self.timestamp(),
                "info":      self.info}


class SingleTaskInfo:
    def __init__(self, code: str, path: Path):
        self.code = code
        self.title = "???"
        self.source = "N/A"
        self.algorithm = -1
        self.implementation = -1
        self.keywords = []
        self.uses: Collection[DateEntry] = []
        self.remarks = ""
        self.public = False
        self.old = None
        self.folder = ""
        self.timestamp = 0
        self.error = None

        if not path.exists():
            i = {"error": "The info.json file is missing."}
        else:
            try:
                i = json.loads(path.open().read())
            except Exception:
                i = {"error": "The info.json file is corrupt."}
            else:
                missing = []
                for e in ["title", "algorithm", "implementation", "public"]:
                    if e not in i:
                        missing.append(e)

                if len(missing) > 0:
                    i["error"] = "Some important entries are missing: " + \
                                 ", ".join(missing) + "."
                else:
                    def bad(x):
                        try:
                            y = int(x)
                        except Exception:
                            return True
                        else:
                            return y < 0 or y > 10

                    if bad(i["algorithm"]):
                        i["algorithm"] = 0
                        i["error"] = "Invalid value for \"algorithm\": " \
                                     "expected an integer between 0 and 10."

                    if bad(i["implementation"]):
                        i["implementation"] = 0
                        i["error"] = "Invalid value for \"implementation\": " \
                                     "expected an integer between 0 and 10."

        self.update(i)

        if self.old is None:
            self.old = len(self.uses) > 0 or self.public

    def update(self, i):
        for key, value in iteritems(i):
            if key == "uses":
                try:
                    self.uses = [DateEntry(e[0], e[1]) for e in i["uses"]]
                except ValueError:
                    self.uses = []

                    if self.error is not None:
                        self.error = "I couldn't parse the dates for " \
                                        "\"(previous) uses\"."
            else:
                setattr(self, key, value)

    def to_dict(self):
        result = {
            "code": self.code,
            "title": self.title,
            "source": self.source,
            "algorithm": self.algorithm,
            "implementation": self.implementation,
            "keywords": self.keywords,
            "uses": [e.to_dict() for e in self.uses],
            "remarks": self.remarks,
            "public": self.public,
            "old": self.old,
        }

        if self.error is not None:
            result["error"] = self.error

        return result


class TaskInfo:
    tasks = Manager().dict()
    unconfirmed_usage = Manager().dict()

    @staticmethod
    def init(
        repository: Repository,
        tasks_folders: Collection[str],
        contests_folders: Collection[str],
    ):
        def load(repository_root: Path, tasks_folders: Collection[str], tasks):
            for folder in tasks_folders:
                directory = repository_root / folder
                if not directory.exists() or not directory.is_dir():
                    logger.warning(
                        'Task folder "{}" does not exist or is not '
                        "a directory, skipping.".format(directory)
                    )
                    continue
                # Load all available tasks
                for d in directory.iterdir():
                    if not d.is_dir():
                        continue

                    # We catch all exceptions since the main loop must go on
                    try:
                        info_path = d / "info.json"

                        code = d.parts[-1]
                        info = SingleTaskInfo(code, info_path).to_dict()

                        old = tasks.get(code, {"timestamp": 0})
                        info["timestamp"] = old["timestamp"]
                        info["folder"] = folder

                        if old != info:
                            info["timestamp"] = time()
                            tasks[code] = info

                    except Exception:
                        logger.info("\n".join(format_exception(*exc_info())))

        def update_tasklist(repository: Repository, tasks_folders: Collection[str], tasks):
            repository_root = Path(repository.path)
            start = time()
            with repository:
                # Remove tasks that are no longer available
                for t in tasks.keys():
                    info_path = repository_root / tasks[t]["folder"] / t

                    if not info_path.exists():
                        del tasks[t]

                load(repository_root, tasks_folders, tasks)

            logger.info("finished iteration of TaskInfo.update_tasklist in {}ms".
                        format(int(1000 * (time() - start))))

        def load_usage(repository_root: Path, unconfirmed_usage) -> None:
            try:
                with open(repository_root / ".unconfirmed_usage.json", "r") as f:
                    data = f.read().splitlines()
                unconfirmed_usage.clear()
                for line in data:
                    parsed_line = json.loads(line)
                    if "task" not in parsed_line or "uses" not in parsed_line:
                        logger.warning("skipping corrupted line {}".format(line))
                        continue
                    task_code = parsed_line["task"]
                    if task_code not in unconfirmed_usage:
                        unconfirmed_usage[task_code] = []
                    confirmed = (
                        parsed_line["confirmed"]
                        if "confirmed" in parsed_line
                        else False
                    )
                    unconfirmed_usage[task_code] += [
                        {
                            "uses": DateEntry(*parsed_line["uses"]).to_dict(),
                            "confirmed": confirmed,
                        }
                    ]
            except FileNotFoundError:
                pass
            except Exception:
                logger.warning("file .unconfirmed_usage.json is corrupt")
                logger.warning("\n".join(format_exception(*exc_info())))

        def is_same_contest(
            contest_code: str, contestconfig: ContestConfig, info
        ) -> bool:
            if contestconfig.defaultgroup is None:
                return False
            start = contestconfig.defaultgroup.start.toordinal()
            stop = contestconfig.defaultgroup.stop.toordinal()
            if start <= info["timestamp"] and info["timestamp"] <= stop:
                return True
            # date in old info.json files might be off by a few days
            # => try to match info.info with contest_code / config
            if info["timestamp"] < start - 42 or stop + 42 < info["timestamp"]:
                return False
            description = re.sub(r"\s+\d+$", "", info["info"]).lower()
            clean_info = make_clean_info(contest_code).lower()
            if (clean_info in description) or (description in clean_info):
                return True

            olympiad = re.search(
                r"^(.{1,4}oi)\d+[-_].*", contest_code, flags=re.IGNORECASE
            )
            if olympiad is None:
                return False
            olympiad = olympiad.group()
            if hasattr(contestconfig, "_short_name"):
                short_name = re.sub(
                    r"\s+\d+$", "", getattr(contestconfig, "_short_name")
                ).lower()
                if (short_name in description) or (description in short_name):
                    return True
            return False

        def should_track_usage(contest_code: str) -> bool:
            """Returns wheter the usage of a task in this contest should be tracked
            in the info.json

            """
            if "test" in contest_code.lower():
                # ignore technical tests
                return False
            return True

        def make_clean_info(contest_code: str) -> str:
            """Returns a "clean" description of the contest from its
            contest_code to be used in the weboverview.
            For example "ioiYYYY_1-1" => "lg1"

            """
            match = re.match(
                r"^(.{1,4}oi)\d+[-_](.*)", contest_code, flags=re.IGNORECASE
            )
            if match is None:
                return contest_code
            olympiad, usage = map(lambda s: s.lower(), match.groups())
            # remove enumerating suffix "-1", "-2", ..., usually campname-dayX
            usage = re.sub(r"[-_]?\d$", "", usage)
            info = ""
            if olympiad == "ioi" and re.match(r"\d", usage):
                info = olympiad + " lg" + usage
            else:
                info = olympiad + " " + usage
            return info

        def parse_contests(
            repository_root: Path,
            contests_folders: Collection[str],
            tasks,
            unconfirmed_usage,
        ) -> list:
            untracked = []
            for folder in contests_folders:
                directory = repository_root / folder
                if not directory.exists() or not directory.is_dir():
                    logger.warning(
                        'Contest folder "{}" does not exist or is not'
                        " a directory, skipping.".format(directory)
                    )
                    continue
                for d in directory.iterdir():
                    try:
                        if not d.is_dir():
                            continue
                        contest_code = d.parts[-1]
                        if not should_track_usage(contest_code):
                            continue
                        config_path = d / "contest-config.py"
                        if not config_path.exists():
                            logger.info(
                                'Contest "{}" has no contest-config, ignoring.'.format(
                                    d
                                )
                            )
                            continue
                        with chdir(d):
                            contestconfig = ContestConfig(
                                d / ".rules",
                                contest_code,
                                ignore_latex=True,
                                minimal=True,
                            )
                            with contextlib.redirect_stdout(None):
                                # _parseconfig doesn't perform any actions, so we suppress
                                # log messages like "Creating ..."
                                contestconfig._parseconfig("contest-config.py")
                        if contestconfig.defaultgroup is None:
                            logger.info(
                                'Contest "{}" has no default group, ignoring.'.format(d)
                            )
                            continue
                        # only update the usage after the contest ended
                        if datetime.now() < contestconfig.defaultgroup.stop:
                            continue
                        for t in contestconfig.tasks.keys():
                            task_code = t
                            task_path = d / t
                            # if the symlink to the task got deleted, we still try to
                            # update usage with the task code that was used in the contest
                            if task_path.exists():
                                task_code = task_path.resolve().parts[-1]
                            if task_code not in tasks:
                                continue
                            task_info = tasks[task_code]
                            if any(
                                is_same_contest(contest_code, contestconfig, x)
                                for x in task_info["uses"]
                            ):
                                # usage is already stored in the info.json
                                continue
                            if task_code in unconfirmed_usage and any(
                                is_same_contest(contest_code, contestconfig, x["uses"])
                                for x in unconfirmed_usage[task_code]
                            ):
                                # at this point the usage was detected and stored
                                # in a previous run, but marked as false positive,
                                # so we ignore it
                                continue
                            contest_day = contestconfig.defaultgroup.start.strftime(
                                "%Y-%m-%d"
                            )
                            info = make_clean_info(contest_code)
                            usage = DateEntry(contest_day, info).to_dict()
                            untracked.append({"task": task_code, "usage": usage})
                            logger.info(f"found usage for task {task_code} in {info}")
                    except Exception:
                        logger.error("Failed to process contest {}".format(d))
                        logger.error("\n".join(format_exception(*exc_info())))
            return untracked

        def store_usage(
            repository: Repository, untracked: list, tasks, unconfirmed_usage
        ) -> None:
            repository_root = Path(repository.path)
            for v in untracked:
                try:
                    task_code, usage = v["task"], v["usage"]
                    task = tasks[task_code]
                    usage_time = datetime.fromordinal(usage["timestamp"])
                    usage_time = usage_time.strftime("%Y-%m-%d")
                    # remove trailing year
                    usage_info = re.sub(r"\s+\d+$", "", usage["info"])
                    info_path = (
                        repository_root / Path(task["folder"]) / task_code / "info.json"
                    )
                    info_path = info_path.resolve()
                    with open(info_path, "r") as f:
                        old_data = json.load(f)
                    if "uses" not in old_data:
                        old_data["uses"] = []
                    old_data["uses"].append([usage_time, usage_info])
                    old_data["uses"].sort()
                    with open(info_path, "w") as f:
                        json.dump(old_data, f, indent=4)
                    err = repository.commit(
                        str(info_path),
                        commit_message=f"Add usage in contest {usage['info']} "
                        f"to task {task_code}, from TaskOverviewBackend",
                        author='"cmsTaskOverviewWebserver <cmsTaskOverviewWebserver@localhost>"',
                    )
                    if err is not None:
                        # committing changes failed, so we try to restore the changes
                        # and retry in the next iteration
                        try:
                            check_output(["git", "checkout", "--", str(info_path)])
                        except Exception as e:
                            logger.error(
                                "restoring old version of {} failed with error {}".format(
                                    info_path, e
                                )
                            )
                        continue
                    task["uses"] += [usage]
                    task["timestamp"] = time()
                    if task_code not in unconfirmed_usage:
                        unconfirmed_usage[task_code] = []
                    unconfirmed_usage[task_code] += [
                        {"uses": usage, "confirmed": False}
                    ]
                    with open(repository_root / ".unconfirmed_usage.json", "a") as f:
                        f.write(
                            f'{{"task":"{task_code}", \
                            "uses":["{usage_time}", "{usage_info}"], \
                            "confirmed":false}}\n'
                        )
                except Exception:
                    logger.error("Failed to update task {}".format(task_code))
                    logger.error("\n".join(format_exception(*exc_info())))

        def update_usage(
            repository: Repository,
            contests_folders: Collection[str],
            tasks,
            unconfirmed_usage,
            only_load=False,
        ) -> None:
            repository_root = Path(repository.path)
            start = time()
            with repository:
                load_usage(repository_root, unconfirmed_usage)
                if not only_load:
                    untracked = parse_contests(
                        repository_root, contests_folders, tasks, unconfirmed_usage
                    )
                    store_usage(repository, untracked, tasks, unconfirmed_usage)

            logger.info(
                "finished iteration of TaskInfo.update_usage in {}ms".format(
                    int(1000 * (time() - start))
                )
            )

        def run(repository, tasks_folders, contests_folders, tasks, unconfirmed_usage):
            scheduler = BackgroundScheduler()
            scheduler.every(
                0.5 * (1 + sqrt(5)),
                update_tasklist,
                args=(repository, tasks_folders, tasks),
            )
            scheduler.every(
                0.5 * (1 + sqrt(5)),
                update_usage,
                args=(repository, contests_folders, tasks, unconfirmed_usage),
                only_load=True,
            )
            # Usage data will be updated only after a contest ended
            # so we can query less frequent
            scheduler.every(
                3600,
                update_usage,
                args=(repository, contests_folders, tasks, unconfirmed_usage),
                skip_first=False,
                priority=1,
            )
            scheduler.run(blocking=True)

        # Load data once on start-up (otherwise tasks might get removed when
        # the server is restarted)
        with repository:
            load(Path(repository.path), tasks_folders, TaskInfo.tasks)

        TaskInfo.info_process = Process(
            target=run,
            args=(
                repository,
                tasks_folders,
                contests_folders,
                TaskInfo.tasks,
                TaskInfo.unconfirmed_usage,
            ),
        )
        TaskInfo.info_process.daemon = True
        TaskInfo.info_process.start()

    @staticmethod
    def task_list():
        data = deepcopy(TaskInfo.tasks)

        return [{"task": data[t]["code"], "timestamp": data[t]["timestamp"]}
                for t in data]

    @staticmethod
    def get_info(keys):
        task_data = deepcopy(TaskInfo.tasks)
        usage_data = deepcopy(TaskInfo.unconfirmed_usage)
        res = {}
        for t in keys:
            if t not in task_data:
                continue
            res[t] = task_data[t]
            if t in usage_data:
                for u in res[t]["uses"]:
                    for v in usage_data[t]:
                        if u == v["uses"]:
                            u["confirmed"] = v["confirmed"]
                            break
        return res

    @staticmethod
    def entries():
        return ["code", "title", "source", "algorithm", "implementation",
                "keywords", "uses", "remarks", "public", "download"]

    @staticmethod
    def desc():
        return {"code": "Code",
                "title": "Title",
                "source": "Source",
                "algorithm": "Diff<sub>Alg</sub>",
                "implementation": "Diff<sub>Impl</sub>",
                "keywords": "Keywords",
                "uses": "Previous uses",
                "remarks": "Remarks",
                "public": "Public?",
                "download": "PDF"}
