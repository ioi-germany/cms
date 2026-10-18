#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2026 Luca Versari <veluca93@gmail.com>
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

"""Script to automate testing of solutions via CMS API.

The script expects a JSON file containing a list of solution checks.
Each check should be an object with the following fields:
- path: path to the solution file.
- min_score: minimum expected score.
- max_score: maximum expected score.
- checks: optional list of expected subtask outcomes, where each
  element can be:
  - null (no assertion on this subtask)
  - "Accepted" (full score on this subtask)
  - "Zero" (0 score on this subtask)
  - "PartialScore" (score > 0 and < max_score on this subtask)
  - "WrongAnswer" (at least one testcase produced a wrong answer)
  - "TimeLimitExceeded" (at least one testcase exceeded CPU time limit)
  - "WallTimeLimitExceeded" (at least one testcase exceeded wall time limit)
  - "MemoryLimitExceeded" (at least one testcase exceeded memory limit)
  - "RuntimeError" (at least one testcase failed due to runtime error)

Such a file can be generated with `task-maker-rust export-solution-checks`.
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from typing import Any
from enum import Enum

import requests

from cms.grading import format_status_text
from cmscontrib.gerpythonformat.Messenger import print_msg, print_block, \
    header, red, green, gray, yellow, blue, lightgreen, orange, purple, bold, \
    box, side_by_side, pad_left, add_line_breaks, \
    remaining_line_length, indent, IndentManager

logger = logging.getLogger(__name__)


class RedAlertFormatter(logging.Formatter):
    RED = "\x1b[31;1m"
    YELLOW = "\x1b[33;1m"
    RSET = "\x1b[0m"

    BASE_FORMAT = "%(levelname)8s %(message)s"

    RED_FORMAT = RED + "%(levelname)8s" + RSET + " %(message)s"

    YELLOW_FORMAT = YELLOW + "%(levelname)8s" + RSET + " %(message)s"

    FORMATS = {
        logging.DEBUG: BASE_FORMAT,
        logging.INFO: BASE_FORMAT,
        logging.WARNING: YELLOW_FORMAT,
        logging.ERROR: RED_FORMAT,
        logging.CRITICAL: RED_FORMAT,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.BASE_FORMAT)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class LimitVerdict(Enum):
    OK = 1
    EXCEEDED = -1
    AMBIGUOUS = 0


class ScoreVerdict(Enum):
    OK = 0
    TOO_LOW = -1
    TOO_HIGH = 1


class UnitTest:
    """Functions for basic unit tests"""

    @staticmethod
    def _check_limit(value: float, weak_limit: float, strong_limit: float):
        if value > weak_limit:
            return LimitVerdict.EXCEEDED
        if value < strong_limit:
            return LimitVerdict.OK
        return LimitVerdict.AMBIGUOUS

    @staticmethod
    def get_result(limits: LimitInfo, details: Evaluation):
        """Collect information about the evaluation.

        limits (dict): a dictionary with entries weak_time_limit and
                       strong_time_limit
        evaluation: the Evaluation object to study

        return ([unicode]): a list of reasons of failure:
                            time, time?, memory, memory? and possibly a
                            score < 1 (if the weak time and memory limits have
                            been satisfied)

        """
        result: list[str] = []

        # check time constraints
        timeverdict = UnitTest._check_limit(
            details["time"],
            limits["weak_time_limit"],
            limits["strong_time_limit"]
        )

        if (
            "wall clock limit exceeded" in (details["text"]) or
            details["time_limit_was_exceeded"]
        ):
            timeverdict = LimitVerdict.EXCEEDED
        if timeverdict == LimitVerdict.EXCEEDED:
            result.append("time")
        elif timeverdict == LimitVerdict.AMBIGUOUS:
            result.append("time?")

        # check memory constraints
        memverdict = UnitTest._check_limit(
            details["memory"] / 2**20,
            limits["weak_mem_limit"],
            limits["strong_mem_limit"],
        )

        if (
            ("violating memory limits" in (details["text"])) or
            ("Execution killed by signal" in (details["text"]))
        ):
            memverdict = LimitVerdict.EXCEEDED

        if memverdict == LimitVerdict.EXCEEDED:
            result.append("memory")
        elif memverdict == LimitVerdict.AMBIGUOUS:
            result.append("memory?")

        # check solution (if possible)
        if UnitTest.meaningful_score(result) and details["score"] is not None:
            result.append(details["score"])

        return result

    @staticmethod
    def ignore(reason: str):
        return UnitTest.is_score(reason) or reason in ("time?", "memory?")

    @staticmethod
    def is_score(reason: str):
        try:
            float(reason)
            return True
        except Exception:
            return False

    @staticmethod
    def remove_scores(results: list[str]):
        return [reason for reason in results if not UnitTest.is_score(reason)]

    @staticmethod
    def compare_score(score: float, interval: tuple[float, float]):
        if score < interval[0]:
            return ScoreVerdict.TOO_LOW
        if score > interval[1]:
            return ScoreVerdict.TOO_HIGH
        return ScoreVerdict.OK

    @staticmethod
    def meaningful_score(results: list[str]):
        """Test whether the score actually makes sense
        """
        return not ("time" in results or "memory" in results)

    @staticmethod
    def is_interval(value: object):
        if not isinstance(value, list) and not isinstance(value, tuple):
            return False
        if len(value) != 2:
            return False

        return UnitTest.is_score(value[0]) and UnitTest.is_score(value[1])

    @staticmethod
    def get_intervals(expectations: list) -> list[tuple[float, float]]:
        return [(x[0], x[1]) for x in expectations if UnitTest.is_interval(x)]

    @staticmethod
    def remove_intervals(expectations: list):
        return [x for x in expectations if not UnitTest.is_interval(x)]

    @staticmethod
    def judge_score(score: float, intervals: list[tuple[float, float] | None]):
        comparisons = [UnitTest.compare_score(score, i) for i in intervals if i]

        if any(x == ScoreVerdict.TOO_LOW for x in comparisons):
            return ScoreVerdict.TOO_LOW
        if any(x == ScoreVerdict.TOO_HIGH for x in comparisons):
            return ScoreVerdict.TOO_HIGH
        return ScoreVerdict.OK

    THRESHOLD_LAX = .1
    THRESHOLD_STRICT = .05
    THRESHOLD_VERY_STRICT = .01

    GRP_IGNORED = "You specified that the outcome of this group should " \
                  "be ignored (please only do this if you're really " \
                  "sure that's what you want)."
    GRP_TOO_LOW = "The submission failed for a reason you did not " \
                  "expect (or score too low)."
    GRP_AMBIGUOUS = "It is not clear whether the submission respects " \
                    "the limits."
    GRP_TOO_HIGH =  "You expected the submission to fail, but it didn't " \
                    "(or score too high)."
    GRP_OKAY = "... all shall be well"
    FAILED = "FAILED"
    OKAY = "OKAY"
    AMBIG = "AMBIGUOUS"
    IGN = "IGNORED"
    IMPOSSIBLE_EXPECTATIONS = "N.B.: The expectations for this group " \
                              "cannot be satisfied (expected failure due " \
                              "to time or memory constraints, but at the " \
                              "same time expected a positive score)."
    NEGATIVE_SCORE_EXPECTED = "N.B.: You expected a negative score for " \
                              "this group---why?"

    @staticmethod
    def compute_group_verdict(
        expected: list[str | tuple[float, float]],
        testcase_results: list[list[str]],
        scores: list[float]
    ):
        """Determine the verdict and a reason for a single group of a unit test.

        expected: the expectations declared for this group
        testcase_results: the results obtained for each of the group's testcases.
        scores: the score for each testcase.

        """
        results = set(reason for r in testcase_results
                             for reason in UnitTest.remove_scores(r))
        meaningful_scores = [
            score
            for r, score in zip(testcase_results, scores)
            if UnitTest.meaningful_score(r)
        ]

        # check score
        score_expectations = UnitTest.get_intervals(expected) or [(1.0, 1.0)]
        score_verdict: ScoreVerdict
        if meaningful_scores:
            subtask_score = min(meaningful_scores)
            score_verdict = UnitTest.judge_score(subtask_score, score_expectations)
        else:
            score_verdict = ScoreVerdict.OK

        missing: list[str] = []

        # judge this group
        if "arbitrary" in expected:
            res = (1337, UnitTest.IGN, UnitTest.GRP_IGNORED)

        # check time and memory
        elif any(x not in expected for x in results if not UnitTest.ignore(x)):
            res = (-1, UnitTest.FAILED, UnitTest.GRP_TOO_LOW)

        elif score_verdict == ScoreVerdict.TOO_LOW:
            res = (-1, UnitTest.FAILED, UnitTest.GRP_TOO_LOW)

        # no "time" or "memory" verdict, maybe "time?" or "memory?"?
        elif any(x.endswith("?") and x[:-1] not in expected for x in results):
            res = (0, UnitTest.AMBIG, UnitTest.GRP_AMBIGUOUS)

        # time and memory limits okay---but is this a bad thing?
        elif ("time" in expected or "memory" in expected) and (
            "time" not in results and "memory" not in results
        ):
            res = (-1, UnitTest.FAILED, UnitTest.GRP_TOO_HIGH)
            missing = (["time"] if "time" in expected else []) + (
                ["memory"] if "memory" in expected else []
            )

        elif score_verdict == ScoreVerdict.OK:
            res = (1, UnitTest.OKAY, UnitTest.GRP_OKAY)

        else:
            res = (-1, UnitTest.FAILED, UnitTest.GRP_TOO_HIGH)

        status, short, desc = res

        # sanity checks
        zero_verdict = UnitTest.judge_score(0.0, score_expectations)
        if zero_verdict == ScoreVerdict.TOO_HIGH and "arbitrary" not in expected:
            desc += "\n\n" + UnitTest.NEGATIVE_SCORE_EXPECTED

        if (
            zero_verdict == ScoreVerdict.TOO_LOW
            and ("time" in expected or "memory" in expected)
            and "arbitrary" not in expected
        ):
            desc += "\n\n" + UnitTest.IMPOSSIBLE_EXPECTATIONS

        return (status, short, desc), missing

    @staticmethod
    def is_sample_subtask(subtask):
        return subtask["score"] == 0

    @staticmethod
    def compute_unit_test_score(sr, total_score, submission_info):
        """Compute the score of a unit test.

        Format of the returned details:
            subtasks:
                name: name of the subtask
                verdict: (42, "", "")
                max_runtime: 0.412
                max_memory: 33659290                      in bytes
                testcases:
                    line: (,)                             case_line()
                    grader: (42, "No expl. exp.")         grader response

        """
        prec = submission_info["score_precision"]
        expectations = submission_info["expected"]

        sample_score = 0

        useful: set[str] = set()
        essential: set[str] = set()
        all_cases = {c["idx"] for s in sr for c in s["testcases"]}
        dominated = {d: {c for c in all_cases if c != d} for d in all_cases}

        for subtask in sr:
            idx = str(subtask["idx"])
            expected = expectations[idx]
            scores: list[float] = []
            results: list[list[str]] = []

            for tc in subtask["testcases"]:
                r = UnitTest.get_result(submission_info["limits"], tc)
                this_score = tc.get("score", 0.0)
                scores.append(this_score)
                results.append(r)

            subtask["verdict"], missing = UnitTest.compute_group_verdict(
                expected, results, scores
            )

            for tc, r in zip(subtask["testcases"], results):
                line = UnitTest.case_line(r, expected, missing)
                grader_text = format_status_text(tc["text"]).strip()

                tc["line"] = line
                tc["grader"] = grader_text
                # always give full feedback for a unit test
                tc["show_in_restricted_feedback"] = True
                tc["show_in_oi_restricted_feedback"] = True

            subtask["max_runtime"] = max(
                (c["time"] for c in subtask["testcases"]), default=None
            )
            subtask["max_memory"] = max(
                (c["memory"] for c in subtask["testcases"]), default=None
            )

            """
            Check testcase utility
            """
            if UnitTest.is_sample_subtask(subtask):
                # in a sample subtask each testcase is effectively worth 1 point
                sample_score += round(sum(scores), prec)
            else:
                for i, tc in enumerate(subtask["testcases"]):
                    codename = tc["idx"]
                    if UnitTest.essential_testcase(scores, i):
                        essential.add(codename)
                    elif not UnitTest.weak_testcase(scores, i):
                        useful.add(codename)
                    dominated[codename] &= {
                        subtask["testcases"][j]["idx"]
                        for j in UnitTest.dominated_by(scores, i)
                    }

        score_okay = (UnitTest.judge_score(total_score,
                                           [submission_info["expected_score"]])
                          == ScoreVerdict.OK)
        okay = score_okay and not any(s["verdict"][0] <= 0 for s in sr)
        sample_score_okay = None
        has_sample_subtask = any(s for s in sr if UnitTest.is_sample_subtask(s))
        if has_sample_subtask:
            sample_score = round(sample_score, prec)
            sample_score_okay = (UnitTest.judge_score(sample_score,
                                    [submission_info["expected_sample_score"]])
                                    == ScoreVerdict.OK)
            okay &= sample_score_okay

        return {
            "subtasks": sr,
            "verdict": (1, UnitTest.OKAY) if okay else (0, UnitTest.FAILED),
            "score_okay": score_okay,
            "sample_score_okay": sample_score_okay,
            "score": total_score,
            "sample_score": sample_score,
            "expected_score": submission_info["expected_score_info"],
            "expected_sample_score": submission_info["expected_sample_score_info"],
            "dominated": {d: list(u) for d, u in dominated.items()},
            "essential": list(essential),
            "useful": list(useful),
        }

    @staticmethod
    def case_line(
        results: list[str],
        expected: list[str | tuple[float, float]],
        missing: list[str],
    ):
        """Information about a single testcase as part of a group
           This function returns a list of pairs, where the first entry
           visualises the respective result and the second one is >0
           iff the result is as expected
        """
        symbols = ["✓", "≈", "✗", "―"]

        def badness(reason, r):
            if reason in r:
                return 2
            elif reason + "?" in r:
                return 1
            else:
                return 0

        def get_int(actual: int, expected: int):
            if actual > expected:
                return -1
            elif actual == expected:
                return 1
            else:
                return 0

        line: list[tuple[str, int]] = []

        # TODO: do something more clever here, like marking the time entry red when we
        # expected TLE for this group but all cases ran in time and memory?
        for reason in ["time", "memory"]:
            this_badness = badness(reason, results)
            exp_badness = badness(reason, expected)

            if reason in missing:
                line.append((symbols[this_badness], -1))
            else:
                line.append((symbols[this_badness], get_int(this_badness, exp_badness)))

        if UnitTest.meaningful_score(results):
            scores = [x for x in results if UnitTest.is_score(x)]
            assert len(scores) == 1
            line.append(
                (scores[0], 0)
            )  # TODO: let the score type do something clever here?
        else:
            line.append((symbols[-1], 0))

        if "arbitrary" in expected:
            for i in range(len(line)):
                line[i] = (line[i][0], 0)

        return line

    @staticmethod
    def essential_testcase(scores: list[float], idx: int):
        """
        Helper method for testcase utility that decides whether removing a
        given testcase from a given group would affect the scoring of a
        given submission

        scores (list): the scores of all testcases in this group on a
            given submission
        idx (int): the index of the testcase in question in the scores
            parameter
        parameter (list): the parameters of the current subtask
        """
        if len(scores) == 1:
            return True

        case_score = scores[idx]
        st_score = min(scores[:idx] + scores[(idx + 1):])

        return case_score + UnitTest.THRESHOLD_STRICT < st_score

    @staticmethod
    def weak_testcase(scores: list[float], idx: int):
        """
        Helper method for testcase utility that decides whether a testcase
        is a "weak" for a given group and submission, meaning whether it
        is useless if our goal is to enforce that the given unit test
        satisfies the expectations for the current group.

        scores (list): the scores of all testcases in this group on a
            given submission
        idx (int): the index of the testcase in question in the scores
            parameter
        """
        if UnitTest.essential_testcase(scores, idx):
            return False

        case_score = scores[idx]
        st_score = min(scores)

        return case_score > st_score + UnitTest.THRESHOLD_LAX

    @staticmethod
    def dominated_by(scores: list[float], idx: int):
        """
        Helper method for testcase utility that determines for a given testcase
        x all cases y in the current group such that x is (not necessarily
        strictly) weaker than y
        """
        return [i for i, s in enumerate(scores)
                  if s < scores[idx] + UnitTest.THRESHOLD_VERY_STRICT]



class SolutionChecker:
    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        admin_token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.admin_token = admin_token
        self.session = requests.Session()
        self.auth_header: dict[str, str] = {}

    @staticmethod
    def _extract_error_message(err: requests.exceptions.HTTPError) -> str:
        if err.response is not None:
            try:
                json_data = err.response.json()
                if "error" in json_data:
                    return json_data["error"]
            except Exception:
                pass
            if err.response.text:
                return err.response.text.strip()
        return str(err)

    def login(self):
        if self.admin_token is not None:
            if self.username is None:
                raise ValueError(
                    "Admin token requires --username to specify user to impersonate."
                )
            login_url = f"{self.base_url}/api/login"
            data = {"admin_token": self.admin_token, "username": self.username}
            if self.password is not None:
                data["password"] = self.password
            try:
                response = self.session.post(login_url, data=data)
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                err_msg = self._extract_error_message(e)
                raise RuntimeError(
                    f"Login with admin token failed: {err_msg}"
                ) from None

            res_data = response.json()
            self.auth_header = {"X-CMS-Authorization": res_data["login_data"]}
            logger.info("Successfully logged in with admin token as %s.", self.username)
            return

        if self.username is None and self.password is None:
            logger.info("No credentials provided, assuming IP autologin.")
            return

        if self.username is None and self.password is not None:
            raise ValueError(
                "Password provided without username. Please specify --username."
            )

        if self.username is not None and self.password is None:
            raise ValueError(
                f"Username '{self.username}' provided without password. "
                f"Please specify --password or use --admin-token."
            )

        login_url = f"{self.base_url}/api/login"
        try:
            response = self.session.post(
                login_url,
                data={"username": self.username, "password": self.password},
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            err_msg = self._extract_error_message(e)
            raise RuntimeError(
                f"Login failed for user '{self.username}': {err_msg}"
            ) from None

        data = response.json()
        self.auth_header = {"X-CMS-Authorization": data["login_data"]}
        logger.info("Successfully logged in as %s.", self.username)

    def submit(self, task_name: str, file_paths: str) -> str:
        task_list_url = f"{self.base_url}/api/task_list"
        response = self.session.get(task_list_url, headers=self.auth_header)
        response.raise_for_status()
        tasks = response.json().get("tasks", [])
        submission_format = []
        for t in tasks:
            if t["name"] == task_name:
                submission_format = t.get("submission_format", [])
                break
        assert submission_format, f"Task {task_name} not found in task list"

        submit_url = f"{self.base_url}/api/{task_name}/submit"
        filenames = [os.path.basename(fp) for fp in file_paths]
        files = {}
        for fmt in submission_format:
            files[fmt] = (filenames[0], open(file_paths[0], "rb")) # FIXME!

        response = self.session.post(
            submit_url,
            files=files,
            headers=self.auth_header,
        )
        response.raise_for_status()
        return response.json().get("id")

    def poll_status(
        self, task_name: str, filename: str, submission_id: str
    ) -> dict[str, Any]:
        status_url = f"{self.base_url}/tasks/{task_name}/submissions/{submission_id}"
        while True:
            response = self.session.get(status_url, headers=self.auth_header)
            response.raise_for_status()
            data = response.json()
            # status 5 is SCORED, 2 is COMPILATION_FAILED
            if data.get("status") in [2, 5]:
                return data
            time.sleep(2)

    def get_submission_details(
        self, task_name: str, submission_id: str
    ) -> list[dict[str, Any]] | None:
        endpoint = "full_details"
        url = (
            f"{self.base_url}/api/{task_name}/submissions/"
            f"{submission_id}/{endpoint}"
        )
        response = self.session.get(url, headers=self.auth_header)
        response.raise_for_status()
        return response.json().get("details")

def main():
    parser = argparse.ArgumentParser(description="CMS Solution Checker")
    parser.add_argument(
        "--checks-json",
        "-c",
        required=True,
        help="Path to solution_checks.json",
    )
    parser.add_argument(
        "--url",
        "-u",
        required=True,
        help="CMS contest URL (e.g. http://localhost:8888/contest)",
    )
    parser.add_argument("--task", "-t", required=True, help="Task name")
    parser.add_argument("--username", "-U", help="CMS username")
    parser.add_argument("--password", "-p", help="CMS password")
    parser.add_argument(
        "--admin-token", "-a", help="CMS contest admin token",
        required=True
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Disable non-warnings"
    )

    args = parser.parse_args()

    logger.setLevel(logging.WARNING if args.quiet else logging.INFO)
    ch = logging.StreamHandler()
    ch.setFormatter(RedAlertFormatter())
    logger.addHandler(ch)

    if not os.path.exists(args.checks_json):
        logger.error("%s not found.", args.checks_json)
        return 1

    with open(args.checks_json, "r") as f:
        checks = json.load(f)

    try:
        checker = SolutionChecker(
            args.url,
            args.username,
            args.password,
            admin_token=args.admin_token,
        )
        checker.login()

        submissions = {}
        logger.info("Submitting %d solutions...", len(checks))
        for criteria in checks:
            sol_path = criteria.get("filenames")
            sub_id = checker.submit(args.task, sol_path)
            submissions[sol_path[0]] = (sub_id, criteria)
            logger.info("Submitted %s: %s", sol_path[0].split("/")[-1], sub_id)

        results = []
        has_failures = False
        logger.info("Waiting for evaluations...")
        for sol_path, (sub_id, criteria) in submissions.items():
            sol_name = sol_path.split("/")[-1]
            status = checker.poll_status(args.task, sol_name, sub_id)
            failed = False
            compilation_failed = False
            errors = []
            score = 0.0
            details = None
            R = None

            if status:
                if status.get("status") == 2:
                    failed = True
                    compilation_failed = True
                    errors.append("Compilation failed.")
                else:
                    # TODO: remove these checks
                    score = status.get("public_score", 0.0)
                    min_s = criteria.get("min_score", 0.0)
                    max_s = criteria.get("max_score", 100.0)
                    if (
                        UnitTest.compare_score(score, [min_s, max_s]) !=
                        ScoreVerdict.OK
                    ):
                        failed = True
                        errors.append(
                            f"score {score} is not in range "
                            f"[{min_s}, {max_s}]"
                        )

                    details = checker.get_submission_details(args.task, sub_id)
                    info = criteria["additional_info"]
                    R = UnitTest.compute_unit_test_score(details, score, info)
                    if not R["verdict"][0]:
                        failed = True

            else:
                failed = True
                errors.append("Evaluation failed.")

            if not failed:
                logger.info("%20s: check successful", sol_name)
            else:
                has_failures = True
                for err in errors:
                    logger.error("%20s: %s", sol_name, err)

            results.append(
                {
                    "name": sol_name,
                    "criteria": criteria,
                    "score": score,
                    "compilation_failed": compilation_failed,
                    "details": details,
                    "failed": failed,
                    "result": R,
                }
            )

            # PRETTY PRINTING
            # TODO: replace this by HTML output?
            def w(details, stat_desc, length, z=False):
                status, desc = stat_desc
                return pad_left(v(status, details.strip() + " " + desc, z), length)

            def v(status, desc, z=False):
                return {  -1 : red,
                        0 : (lambda x: str(x)) if z else yellow,
                        1 : green,
                        1337 : gray}[status](desc)

            def myheader(name, status):
                status, desc, _ = status
                base_space = remaining_line_length() - 15
                space = base_space - len(name) - len(desc)

                return header(name + " " + (space - 2) * "═" + " " +
                            v(status, desc), depth=3)

            # Present verdict
            with header(f"Unit test results for {sol_name}", depth=2):
                for st in R["subtasks"]:
                    with myheader(st["name"], st["verdict"]):
                        print_msg(st["verdict"][2], use_ellipsis=False)
                        print()
                        print(indent(side_by_side(
                            [bold("Codename"), bold("Time"), bold("Memory"), bold("Answer"), bold("Grader response")],
                            [0, 12, 22, 34, 44])))

                        for c in st["testcases"]:
                            l = [(b, (a)) for a, b in c["line"]]
                            ftime = "%.3fs" % c["time"]
                            if c["memory"] is None:
                                fmem = "??? MB"
                            else:
                                fmem = "%.1fMB" % (float(c["memory"]) / 2**20)
                            ftime = w(ftime, l[0], 8, z=True)
                            fmem = w(fmem, l[1], 10, z=True)
                            fans = v(*l[2], z=True)
                            fresp = add_line_breaks(c["grader"],
                                                    remaining_line_length() - 44)

                            print(indent(side_by_side([c["idx"], ftime, fmem, fans, fresp],
                                                    [2, 10, 19, 34, 44])))

                        print()
                        print(indent("     max. runtime in this group: " +
                                        bold("{:.3f}s".format(st["max_runtime"]))))
                        print(indent("max. memory usage in this group: " +
                                        bold("%.1fMB" %
                                            (float(st["max_memory"]) / 2**20))))

                print()

            score_precision = criteria["additional_info"]["score_precision"]
            score = R["score"]
            rounded_score = round(score, score_precision)
            if score != rounded_score:
                score = "{} ({})".format(rounded_score, score)

            score = green(score) if R["score_okay"] else red(score)
            expected_score = R["expected_score"]
            print_msg(f"score: {score}; expected: {expected_score}\n")

        print()

        if has_failures:
            print_msg(red(bold("Some unit tests failed!")))
        else:
            print_msg(green(bold("All unit tests successful.")))

        return 1 if has_failures else 0

    except (ValueError, RuntimeError) as e:
        logger.error("%s", e)
        return 1
    except requests.exceptions.HTTPError as e:
        err_msg = SolutionChecker._extract_error_message(e)
        status_code = e.response.status_code if e.response is not None else "unknown"
        logger.error("API error (%s): %s", status_code, err_msg)
        return 1


if __name__ == "__main__":
    sys.exit(main())
