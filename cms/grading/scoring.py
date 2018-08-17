#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2015 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

from collections import namedtuple

from sqlalchemy.orm import joinedload

from cms.db import Submission
from cmscommon.constants import SCORE_MODE_MAX, SCORE_MODE_MAX_TOKENED_LAST


__all__ = [
    "compute_changes_for_dataset", "task_score",
]


SubmissionScoreDelta = namedtuple(
    'SubmissionScoreDelta',
    ['submission', 'old_score', 'new_score',
     'old_public_score', 'new_public_score',
     'old_ranking_score_details', 'new_ranking_score_details'])


def compute_changes_for_dataset(old_dataset, new_dataset):
    """This function will compute the differences expected when changing from
    one dataset to another.

    old_dataset (Dataset): the original dataset, typically the active one.
    new_dataset (Dataset): the dataset to compare against.

    returns (list): a list of tuples of SubmissionScoreDelta tuples
        where they differ. Those entries that do not differ will have
        None in the pair of respective tuple entries.

    """
    # If we are switching tasks, something has gone seriously wrong.
    if old_dataset.task is not new_dataset.task:
        raise ValueError(
            "Cannot compare datasets referring to different tasks.")

    task = old_dataset.task

    def compare(a, b):
        if a == b:
            return False, (None, None)
        else:
            return True, (a, b)

    # Construct query with all relevant fields to avoid roundtrips to the DB.
    submissions = \
        task.sa_session.query(Submission)\
            .filter(Submission.task == task)\
            .options(joinedload(Submission.participation))\
            .options(joinedload(Submission.token))\
            .options(joinedload(Submission.results)).all()

    ret = []
    for s in submissions:
        old = s.get_result(old_dataset)
        new = s.get_result(new_dataset)

        diff1, pair1 = compare(
            old.score if old is not None else None,
            new.score if new is not None else None)
        diff2, pair2 = compare(
            old.public_score if old is not None else None,
            new.public_score if new is not None else None)
        diff3, pair3 = compare(
            old.ranking_score_details if old is not None else None,
            new.ranking_score_details if new is not None else None)

        if diff1 or diff2 or diff3:
            ret.append(SubmissionScoreDelta(*(s,) + pair1 + pair2 + pair3))

    return ret


# Computing global scores (for ranking).

def task_score(participation, task):
    """Return the score of a contest's user on a task.

    participation (Participation): the user and contest for which to
        compute the score.
    task (Task): the task for which to compute the score.

    return ((float, bool)): the score of user on task, and True if not
        all submissions of the participation in the task have been scored.

    """
    # As this function is primarily used when generating a rankings table
    # (AWS's RankingHandler), we optimize for the case where we are generating
    # results for all users and all tasks. As such, for the following code to
    # be more efficient, the query that generated task and user should have
    # come from a joinedload with the submissions, tokens and
    # submission_results table. Doing so means that this function should incur
    # no exta database queries.

    submissions = [s for s in participation.submissions
                   if s.task is task and s.official]
    if len(submissions) == 0:
        return 0.0, False

    submissions_and_results = [
        (s, s.get_result(task.active_dataset))
        for s in sorted(submissions, key=lambda s: s.timestamp)]

    if task.score_mode == SCORE_MODE_MAX:
        return _task_score_max(submissions_and_results)
    elif task.score_mode == SCORE_MODE_MAX_TOKENED_LAST:
        return _task_score_max_tokened_last(submissions_and_results)
    else:
        raise ValueError("Unknown score mode '%s'" % task.score_mode)


def _task_score_max_tokened_last(submissions_and_results):
    """Compute score using the "max tokened last" score mode.

    This was used in IOI 2010-2012. The score of a participant on a task is
    the maximum score amongst all tokened submissions and the last submission
    (not yet computed scores count as 0.0).

    submissions_and_results ([(Submission, SubmissionResult|None)]): list of
        all submissions and their results for the participant on the task (on
        the dataset of interest); result is None if not available (that is,
        if the submission has not been compiled).

    return ((float, bool)): (score, partial), same as task_score().

    """
    partial = False

    # The score of the last submission (if computed, otherwise 0.0). Note that
    # partial will be set to True in the next loop.
    last_score = 0.0
    _, last_sr = submissions_and_results[-1]
    if last_sr is not None and last_sr.scored():
        last_score = last_sr.score

    # The maximum score amongst the tokened submissions (not yet computed
    # scores count as 0.0).
    max_tokened_score = 0.0
    for s, sr in submissions_and_results:
        if sr is not None and sr.scored():
            if s.tokened():
                max_tokened_score = max(max_tokened_score, sr.score)
        else:
            partial = True

    return max(last_score, max_tokened_score), partial


def _task_score_max(submissions_and_results):
    """Compute score using the "max" score mode.

    This was used in IOI 2013-2016. The score of a participant on a task is
    the maximum score amongst all submissions (not yet computed scores count
    as 0.0).

    submissions_and_results ([(Submission, SubmissionResult|None)]): list of
        all submissions and their results for the participant on the task (on
        the dataset of interest); result is None if not available (that is,
        if the submission has not been compiled).

    return ((float, bool)): (score, partial), same as task_score().

    """
    partial = False
    score = 0.0

    for _, sr in submissions_and_results:
        if sr is not None and sr.scored():
            score = max(score, sr.score)
        else:
            partial = True

    return score, partial


class UnitTest:
    """Functions for basic unit tests
    """
    @staticmethod
    def get_result(limits, evaluation):
        """Collect information about the evaluation.

        limits (dict): a dictionary with entries weak_time_limit and
                       strong_time_limit
        evaluation (Evaluation): the Evaluation object to study

        return ([unicode]): a list of reasons of failure:
                            time, time?, memory, memory? and possibly a
                            score < 1 (if the weak time and memory limits have
                            been satisfied)

        """
        result = []

        def check(val, weak, strong):
            if val > weak:
                return -1
            if val < strong:
                return 1
            else:
                return 0

        # check time constraints
        # TODO What if this is None?
        if evaluation.execution_time is not None:
            timeverdict = check(float(evaluation.execution_time),
                                float(limits["weak_time_limit"]),
                                float(limits["strong_time_limit"]))

            if "wall clock limit exceeded" in (evaluation.text)[0]:
                timeverdict = -1

            if timeverdict == -1:
                result.append("time")
            elif timeverdict == 0:
                result.append("time?")

        # check memory constraints
        # TODO What if this is None?
        if evaluation.execution_memory is not None:
            memverdict = check(float(evaluation.execution_memory) / 2**20,
                               float(limits["weak_mem_limit"]),
                               float(limits["strong_mem_limit"]))
            if "violating memory limits" in (evaluation.text)[0]:
                memverdict = -1
            if memverdict == -1:
                result.append("memory")
            elif memverdict == 0:
                result.append("memory?")

        # check solution (if possible)
        if UnitTest.meaningful_score(result):
            result.append(evaluation.outcome)

        return result

    @staticmethod
    def ignore(x, l):
        return UnitTest.is_score(x) or ("time" in l and x == "time?") or\
                                       ("memory" in l and x == "memory?")

    @staticmethod
    def is_score(x):
        try:
            float(x)
            return True
        except:
            return False

    @staticmethod
    def get_scores(l):
        return [float(x) for x in l if UnitTest.is_score(x)]

    @staticmethod
    def remove_scores(l):
        return [x for x in l if not UnitTest.is_score(x)]

    @staticmethod
    def score(results):
        """Get the minimum score of a list of results.

        results ([unicode]): list of results
                             (time, time?, memory, memory? or a score)

        return (float): minimum score (1.0 if no score is present)

        """
        return min(UnitTest.get_scores(results) + [1.0])

    @staticmethod
    def compare_score(score, interval):
        if score < interval[0]:
            return -1
        if score > interval[1]:
            return 1
        return 0

    @staticmethod
    def meaningful_score(results):
        """Test whether the score actually makes sense
        """
        return not('time' in results or 'memory' in results)

    @staticmethod
    def is_interval(x):
        if not isinstance(x, list):
            return False
        if len(x) != 2:
            return False

        return UnitTest.is_score(x[0]) and UnitTest.is_score(x[1])

    @staticmethod
    def get_intervals(l):
        return [x for x in l if UnitTest.is_interval(x)]

    @staticmethod
    def remove_intervals(l):
        return [x for x in l if not UnitTest.is_interval(x)]

    @staticmethod
    def case_line(results, mandatory, _optional, c=['✓', '≈', '✗', '―']):
        """Information about a single testcase as part of a group
           This function returns a list of pairs, where the first entry
           visualises the respective result and the second one is >0
           iff the result is as expected
        """
        optional = _optional + mandatory

        def badness(key, r):
            if key in r:
                return 2
            if key + '?' in r:
                return 1
            else:
                return 0

        def get_int(b):
            if b:
                return 1
            else:
                return -1

        L = []

        for x in ['time', 'memory']:
            L.append((c[badness(x, results)],
                      get_int((x in results or x not in mandatory) and
                              badness(x, results) <= badness(x, optional))))

        if UnitTest.meaningful_score(results):
            s = UnitTest.score(results)

            optional_intervals = UnitTest.get_intervals(optional)
            if len(optional_intervals) == 0:
                optional_intervals = [[1.0, 1.0]]

            score_okay = all(UnitTest.compare_score(s, i) == 0
                             for i in UnitTest.get_intervals(mandatory)) and \
                         all(UnitTest.compare_score(s, i) != -1
                             for i in optional_intervals)
            L.append((s, get_int(score_okay)))
        else:
            L.append((c[-1], 0))

        if "arbitrary" in optional:
            for i in range(0, len(L)):
                L[i] = (L[i][0], 0)

        return L

    @staticmethod
    def judge_score(x, intervals):
        l = [UnitTest.compare_score(x, i) for i in intervals]

        if any(x < 0 for x in l):
            return -1
        if any(x > 0 for x in l):
            return 1
        return 0

    @staticmethod
    def judge_scores(scores, intervals):
        if len(scores) == 0:
            return 0
        else:
            return min(UnitTest.judge_score(s, intervals) for s in scores)

    @staticmethod
    def judge_group(results, _extended_results, mandatory, _optional):
        """Judge a whole group given a concatenated list of the results of
           the individual cases
           extended_results contains results of testcases with explicit
           expectations
        """
        optional = _optional + mandatory
        extended_results = results + _extended_results

        if "arbitrary" in mandatory:
            return (1337, "ignored", "You specified that this specific "
                    "outcome should be ignored (please only do this if you're "
                    "really sure that's what you want).")

        if "arbitrary" in optional and len(mandatory) != 0:
            raise Exception("Undefined behaviour: you specified the outcome of "
                            "a group as arbitrary while giving specific "
                            "expectations for at least one testcase in this "
                            "group. I don't know what to do.")

        scores = UnitTest.get_scores(results)

        # When checking whether the score is too low we also care about the
        # optional score constraints
        intervals = UnitTest.get_intervals(optional) or [[1.0, 1.0]]
        score_verdict = UnitTest.judge_scores(scores, intervals)

        if score_verdict == -1 or any(x not in optional for x in results
                                      if not UnitTest.ignore(x,
                                          ['time', 'memory'])):
            return (-2, "failed", "The submission failed for a reason "
                    "you did not expect (or score too low).")

        if any(x.endswith("?") for x in results
               if not UnitTest.ignore(x, optional)):
            return (0, "ambiguous", "It is not clear whether the submission "
                       "respects the limits.")

        # When checking whether the score is too high we only care about the
        # mandatory score constraints
        intervals = UnitTest.get_intervals(mandatory) or [[1.0, 1.0]]
        score_verdict = UnitTest.judge_scores(scores, intervals)

        mandatory = UnitTest.remove_intervals(mandatory)

        if (score_verdict == 0 and (len(mandatory) == 0 or
                                    UnitTest.score(results) != 1.0)) or\
           any(x in extended_results for x in mandatory):
            return (1, "okay", "... all shall be well.")

        return (-1, "failed",
                "You expected the submission to fail but it didn't "
                "(or score too high).")

    @staticmethod
    def judge_case(results, mandatory, optional):
        """Judge a single testcase
        """
        if "arbitrary" in mandatory:
            raise Exception("Undefined behaviour: you specified the outcome of "
                            "a testcase as arbitrary. I don't know what to do")

        a, b, c = UnitTest.judge_group(results, [], mandatory, optional)
        return a, c
