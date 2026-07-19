#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2015 wafrelka <wafrelka@gmail.com>
# Copyright © 2014-2015 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2014-2026 Tobias Lenz <t_lenz94@web.de>
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


"""In this file there is the basic infrastructure from which we can
build a score type.

A score type is a class that receives all submissions for a task and
assign them a score, keeping the global state of the scoring for the
task.

"""

import json
import logging
import re
from typing import TypedDict, NotRequired, cast
from abc import ABCMeta, abstractmethod

from cms import FEEDBACK_LEVEL_RESTRICTED
from cms.db import SubmissionResult
from cms.grading.steps import EVALUATION_MESSAGES
from cms.locale import Translation, DEFAULT_TRANSLATION
from cms.server.jinja2_toolbox import GLOBAL_ENVIRONMENT
from cms.grading import format_status_text
from cms.grading.scoring import ScoreVerdict, UnitTest
from jinja2 import Template


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message: str):
    return message


class ScoreType(metaclass=ABCMeta):
    """Base class for all score types, that must implement all methods
    defined here.

    """

    TEMPLATE = ""

    def __init__(self, parameters: object, public_testcases: dict[str, bool],
                 score_precision: int):
        """Initializer.

        parameters: format is specified in the subclasses.
        public_testcases: associate to each testcase's codename
                          a boolean indicating if the testcase
                          is public.

        """
        self.parameters = parameters
        self.public_testcases = public_testcases
        self.score_precision = score_precision

        # Preload the maximum possible scores.
        try:
            self.max_score, self.max_public_score, self.ranking_headers = \
                self.max_scores()

            # Only SubtaskGroup has this method. I think it's not needed with
            # the other scoretypes. But this is certainly a messy way to make
            # this distinction. SubtaskGroup is also the only one that is
            # really used and thus tested in our fork right now, because
            # GerMake _always_ uses it.
            if hasattr(self, "score_column_headers"):
                self.public_score_header, self.private_score_header = \
                    self.score_column_headers()
        except Exception as e:
            raise ValueError(
                "Unable to instantiate score type (probably due to invalid "
                "values for the score type parameters): %s." % e)

        self.template: Template = GLOBAL_ENVIRONMENT.from_string(self.TEMPLATE)

    @staticmethod
    def format_score(
        score: float,
        max_score: float,
        unused_score_details: object,
        translation: Translation = DEFAULT_TRANSLATION,
    ) -> str:
        """Produce the string of the score that is shown in CWS.

        In the submission table in the task page of CWS the global
        score of the submission is shown (the sum of all subtask and
        testcases). This method is in charge of producing the actual
        text that is shown there. It can be overridden to provide a
        custom message (e.g. "Accepted"/"Rejected").

        score: the global score of the submission.
        max_score: the maximum score that can be achieved.
        unused_score_details: the opaque data structure that
            the ScoreType produced for the submission when scoring it.
        translation: the translation to use.

        return: the message to show.

        """
        return "%s / %s" % (
            translation.format_decimal(score),
            translation.format_decimal(max_score))

    @staticmethod
    def unit_test_result(unit_test_score_details):
        return unit_test_score_details["verdict"][0]

    @staticmethod
    def format_unit_test_verdict(unit_test_score_details):
        return unit_test_score_details["verdict"][1]

    def get_html_details(
        self,
        score_details: object,
        feedback_level: str = FEEDBACK_LEVEL_RESTRICTED,
        translation: Translation = DEFAULT_TRANSLATION,
    ) -> str:
        """Return an HTML string representing the score details of a
        submission.

        score_details: the data saved by the score type
            itself in the database; can be public or private.
        feedback_level: the level of details to show to users.
        translation: the translation to use.

        return: an HTML string representing score_details.

        """
        _ = translation.gettext
        n_ = translation.ngettext
        if score_details is None:
            logger.error("Found a null score details string. "
                         "Try invalidating scores.")
            return _("Score details temporarily unavailable.")
        else:
            # FIXME we should provide to the template all the variables
            # of a typical CWS context as it's entitled to expect them.
            try:
                return self.template.render(details=score_details,
                                            feedback_level=feedback_level,
                                            translation=translation,
                                            gettext=_, ngettext=n_)
            except Exception:
                logger.exception("Found an invalid score details string. "
                                 "Try invalidating scores.")
                return _("Score details temporarily unavailable.")

    @abstractmethod
    def max_scores(self) -> tuple[float, float, list[str]]:
        """Returns the maximum score that one could aim to in this
        problem. Also return the maximum score from the point of view
        of a user that did not play the token. And the headers of the
        columns showing extra information (e.g. subtasks) in RWS.
        Depend on the subclass.

        return: maximum score and maximum score with only public
            testcases; ranking headers.

        """
        pass

    @abstractmethod
    def compute_score(
        self, submission_result: SubmissionResult
    ) -> tuple[float, object, float, object, list[str]]:
        """Computes a score of a single submission.

        submission_result: the submission
            result of which we want the score

        return: respectively: the score, an opaque JSON-like data
            structure with additional information (e.g. testcases' and
            subtasks' score) that will be converted to HTML by
            get_html_details, the score and a similar data structure
            from the point of view of a user who did not play a token,
            the list of strings to send to RWS.

        """
        pass

    def compute_unit_test_score(self, submission_result,
                                submission_info):
        """
        You might want to override this
        """
        return {}

    def feedback(self):
        """
        You might want to override this
        """
        return "token"


class ScoreTypeAlone(ScoreType):
    """Intermediate class to manage tasks where the score of a
    submission depends only on the submission itself and not on the
    other submissions' outcome. Remains to implement compute_score to
    obtain the score of a single submission and max_scores.

    """
    pass


class ScoreTypeGroupParametersDict(TypedDict):
    max_score: float
    testcases: int | str | list[str]
    threshold: NotRequired[float]
    always_show_testcases: NotRequired[bool]
    key: NotRequired[list[str]]
    name: NotRequired[str]


# the format of parameters is impossible to type-hint correctly, it seems...
# this hint is (mostly) correct for the methods this base class implements,
# subclasses might need a longer tuple.
ScoreTypeGroupParameters = tuple[float, int | str | list[str]] | ScoreTypeGroupParametersDict


class ScoreTypeGroup(ScoreTypeAlone):
    """Intermediate class to manage tasks whose testcases are
    subdivided in groups (or subtasks). The score type parameters must
    be in the form [[m, t, ...], [...], ...], where m is the maximum
    score for the given subtask and t is the parameter for specifying
    testcases, or be a list of dicts matching ScoreTypeGroupParametersDict.

    If t is int, it is interpreted as the number of testcases
    comprising the subtask (that are consumed from the first to the
    last, sorted by num). If t is unicode, it is interpreted as the regular
    expression of the names of target testcases. If t is a list of strings,
    it is interpreted as a list of testcase codenames. All t must have the
    same type.

    A subclass must implement the method 'get_public_outcome' and
    'reduce'.

    """
    parameters: list[ScoreTypeGroupParameters]

    # Mark strings for localization.
    N_("Subtask %(index)s")
    N_("#")
    N_("Outcome")
    N_("Details")
    N_("Execution time")
    N_("Memory used")
    N_("N/A")
    TEMPLATE = """\
{% for st in details %}
    {% if "score_fraction" in st %}
        {% if st["score_fraction"] >= 1.0 %}
<div class="subtask correct">
        {% elif st["score_fraction"] <= 0.0 %}
<div class="subtask notcorrect">
        {% else %}
<div class="subtask partiallycorrect">
        {% endif %}
    {% else %}
<div class="subtask undefined">
    {% endif %}
    <div class="subtask-head">
        <span class="title">
            {% trans index=st["idx"] %}Subtask {{ index }}{% endtrans %}
        </span>
    {% if "score" in st and "max_score" in st %}
        <span class="score">
            ({{ st["score"]|format_decimal }}
             / {{ st["max_score"]|format_decimal }})
        </span>
    {% else %}
        <span class="score">
            ({% trans %}N/A{% endtrans %})
        </span>
    {% endif %}
    </div>
    <div class="subtask-body">
        <table class="testcase-list">
            <thead>
                <tr>
                    <th class="idx">
                        {% trans %}#{% endtrans %}
                    </th>
                    <th class="outcome">
                        {% trans %}Outcome{% endtrans %}
                    </th>
                    <th class="details">
                        {% trans %}Details{% endtrans %}
                    </th>
    {% if feedback_level == FEEDBACK_LEVEL_FULL %}
                    <th class="execution-time">
                        {% trans %}Execution time{% endtrans %}
                    </th>
                    <th class="memory-used">
                        {% trans %}Memory used{% endtrans %}
                    </th>
    {% endif %}
                </tr>
            </thead>
            <tbody>
    {% for tc in st["testcases"] %}
        {% set show_tc = "outcome" in tc
               and ((feedback_level == FEEDBACK_LEVEL_FULL)
               or (feedback_level == FEEDBACK_LEVEL_RESTRICTED
               and tc["show_in_restricted_feedback"])
               or (feedback_level == FEEDBACK_LEVEL_OI_RESTRICTED
               and tc["show_in_oi_restricted_feedback"])) %}
        {% if show_tc %}
            {% if tc["outcome"] == "Correct" %}
                <tr class="correct">
            {% elif tc["outcome"] == "Not correct" %}
                <tr class="notcorrect">
            {% else %}
                <tr class="partiallycorrect">
            {% endif %}
                    <td class="idx">{{ loop.index }}</td>
                    <td class="outcome">{{ _(tc["outcome"]) }}</td>
                    <td class="details">
                      {{ tc["text"]|format_status_text }}
                    </td>
            {% if feedback_level == FEEDBACK_LEVEL_FULL %}
                    <td class="execution-time">
                {% if "time_limit_was_exceeded" in tc and tc["time_limit_was_exceeded"] %}
                        &gt; {{ tc["time_limit"]|format_duration }}
                {% elif "time" in tc and tc["time"] is not none %}
                        {{ tc["time"]|format_duration }}
                {% else %}
                        {% trans %}N/A{% endtrans %}
                {% endif %}
                    </td>
                    <td class="memory-used">
                {% if "memory" in tc and tc["memory"] is not none %}
                        {{ tc["memory"]|format_size }}
                {% else %}
                        {% trans %}N/A{% endtrans %}
                {% endif %}
                    </td>
            {% endif %}
                </tr>
        {% else %}
            {% if feedback_level != FEEDBACK_LEVEL_OI_RESTRICTED %}
                <tr class="undefined">
                    <td class="idx">{{ loop.index }}</td>
                {% if feedback_level == FEEDBACK_LEVEL_FULL %}
                    <td colspan="4">
                {% else %}
                    <td colspan="2">
                {% endif %}
                        {% trans %}N/A{% endtrans %}
                    </td>
                </tr>
            {% endif %}
        {% endif %}
    {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endfor %}"""

    def get_max_score(self, group_parameter: ScoreTypeGroupParameters) -> float:
        if isinstance(group_parameter, tuple) or isinstance(group_parameter, list):
            score = group_parameter[0]
        else:
            score = group_parameter["max_score"]
        assert (
            round(
                score,
                self.score_precision
            ) == score
        ), (f"The max score for a subtask"
            "has more precision than the task allows.")
        return score

    def get_testcases(self, group_parameter: ScoreTypeGroupParameters) -> int | str | list[str]:
        if isinstance(group_parameter, tuple) or isinstance(group_parameter, list):
            return group_parameter[1]
        else:
            return group_parameter["testcases"]

    def get_always_show_testcases(self, group_parameter: ScoreTypeGroupParameters) -> bool:
        if isinstance(group_parameter, tuple) or isinstance(group_parameter, list):
            return False
        else:
            return group_parameter.get("always_show_testcases", False)

    def retrieve_target_testcases(self) -> list[list[str]]:
        """Return the list of the target testcases for each subtask.

        Each element of the list consist of multiple strings.
        Each string represents the testcase name which should be included
        to the corresponding subtask.
        The order of the list is the same as 'parameters'.

        return: the list of the target testcases for each task.

        """

        t_params = [self.get_testcases(p) for p in self.parameters]

        if all(isinstance(t, int) for t in t_params):

            # XXX Lexicographical order by codename
            indices = sorted(self.public_testcases.keys())
            current = 0
            targets = []

            for t in t_params:
                # this assert is guaranteed by the `if` check, but the type checker is dumb...
                assert isinstance(t, int)
                next_ = current + t
                targets.append(indices[current:next_])
                current = next_

            return targets

        elif all(isinstance(t, str) for t in t_params):

            indices = sorted(self.public_testcases.keys())
            targets = []

            for t in t_params:
                assert isinstance(t, str)
                regexp = re.compile(t)
                target = [tc for tc in indices if regexp.match(tc)]
                if not target:
                    raise ValueError(
                        "No testcase matches against the regexp '%s'" % t)
                targets.append(target)

            return targets

        elif all(isinstance(t, list) for t in t_params) and all(all(isinstance(t, str) for t in s) for s in t_params):
            return t_params

        raise ValueError(
            "In the score type parameters, all values of 'testcases' "
            "must have the same type (int, unicode or list of strings)")

    def max_scores(self):
        """See ScoreType.max_score."""
        score = 0.0
        public_score = 0.0
        headers = list()

        targets = self.retrieve_target_testcases()

        for st_idx, parameter in enumerate(self.parameters):
            target = targets[st_idx]
            score += self.get_max_score(parameter)
            if all(self.public_testcases[tc_idx] for tc_idx in target):
                public_score += self.get_max_score(parameter)
            headers += ["Subtask %d (%g)" % (st_idx, self.get_max_score(parameter))]

        return score, public_score, headers

    def compute_score(self, submission_result):
        """See ScoreType.compute_score."""
        # Actually, this means it didn't even compile!
        if not submission_result.evaluated():
            return 0.0, [], 0.0, [], ["%lg" % 0.0 for _ in self.parameters]

        score = 0
        subtasks = []
        public_score = 0
        public_subtasks = []
        ranking_details = []

        targets = self.retrieve_target_testcases()
        evaluations = {ev.codename: ev for ev in submission_result.evaluations}

        score_precision = submission_result.submission.task.score_precision

        for st_idx, parameter in enumerate(self.parameters):
            target = targets[st_idx]

            testcases = []
            public_testcases = []
            # In "Restricted" feedback mode:
            #   show until the first testcase with a lowest score
            # In "OI Restricted" feedback mode:
            #   show only the first testcase with a lowest score

            tc_first_lowest_idx = None
            tc_first_lowest_score = None
            for tc_idx in target:
                tc_score = float(evaluations[tc_idx].outcome)
                tc_outcome = self.get_public_outcome(
                    tc_score, parameter)

                time_limit_was_exceeded = False
                if evaluations[tc_idx].text == [EVALUATION_MESSAGES.get("timeout").message]:
                    time_limit_was_exceeded = True

                testcases.append({
                    "idx": tc_idx,
                    "outcome": tc_outcome,
                    "text": evaluations[tc_idx].text,
                    "time": evaluations[tc_idx].execution_time,
                    "time_limit": evaluations[tc_idx].dataset.time_limit,
                    "time_limit_was_exceeded": time_limit_was_exceeded,
                    "memory": evaluations[tc_idx].execution_memory,
                    "show_in_restricted_feedback": self.public_testcases[tc_idx],
                    "show_in_oi_restricted_feedback": self.public_testcases[tc_idx]})

                if self.public_testcases[tc_idx]:
                    public_testcases.append(testcases[-1])
                    if tc_first_lowest_score is None or \
                            tc_score < tc_first_lowest_score:
                        tc_first_lowest_idx = tc_idx
                        tc_first_lowest_score = tc_score
                else:
                    public_testcases.append({"idx": tc_idx})

            st_score_fraction = self.reduce(
                [float(evaluations[tc_idx].outcome) for tc_idx in target],
                parameter)
            st_score = st_score_fraction * self.get_max_score(parameter)
            rounded_score = round(st_score, score_precision)

            if tc_first_lowest_idx is not None and st_score_fraction < 1.0 and not self.get_always_show_testcases(parameter):
                for tc in testcases:
                    if not self.public_testcases[tc["idx"]]:
                        continue
                    tc["show_in_restricted_feedback"] = (
                        tc["idx"] <= tc_first_lowest_idx)
                    tc["show_in_oi_restricted_feedback"] = (
                        tc["idx"] == tc_first_lowest_idx)

            score += rounded_score
            subtasks.append({
                "idx": st_idx,
                # We store the fraction so that an "example" testcase
                # with a max score of zero is still properly rendered as
                # correct or incorrect.
                "score_fraction": st_score_fraction,
                # But we also want the properly rounded score for display.
                "score": rounded_score,
                "max_score": self.get_max_score(parameter),
                "testcases": testcases})
            if all(self.public_testcases[tc_idx] for tc_idx in target):
                public_score += rounded_score
                public_subtasks.append(subtasks[-1])
            else:
                public_subtasks.append({"idx": st_idx,
                                        "testcases": public_testcases})
            ranking_details.append("%g" % rounded_score)

        # The following line should be unnecessary since subtask scores
        # are rounded. However we are using floats not Decimals
        # and this can cause errors. So we round again to be sure.
        score = round(score, score_precision)

        return score, subtasks, public_score, public_subtasks, ranking_details

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
    FAILED = "failed"
    OKAY = "okay"
    AMBIG = "ambiguous"
    IGN = "ignored"
    IMPOSSIBLE_EXPECTATIONS = "N.B.: The expectations for this group " \
                              "cannot be satisfied (expected failure due " \
                              "to time or memory constraints, but at the " \
                              "same time expected a positive score)."
    NEGATIVE_SCORE_EXPECTED = "N.B.: You expected a negative score for " \
                              "this group---why?"

    def compute_group_verdict(
        self,
        expected: list[str | tuple[float, float]],
        testcase_results: list[list[str]],
        scores: list[float],
        parameter: ScoreTypeGroupParametersDict,
    ):
        """Determine the verdict and a reason for a single group of a unit test.

        expected: the expectations declared for this group
        testcase_results: the results obtained for each of the group's testcases.
        scores: the score for each testcase.

        """
        results = set(reason for r in testcase_results for reason in r)
        meaningful_scores = [
            score
            for r, score in zip(testcase_results, scores)
            if UnitTest.meaningful_score(r)
        ]

        # check score
        score_expectations = UnitTest.get_intervals(expected) or [(1.0, 1.0)]
        score_verdict: ScoreVerdict
        if meaningful_scores:
            subtask_score = self.reduce(meaningful_scores, parameter)
            score_verdict = UnitTest.judge_score(subtask_score, score_expectations)
        else:
            score_verdict = ScoreVerdict.OK

        missing: list[str] = []

        # judge this group
        if "arbitrary" in expected:
            res = (1337, ScoreTypeGroup.IGN, ScoreTypeGroup.GRP_IGNORED)

        # check time and memory
        elif any(x not in expected for x in results if not UnitTest.ignore(x)):
            res = (-1, ScoreTypeGroup.FAILED, ScoreTypeGroup.GRP_TOO_LOW)

        elif score_verdict == ScoreVerdict.TOO_LOW:
            res = (-1, ScoreTypeGroup.FAILED, ScoreTypeGroup.GRP_TOO_LOW)

        # no "time" or "memory" verdict, maybe "time?" or "memory?"?
        elif any(x.endswith("?") and x[:-1] not in expected for x in results):
            res = (0, ScoreTypeGroup.AMBIG, ScoreTypeGroup.GRP_AMBIGUOUS)

        # time and memory limits okay---but is this a bad thing?
        elif ("time" in expected or "memory" in expected) and (
            "time" not in results and "memory" not in results
        ):
            res = (-1, ScoreTypeGroup.FAILED, ScoreTypeGroup.GRP_TOO_HIGH)
            missing = (["time"] if "time" in expected else []) + (
                ["memory"] if "memory" in expected else []
            )

        elif score_verdict == ScoreVerdict.OK:
            res = (1, ScoreTypeGroup.OKAY, ScoreTypeGroup.GRP_OKAY)

        else:
            res = (-1, ScoreTypeGroup.FAILED, ScoreTypeGroup.GRP_TOO_HIGH)

        status, short, desc = res

        # sanity checks
        zero_verdict = UnitTest.judge_score(0.0, score_expectations)
        if zero_verdict == ScoreVerdict.TOO_HIGH and "arbitrary" not in expected:
            desc += "\n\n" + ScoreTypeGroup.NEGATIVE_SCORE_EXPECTED

        if (
            zero_verdict == ScoreVerdict.TOO_LOW
            and ("time" in expected or "memory" in expected)
            and "arbitrary" not in expected
        ):
            desc += "\n\n" + ScoreTypeGroup.IMPOSSIBLE_EXPECTATIONS

        return (status, short, desc), missing

    def compute_unit_test_score(
        self, submission_result: SubmissionResult, _submission_info: str | None
    ):
        """Compute the score of a unit test.

        Format of the returned details:
            unit_test: True/False
            subtasks:
                name: name of the subtask
                verdict: (42, "", "")
                max_runtime: 0.412
                max_memory: 33659290                      in bytes
                cases:
                    line: (,)                             case_line()
                    grader: (42, "No expl. exp.")         grader response
                    time: 0.412
                    memory: 33659290                      in bytes

        """
        if _submission_info is None:
            return {
                "unit_test": True,  # should this be False?
                "verdict": (-1, "Not a Unit Test"),
            }
        if any(not isinstance(subtask, dict) for subtask in self.parameters):
            return {
                "unit_test": False,
                "verdict": (-1, "Unit Tests not available for this ScoreType"),
            }

        submission_info: dict = json.loads(_submission_info)
        expectations: dict[tuple, list[str | tuple[float, float]]] = {
            tuple(json.loads(key)): val
            for key, val in submission_info["expected"].items()
        }

        useful: set[str] = set()
        essential: set[str] = set()
        cases_by_subtask = self.retrieve_target_testcases()
        all_cases = {c for s in cases_by_subtask for c in s}
        dominated = {d: {c for c in all_cases if c != d} for d in all_cases}

        # Actually, this means it didn't even compile
        if not submission_result.evaluated():
            subtasks = []
        else:
            evaluations = dict((ev.codename, ev)
                            for ev in submission_result.evaluations)

            subtasks = []

            for _subtask, testcases in zip(self.parameters, cases_by_subtask):
                subtask = cast(ScoreTypeGroupParametersDict, _subtask)
                subtasks.append(
                    {"name": subtask["name"], "cases": [], "verdict": (42, "", "")}
                )

                expected = expectations[tuple(subtask["key"])]
                scores: list[float] = []
                cases: list[str] = []
                results: list[list[str]] = []

                for tc in testcases:
                    ev = evaluations[tc] # TODO: adjust this if we want to support multiscoring
                    r = UnitTest.get_result(submission_info["limits"], ev)
                    this_score = float(ev.outcome)
                    scores.append(this_score)
                    cases.append(tc)
                    results.append(r)

                subtasks[-1]["verdict"], missing = self.compute_group_verdict(
                    expected, results, scores, subtask
                )

                for tc in testcases:
                    ev = evaluations[tc] # TODO: adjust this if we want to support multiscoring
                    r = UnitTest.get_result(submission_info["limits"], ev)
                    line = self.case_line(r, expected, missing)
                    grader_text = format_status_text((ev.text)).strip()

                    subtasks[-1]["cases"].append(
                        {
                            "line": line,
                            "grader": grader_text,
                            "time": ev.execution_time,
                            "memory": ev.execution_memory,
                            "codename": tc,
                        }
                    )

                subtasks[-1]["max_runtime"] = \
                    max((c["time"] for c in subtasks[-1]["cases"]),
                        default=None)
                subtasks[-1]["max_memory"] = \
                    max((c["memory"] for c in subtasks[-1]["cases"]),
                        default=None)

                """
                Check testcase utility
                """
                if subtask["max_score"] == 0:  # used to be subtask["sample"]
                    continue

                for i, tc in enumerate(testcases):
                    if self.essential_testcase(scores, i, subtask):
                        essential.add(tc)
                    elif not self.weak_testcase(scores, i, subtask):
                        useful.add(tc)
                    dominated[tc] &= \
                        {cases[j] for j in self.dominated_by(scores, i, subtask)}

        prec = self.score_precision
        total_score = self.compute_score(submission_result)[0]
        expected_score: tuple[float, float] = submission_info["expected_score"]
        score_okay = (
            round(expected_score[0], prec)
            <= total_score
            <= round(expected_score[1], prec)
        )
        okay = score_okay and not any(s["verdict"][0] <= 0 for s in subtasks)

        return {
            "unit_test": True,
            "unit_test_name": submission_result.submission.comment,
            "subtasks": subtasks,
            "verdict": (1, ScoreTypeGroup.OKAY) if okay \
                       else (0, ScoreTypeGroup.FAILED),
            "score_okay": score_okay,
            "score": total_score,
            "expected_score": submission_info["expected_score_info"],

            "dominated": {d: list(u) for d, u in dominated.items()},
            "essential": list(essential),
            "useful": list(useful)
        }

    def case_line(
        self,
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
            for i in range(0, len(line)):
                line[i] = (line[i][0], 0)

        return line

    def essential_testcase(
        self, scores: list[float], idx: int, parameter: ScoreTypeGroupParametersDict
    ):
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

        score_inc = self.reduce(scores, parameter)
        score_exc = self.reduce(scores[:idx] + scores[idx + 1:], parameter)
        return score_inc + ScoreTypeGroup.THRESHOLD_STRICT < score_exc

    def weak_testcase(
        self, scores: list[float], idx: int, parameter: ScoreTypeGroupParametersDict
    ):
        """
        Helper method for testcase utility that decides whether a testcase
        is a "weak" for a given group and submission, meaning whether it
        is useless if our goal is to enforce that the given unit test
        satisfies the expectations for the current group.

        How one should precisely define "weak" and "useless" heavily
        depends on the behavior of the score type and you might want to
        override this method in a custom subclass. Here we use the heuristic
        that a testcase is weak if the submission succeeds on it, or if
        it is not essential and if using only this testcase and all
        testcases with higher score would yield a considerably higher score
        for this group. This heuristic works best when the "reduce" function
        is idempotent (meaning duplicating entries of scores does not
        change the result) or if the only scores are 0.0 and 1.0.

        scores (list): the scores of all testcases in this group on a
            given submission
        idx (int): the index of the testcase in question in the scores
            parameter
        parameter (list): the parameters of the current subtask
        """
        if self.essential_testcase(scores, idx, parameter):
            return False

        if scores[idx] > 1 - ScoreTypeGroup.THRESHOLD_LAX:
            return True

        better = [x for x in scores if x >= scores[idx]]
        score_exc = self.reduce(better, parameter)
        score_inc = self.reduce(scores, parameter)

        return score_exc > score_inc + ScoreTypeGroup.THRESHOLD_LAX

    def dominated_by(
        self, scores: list[float], idx: int, parameter: ScoreTypeGroupParametersDict
    ):
        """
        Helper method for testcase utility that determines for a given testcase
        x all cases y in the current group such that x is (not necessarily
        strictly) weaker than y
        """
        return [i for i, s in enumerate(scores)
                  if s < scores[idx] + ScoreTypeGroup.THRESHOLD_VERY_STRICT]

    @abstractmethod
    def get_public_outcome(self, outcome: float, parameter: ScoreTypeGroupParameters) -> str:
        """Return a public outcome from an outcome.

        The public outcome is shown to the user, and this method
        return the public outcome associated to the outcome of a
        submission in a testcase contained in the group identified by
        parameter.

        outcome: the outcome of the submission in the testcase.
        parameter: the parameters of the current group.

        return: the public output.

        """
        pass

    @abstractmethod
    def reduce(self, outcomes: list[float], parameter: ScoreTypeGroupParameters) -> float:
        """Return the score of a subtask given the outcomes.

        outcomes: the outcomes of the submission in
            the testcases of the group.
        parameter: the parameters of the group.

        return: the public output.

        """
        pass
