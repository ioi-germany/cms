#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2016-2017 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2016 Simon Bürger <simon.buerger@rwth-aachen.de>
# Copyright © 2026 Erik Sünderhauf <erik.suenderhauf@gmx.de>
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
from typing import Collection, Iterator, List

from cms.io.BackgroundScheduler import BackgroundScheduler
from cms.io.Repository import Repository
from cmscontrib.gerpythonformat.ContestConfig import ContestConfig
from cmscontrib.gerpythonformat.LocationStack import chdir

logger = logging.getLogger(__name__)


class DateEntry:
    def __init__(self, date_code, info):
        self.date = datetime.strptime(date_code, "%Y-%m-%d").date()
        self.info = info + " {}".format(self.date.year + (1 if self.date.month >= 8 else 0))

    def timestamp(self):
        return self.date.toordinal()

    def to_dict(self):
        return {"timestamp": self.timestamp(),
                "info":      self.info}


class SingleTaskInfo:
    PUBLIC_TAG = "public"
    PRIVATE_TAG = "private"

    def __init__(self, code: str, folder: Path):
        self.code = code
        self.title = "???"
        self.source = "N/A"
        self.algorithm = -1
        self.implementation = -1
        self.keywords = []
        self.uses: Collection[DateEntry] = []
        self.remarks = ""
        self.public = None
        self.tags: List[str] = []
        self.old = None
        self.folder = folder
        self.timestamp = 0
        self.error = None

    def update(self, data: dict):
        for key, value in data.items():
            if key == "uses":
                try:
                    self.uses = [DateEntry(e[0], e[1]) for e in data["uses"]]
                except ValueError:
                    self.uses = []
                    if self.error is None:
                        self.error = (
                            'I couldn\'t parse the dates for "(previous) uses".'
                        )
            else:
                setattr(self, key, value)
        if self.public and self.PUBLIC_TAG not in map(str.lower, self.tags):
            self.tags.append(self.PUBLIC_TAG)
        if (
            self.public is not None # for legacy tags
            and not self.public
            and self.PRIVATE_TAG not in map(str.lower, self.tags)
        ):
            self.tags.append(self.PRIVATE_TAG)
        if self.old is None:
            self.old = len(self.uses) > 0 or self.public

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
            "tags": self.tags,
            "old": self.old,
            "folder": str(self.folder),
            "error": self.error
        }

        return result

class TaskDataSource:
    """Base class representing different data sources for the tasks"""

    def __init__(self, tasks, is_annotator=False) -> None:
        self.tasks = tasks
        self.is_annotator = is_annotator

    def merge_uses(self, new: list, old: list) -> list:
        def clean(u):
            return {k: v for k, v in u.items() if k != "confirmed"}

        lookup = {frozenset(clean(u).items()): dict(u) for u in old}
        res = {}
        if self.is_annotator:
            res = lookup
        for u in new:
            k = frozenset(clean(u).items())
            v = lookup.get(k, None)
            if v is not None:
                # only annotate existing data
                v.update(u)
                res[k] = v
            elif not self.is_annotator:
                res[k] = dict(u)
        return list(res.values())

    def merge(self, new: dict, old: dict) -> dict:
        res = dict(old)
        for k, v in new.items():
            if k not in res and self.is_annotator:
                continue
            if k == "uses":
                res[k] = self.merge_uses(v, res.get(k, []))
            else:
                res[k] = v
        return res

    def apply(self, data: dict) -> None:
        for task_code, info in data.items():
            if info is None:
                if not self.is_annotator:
                    self.tasks.pop(task_code, None)
                continue
            old = self.tasks.get(task_code, {"timestamp": 0})
            info = self.merge(info, old)
            if info != old:
                info["timestamp"] = time()
                self.tasks[task_code] = info

    def load_once(self, repository: Repository) -> None:
        """responsible for loading data on startup"""
        pass

    def schedule(self, scheduler: BackgroundScheduler, repository: Repository) -> None:
        """responsible for registering (recurring) data updates"""
        pass

class InfoJsonSource(TaskDataSource):
    REQUIRED_FIELDS = ("title", "algorithm", "implementation")

    def __init__(self, tasks, tasks_folders: Collection[str]):
        super().__init__(tasks)
        self.tasks_folders = tasks_folders
        self.task_codes: set[str] = set()

    def load_once(self, repository: Repository) -> None:
        self.update(repository)

    def schedule(self, scheduler: BackgroundScheduler, repository: Repository) -> None:
        scheduler.every(0.5 * (1 + sqrt(5)), self.update, args=[repository])

    def load(self, repository: Repository) -> dict:
        repository_root = Path(repository.path)
        res: dict = {}
        cur_codes: set[str] = set()
        for task_dir in self.task_iter(repository_root):
            # We catch all exceptions since the main loop must go on
            try:
                code = task_dir.parts[-1]
                cur_codes.add(code)
                folder = task_dir.relative_to(repository_root).parent
                task_info = SingleTaskInfo(code, Path(folder))
                task_info.update(self.parse_single(task_dir))
                res[code] = task_info.to_dict()
            except Exception:
                logger.info("\n".join(format_exception(*exc_info())))
        # Remove tasks that are no longer available
        for code in self.task_codes - cur_codes:
            res[code] = None
        self.task_codes = cur_codes
        return res

    def parse_single(self, task_dir: Path) -> dict:
        info_path = task_dir / "info.json"
        if not info_path.exists():
            return {"error": "The info.json file is missing."}
        try:
            i = json.loads(info_path.open().read())
        except Exception:
            return {"error": "The info.json file is corrupt."}
        missing = []
        for e in self.REQUIRED_FIELDS:
            if e not in i:
                missing.append(e)

        if len(missing) > 0:
            i["error"] = (
                "Some important entries are missing: " + ", ".join(missing) + "."
            )
            return i

        def bad(x):
            try:
                y = int(x)
            except Exception:
                return True
            else:
                return y < 0 or y > 10

        for k in ["algorithm", "implementation"]:
            if bad(i[k]):
                i[k] = 0
                i["error"] = (
                    f'Invalid value for "{k}": expected an integer between 0 and 10.'
                )
        return i

    def update(self, repository: Repository) -> None:
        start = time()
        with repository:
            self.apply(self.load(repository))
        logger.info(
            "Parsed all info.json's in {}ms".format(int(1000 * (time() - start)))
        )

    def task_iter(self, repository_root) -> Iterator[Path]:
        """iterates over all tasks, which are
        in one of the configured tasks_folders
        """
        for folder in self.tasks_folders:
            directory = repository_root / folder
            if not directory.exists() or not directory.is_dir():
                logger.warning(
                    'Tasks folder "{}" does not exist or is not '
                    "a directory, skipping.".format(directory)
                )
                continue
            # Load all available tasks
            for task_dir in directory.iterdir():
                if not task_dir.is_dir():
                    continue
                yield task_dir


class ContestConfigSource(TaskDataSource):

    def __init__(self, tasks, contests_folders: Collection[str]) -> None:
        super().__init__(tasks, is_annotator=True)
        self.contests_folders = contests_folders
        self.unconfirmed_usage: dict[str, list[dict]] = {}

    def load_once(self, repository: Repository) -> None:
        self.apply(self.load_usage(Path(repository.path)))

    def schedule(self, scheduler: BackgroundScheduler, repository: Repository) -> None:
        scheduler.every(
            0.5 * (1 + sqrt(5)),
            self.update_usage,
            args=[repository],
            only_load=True,
        )
        # Usage data will be updated only after a contest ended
        # so we can query less frequent
        scheduler.every(
            3600,
            self.update_usage,
            args=[repository],
            _skip_first=False,
            _priority=1,
        )

    def update_usage(self, repository: Repository, only_load: bool = False) -> None:
        repository_root = Path(repository.path)
        start = time()
        with repository:
            self.apply(self.load_usage(repository_root))
            if not only_load:
                untracked = self.parse_contests(repository_root)
                self.store_usage(repository, untracked)
        logger.info(
            "finished iteration of ContestConfigSource.update_usage in {}ms".format(
                int(1000 * (time() - start))
            )
        )

    def load_usage(self, repository_root: Path) -> dict:
        try:
            with open(repository_root / ".unconfirmed_usage.json", "r") as f:
                data = f.read().splitlines()
        except FileNotFoundError:
            return {}
        except Exception:
            logger.warning("file .unconfirmed_usage.json is corrupt")
            logger.warning("\n".join(format_exception(*exc_info())))
            return {}
        self.unconfirmed_usage.clear()
        for line in data:
            try:
                parsed_line = json.loads(line)
            except Exception:
                logger.warning("skipping corrupted line {}".format(line))
                continue
            if "task" not in parsed_line or "uses" not in parsed_line:
                logger.warning("skipping corrupted line {}".format(line))
                continue
            task_code = parsed_line["task"]
            if task_code not in self.unconfirmed_usage:
                self.unconfirmed_usage[task_code] = []
            confirmed = parsed_line.get("confirmed", False)
            entry = {
                "uses": DateEntry(*parsed_line["uses"]).to_dict(),
                "confirmed": confirmed,
            }
            self.unconfirmed_usage[task_code] += [entry]
        res = {}
        for task_code, uses in self.unconfirmed_usage.items():
            res[task_code] = {"uses": []}
            for u in uses:
                u, c = u["uses"], u["confirmed"]
                u["confirmed"] = c
                res[task_code]["uses"].append(u)
        return res

    @staticmethod
    def is_same_contest(contest_code: str, contestconfig: ContestConfig, info) -> bool:
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
        clean_info = ContestConfigSource.make_clean_info(contest_code).lower()
        if (clean_info in description) or (description in clean_info):
            return True

        olympiad = re.search(r"^(.{1,4}oi)\d+[-_].*", contest_code, flags=re.IGNORECASE)
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

    @staticmethod
    def make_clean_info(contest_code: str) -> str:
        """Returns a "clean" description of the contest from its
        contest_code to be used in the weboverview.
        For example "ioiYYYY_1-1" => "lg1"

        """
        match = re.match(r"^(.{1,4}oi)\d+[-_](.*)", contest_code, flags=re.IGNORECASE)
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

    def parse_contests(self, repository_root: Path) -> list:
        untracked = []
        for contest_dir in self.contest_iter(repository_root):
            try:
                contest_code = contest_dir.parts[-1]
                with chdir(contest_dir):
                    contestconfig = ContestConfig(
                        contest_dir / ".rules",
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
                        'Contest "{}" has no default group, ignoring.'.format(
                            contest_dir
                        )
                    )
                    continue
                # only update the usage after the contest ended
                if datetime.now() < contestconfig.defaultgroup.stop:
                    continue
                for t in contestconfig.tasks.keys():
                    task_code = t
                    task_path = contest_dir / t
                    # if the symlink to the task got deleted, we still try to
                    # update usage with the task code that was used in the contest
                    if task_path.exists():
                        task_code = task_path.resolve().parts[-1]
                    if task_code not in self.tasks:
                        continue
                    task_info = self.tasks[task_code]
                    if any(
                        self.is_same_contest(contest_code, contestconfig, x)
                        for x in task_info["uses"]
                    ):
                        # usage is already stored in the info.json
                        continue
                    if task_code in self.unconfirmed_usage and any(
                        self.is_same_contest(contest_code, contestconfig, x["uses"])
                        for x in self.unconfirmed_usage[task_code]
                    ):
                        # at this point the usage was detected and stored
                        # in a previous run, but marked as false positive,
                        # so we ignore it
                        continue
                    contest_day = contestconfig.defaultgroup.start.strftime("%Y-%m-%d")
                    info = self.make_clean_info(contest_code)
                    usage = DateEntry(contest_day, info).to_dict()
                    untracked.append({"task": task_code, "usage": usage})
                    logger.info(
                        f"found usage for task {task_code} in {info} ({contest_code})"
                    )
            except Exception:
                logger.error("Failed to process contest {}".format(contest_dir))
                logger.error("\n".join(format_exception(*exc_info())))
        return untracked

    def store_usage(self, repository: Repository, untracked: list) -> None:
        repository_root = Path(repository.path)
        for v in untracked:
            try:
                task_code, usage = v["task"], v["usage"]
                task = self.tasks[task_code]
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
                        with chdir(repository.path):
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
                if task_code not in self.unconfirmed_usage:
                    self.unconfirmed_usage[task_code] = []
                self.unconfirmed_usage[task_code] += [
                    {"uses": usage, "confirmed": False}
                ]
                log_entry = json.dumps(
                    {
                        "task": task_code,
                        "uses": [usage_time, usage_info],
                        "last_update": datetime.now().isoformat(),
                        "confirmed": False,
                    }
                )
                with open(repository_root / ".unconfirmed_usage.json", "a") as f:
                    f.write(log_entry + "\n")
            except Exception:
                logger.error("Failed to update task {}".format(task_code))
                logger.error("\n".join(format_exception(*exc_info())))

    @staticmethod
    def should_track_usage(contest_code: str) -> bool:
        """Returns wheter the usage of a task in this contest should be tracked
        in the info.json
        """
        if "test" in contest_code.lower():
            # ignore technical tests
            return False
        return True

    def contest_iter(self, repository_root: Path) -> Iterator[Path]:
        """iterates over all contests, which contain a contest-config.py, are
        in one of the configured contests_folders, and whose usage should be tracked
        """
        for folder in self.contests_folders:
            directory = repository_root / folder
            if not directory.exists() or not directory.is_dir():
                logger.warning(
                    'Contest folder "{}" does not exist or is not'
                    " a directory, skipping.".format(directory)
                )
                continue
            for contest_dir in directory.iterdir():
                try:
                    if not contest_dir.is_dir():
                        continue
                    contest_code = contest_dir.parts[-1]
                    if not self.should_track_usage(contest_code):
                        continue
                    config_path = contest_dir / "contest-config.py"
                    if not config_path.exists():
                        logger.info(
                            'Contest "{}" has no contest-config, ignoring.'.format(
                                contest_dir
                            )
                        )
                        continue
                    yield contest_dir
                except Exception:
                    logger.error("Failed to process contest {}".format(contest_dir))
                    logger.error("\n".join(format_exception(*exc_info())))


class TaskInfo:
    tasks = Manager().dict()

    @staticmethod
    def init(
        repository: Repository,
        tasks_folders: Collection[str],
        contests_folders: Collection[str],
    ):
        def run_scheduler(repository, sources: List[TaskDataSource]):
            scheduler = BackgroundScheduler()
            for s in sources:
                s.schedule(scheduler, repository)
            scheduler.run(blocking=True)

        sources: List[TaskDataSource] = [
            InfoJsonSource(TaskInfo.tasks, tasks_folders),
            ContestConfigSource(TaskInfo.tasks, contests_folders)
        ]

        # Load data once on start-up (otherwise tasks might get removed when
        # the server is restarted)
        for s in sources:
            s.load_once(repository)

        TaskInfo.info_process = Process(
            target=run_scheduler,
            args=(repository, sources),
            daemon=True,
        )
        TaskInfo.info_process.start()

    @staticmethod
    def task_list() -> list:
        data = deepcopy(TaskInfo.tasks)
        return [
            {"task": data[t]["code"], "timestamp": data[t]["timestamp"]} for t in data
        ]

    @staticmethod
    def get_info(keys, all_tasks = False) -> dict:
        task_data = deepcopy(TaskInfo.tasks)
        res = {}
        for t in (task_data if all_tasks else keys):
            if t not in task_data:
                continue
            res[t] = task_data[t]
        return res

    @staticmethod
    def entries() -> list:
        return ["code", "title", "source", "algorithm", "implementation",
                "keywords", "uses", "remarks", "tags", "download"]

    @staticmethod
    def desc() -> dict:
        return {
            "code": "Code",
            "title": "Title",
            "source": "Source",
            "algorithm": "Diff<sub>Alg</sub>",
            "implementation": "Diff<sub>Impl</sub>",
            "keywords": "Keywords",
            "uses": "Previous uses",
            "remarks": "Remarks",
            "tags": "Tags",
            "download": "PDF",
        }
