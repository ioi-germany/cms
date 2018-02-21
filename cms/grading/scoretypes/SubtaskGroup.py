#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2015 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2013-2017 Tobias Lenz <t_lenz94@web.de>
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

from cms.grading.ScoreType import ScoreType
from cms.grading import UnitTest, format_status_text

import json
import logging

from six import iteritems

logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class SubtaskGroup(ScoreType):
    """The testcases are divided into subtasks, which themselves consist of
    groups. The score of a group is the minimum score among the contained
    test cases multiplied with a parameter of the group. The score of a subtask
    is the sum of the scores of the contained groups. The public score does not
    count towards the real score.

    """
    # Mark strings for localization.
    N_("Group")
    N_("Outcome")
    N_("Details")
    N_("Execution time")
    N_("Memory used")
    N_("N/A")
    TEMPLATE = """\
{% from cms.grading import format_status_text %}
{% from cms.server import format_size %}
{% if not details["unit_test"] %}{# Normal submission #}
{% for st in details["subtasks"] %}
    {% if "score" in st and "max_score" in st %}
        {% if st["score"] >= st["max_score"] %}
<div class="subtask correct">
        {% elif st["score"] <= 0.0 %}
<div class="subtask notcorrect">
        {% else %}
<div class="subtask partiallycorrect">
        {% end %}
    <div class="subtask-head">
        <span class="title" style="margin-top:-2px;">
            {{ st["name"] }}
        </span>
        <span class="score">
            {% if st["public"] and not st["for_public_score"] %}
                {% if st["score"] >= st["max_score"] %}
                    OKAY
                {% elif st["score"] <= 0.0 %}
                    FAILED
                {% else %}
                    PARTIALLY
                {% end %}
            {% else %}
                {{ '%g' % round(st["score"], 2) }} / {{ st["max_score"] }}
            {% end %}
        </span>
    </div>
    <div class="subtask-body">
        <table class="testcase-list">
            <thead>
                <tr>
                    <th>{{ _("Outcome") }}</th>
                    <th>{{ _("Details") }}</th>
                    <th>{{ _("Execution time") }}</th>
                    <th>{{ _("Memory used") }}</th>
                    <th>{{ _("Group") }}</th>
                </tr>
            </thead>
            <tbody>
        {% for tc in st["testcases"] %}
            {% if "outcome" in tc and "text" in tc %}
                {% if tc["outcome"] == "Correct" %}
                <tr class="correct">
                {% elif tc["outcome"] == "Not correct" %}
                <tr class="notcorrect">
                {% else %}
                <tr class="partiallycorrect">
                {% end %}
                    <td>{{ _(tc["outcome"]) }}</td>
                    <td>{{ format_status_text(tc["text"], _) }}</td>
                    <td>
                {% if "time" in tc and tc["time"] is not None %}
                        {{ "%(seconds)0.3f s" % {'seconds': tc["time"]} }}
                {% else %}
                        {{ _("N/A") }}
                {% end %}
                    </td>
                    <td>
                {% if "memory" in tc and tc["memory"] is not None %}
                        {{ format_size(tc["memory"]) }}
                {% else %}
                        {{ _("N/A") }}
                {% end %}
                    </td>
                {% if "grouplen" in tc %}
                    <td rowspan="{{ tc["grouplen"] }}">{{ tc["groupnr"] }}</td>
                {% end %}
            {% else %}
                <tr class="undefined">
                    <td colspan="5">
                        {{ _("N/A") }}
                    </td>
                </tr>
            {% end %}
        {% end %}
            </tbody>
        </table>
    </div>
</div>
    {% end %}
{% end %}
{% else %}{# Unit test #}
{% if "public_score_okay" in details %}
{% if details["public_score_okay"] == True %}
    <div class="subtask correct">
        <div class="subtask-head">
            <span class="title" style="margin-top:-2px">
                Public score
            </span>
            <span class="score">
                OKAY
            </span>
        </div>
        <div class="subtask-body">
            <table class="table table-bordered table-striped">
                <tr>
                <td>
                    Expected: {{details["wanted_public"]}}
                </td>
                <td>
                    Got: {{details["public"]}}
                </td>
                </tr>
            </table>
        </div>
    </div>
{% elif details["public_score_okay"] == False %}
    <div class="subtask notcorrect">
        <div class="subtask-head">
            <span class="title" style="margin-top:-2px">
                Public score
            </span>
            <span class="score">
                FAILED
            </span>
        </div>
        <div class="subtask-body">
            <table class="table table-bordered table-striped">
                <tr>
                <td>
                    Expected: {{details["wanted_public"]}}
                </td>
                <td>
                    Got: {{details["public"]}}
                </td>
                </tr>
            </table>
        </div>
    </div>
{% else %}
    <div class="subtask correct">
        <div class="subtask-head">
            <span class="title" style="margin-top:-2px">
                Public score
            </span>
            <span class="score">
                ———
            </span>
        </div>
        <div class="subtask-body">
            <table class="table table-bordered table-striped">
                <tr><td>
                    This is a full feedback task, hence there is no
                    such thing as a public score.
                </td></tr>
            </table>
        </div>
    </div>
{% end %}
{% if details["private_score_okay"] %}
    <div class="subtask correct">
        <div class="subtask-head">
            <span class="title" style="margin-top:-2px">
                Total score
            </span>
            <span class="score">
                OKAY
            </span>
        </div>
        <div class="subtask-body">
            <table class="table table-bordered table-striped">
                <tr>
                <td>
                    Expected: {{details["wanted_private"]}}
                </td>
                <td>
                    Got: {{details["private"]}}
                </td>
                </tr>
            </table>
        </div>
    </div>
{% else %}
    <div class="subtask notcorrect">
        <div class="subtask-head">
            <span class="title" style="margin-top:-2px">
                Total score
            </span>
            <span class="score">
                FAILED
            </span>
        </div>
        <div class="subtask-body">
            <table class="table table-bordered table-striped">
                <tr>
                <td>
                    Expected: {{details["wanted_private"]}}
                </td>
                <td>
                    Got: {{details["private"]}}
                </td>
                </tr>
            </table>
        </div>
    </div>
{% end %}
<br><br>
{% end %}

{% for st in details["subtasks"] %}
    {% if st["status"][0] == 1337%}
<div class="subtask partiallycorrect">
    {% elif st["status"][0] > 0 %}
<div class="subtask correct">
    {% else %}
<div class="subtask notcorrect">
    {% end %}
    <div class="subtask-head">
        <span class="title" style="margin-top:-2px;">
            {{ st["name"] }}
        </span>
        <span class="score">
            {{st["status"][1]}}
        </span>
    </div>
    <div class="subtask-body">
        <table class="table table-bordered table-striped">
            <col class="short">
            <col class="short">
            <col class="short">
            <col style="width:44%;">
            <col style="width:44%;">
            <thead>
                <tr>
                    <th class="short">{{ _("T") }}</th>
                    <th class="short">{{ _("M") }}</th>
                    <th class="short">{{ _("A") }}</th>
                    <th>{{ _("Testcase verdict") }}</th>
                    <th>{{ _("Group verdict") }}</th>
                </tr>
            </thead>
            <tbody>
    {% for i, g in enumerate(st["groups"]) %}
        {% set first = True %}
        {% for c in g["cases"] %}
                <tr>
                    <td class="{{"unit_test_ok" if c["line"][0][1] > 0 else \
                                 "unit_test_failed" if c["line"][0][1] < 0 \
                                 else ""}} short" style="cursor:default;"
                     title="{{ "%(seconds)0.3f s" % {'seconds': c["time"]} }}">
                        {{c["line"][0][0]}}
                    </td>
                    <td class="{{"unit_test_ok" if c["line"][1][1] > 0 else \
                                 "unit_test_failed" if c["line"][1][1] < 0 \
                                 else ""}} short" style="cursor:default;"
                     title="{{ format_size(c["memory"]) }}">
                        {{c["line"][1][0]}}
                    </td>
                    <td class="{{"unit_test_ok" if c["line"][2][1] > 0 else \
                                 "unit_test_failed" if c["line"][2][1] < 0 \
                                 else ""}} short">
                        {{c["line"][2][0]}}
                    </td>
                    <td class="{{"no_expectations" \
                                 if c["verdict"][0] == 42 else \
                                 "unit_test_ok" if c["verdict"][0] > 0 else \
                                 "unit_test_failed"}}">

            {% set x = c["verdict"][1].split(chr(10)) %}
            {% for i,t in enumerate(x) %}
                        {{t}}
                {% if i < len(x) - 1 %}
                        <br>
                {% end %}
            {% end %}
                    </td>
            {% if first %}
                    <td rowspan={{len(g["cases"])}}
                     class="{{"unit_test_mid" if g["verdict"][0] == 1337 else \
                              "unit_test_ok" if g["verdict"][0] > 0 else \
                              "unit_test_failed"}}">

                {% set x = g["verdict"][1].split(chr(10)) %}
                {% for i,t in enumerate(x) %}
                        {{t}}
                    {% if i < len(x) - 1 %}
                        <br>
                    {% end %}
                {% end %}
                    </td>
            {% end %}
            {% set first = False %}
                </tr>
        {% end %}
    {% end %}
            </tbody>
        </table>
    </div>
</div>
{% end %}
{% end %}
"""

    def feedback(self):
        return self.parameters["feedback"]

    def unit_test_expected_scores(self, submission_info):
        submission_info = json.loads(submission_info)

        public = submission_info.get("expected_public_score", 0)
        private = submission_info.get("expected_score", 0)

        if self.feedback() == "partial":
            public = submission_info.get("expected_partial_score", 0)

        return public, private

    def unit_test_expected_scores_info(self, submission_info):
        submission_info = json.loads(submission_info)

        public = submission_info.get("expected_public_score_info", 0)
        private = submission_info.get("expected_score_info", 0)

        if self.feedback() == "partial":
            public = submission_info.get("expected_partial_score_info", 0)

        return public, private

    def max_scores(self):
        """Compute the maximum score of a submission.

        See the same method in ScoreType for details.

        """
        private_score = 0.0
        public_score = 0.0
        headers = list()

        for subtask in self.parameters["tcinfo"]:
            st_score = 0
            for group in subtask["groups"]:
                st_score += group["points"]
            if subtask["for_public_score"]:
                public_score += st_score
            if subtask["for_private_score"]:
                private_score += st_score
            headers += ["%s (%g)" % (subtask["name"], st_score)]

        return private_score, public_score, headers

    def _compute_score(self, submission_result, public):
        """Compute the score of a normal submission.

        See the same method in ScoreType for details.

        """
        # Actually, this means it didn't even compile!
        if not submission_result.evaluated():
            if public:
                return 0.0, json.dumps({"unit_test": False, "subtasks": []})
            else:
                return 0.0, json.dumps({"unit_test": False, "subtasks": []}), \
                    ["%lg" % 0.0 for _ in self.parameters["tcinfo"]]

        evaluations = dict((ev.codename, ev)
                           for ev in submission_result.evaluations)
        subtasks = []
        score = 0
        if not public:
            ranking_details = []

        for subtask in self.parameters["tcinfo"]:
            if subtask["public"] or not public:  # Shakespeare has been here
                st_score = 0
                st_maxscore = 0
                testcases = []
                for groupnr, group in enumerate(subtask["groups"]):
                    outcomes = [float(evaluations[idx].outcome)
                                for idx in group["cases"]]
                    gr_score = min(outcomes) * group["points"]
                    st_score += gr_score
                    st_maxscore += group["points"]

                    first = True
                    for idx in group["cases"]:
                        oc = self.get_public_outcome(
                            float(evaluations[idx].outcome))
                        tc = {"outcome": oc,
                              "text": evaluations[idx].text,
                              "time": evaluations[idx].execution_time,
                              "memory": evaluations[idx].execution_memory,
                              }
                        if first:
                            first = False
                            tc["groupnr"] = groupnr + 1
                            tc["grouplen"] = len(group["cases"])

                        testcases.append(tc)
                if (public and subtask["for_public_score"]) or \
                   (not public and subtask["for_private_score"]):
                    score += st_score
                subtasks.append({
                    "public": subtask["public"],  # TODO depends on public?
                    "for_public_score": subtask["for_public_score"],
                    "for_private_score": subtask["for_private_score"],
                    "name": subtask["name"],
                    "score": st_score,
                    "max_score": st_maxscore,
                    "testcases": testcases,
                })
                if not public:
                    ranking_details.append("%lg" % round(st_score, 2))
            else:
                subtasks.append({
                    "name": subtask["name"],
                    "testcases": [],
                })

        details = {"unit_test": False, "subtasks": subtasks}

        if public:
            return score, json.dumps(details)
        else:
            return score, json.dumps(details), ranking_details

    def compute_score(self, submission_result):
        """Compute the score of a normal submission.

        See the same method in ScoreType for details.

        """
        public_score, public_score_details = \
            self._compute_score(submission_result, True)
        score, score_details, ranking_score_details = \
            self._compute_score(submission_result, False)
        return score, score_details, \
            public_score, public_score_details, \
            ranking_score_details

    def compute_unit_test_score(self, submission_result,
                                submission_info):
        """Compute the score of a unit test.

        Format of the returned details:
            unit_test: True/False
            subtasks:
                name: name of the subtask
                status: (0, "okay")
                groups:
                    verdict: (42, "")
                    cases:
                        line: (,)                             case_line()
                        verdict: (42, "No expl. exp.")        judge_case()
                                                        if len(mandatory) != 0
                        time: 0.412
                        memory: 33659290                      in bytes

        """
        if submission_info is None:
            return json.dumps({"unit_test": True,
                               "verdict": (-1, "Not a Unit Test")})

        wanted_public, wanted_private = \
            self.unit_test_expected_scores(submission_info)
        wanted_public_info, wanted_private_info = \
            self.unit_test_expected_scores_info(submission_info)

        submission_info = json.loads(submission_info)

        # Actually, this means it didn't even compile!
        if not submission_result.evaluated():
            return json.dumps({"unit_test": True, 'subtasks': [],
                               'verdict': (-1, "Compilation failed")})

        evaluations = dict((ev.codename, ev)
                           for ev in submission_result.evaluations)
        subtasks = []
        public_score = 0
        private_score = 0

        expectations = {tuple(json.loads(key)): val for key, val
                        in iteritems(submission_info["expected"])}
        case_expectations = submission_info["expected_case"]
        possible_task = expectations[()]
        subtasks_failed = False

        for subtask in self.parameters["tcinfo"]:
            subtasks.append({"name": subtask["name"], "groups": []})

            # There are no expectations for partial feedback subtasks
            if subtask["partial"]:
                possible_subtask = []
            else:
                possible_subtask = expectations[tuple(subtask["key"])]

            group_score = 0

            worst_group = (1, "okay")
            group_status = []

            for i, g in enumerate(subtask["groups"]):
                # There are no expectations for partial feedback subtasks
                if subtask["partial"]:
                    possible_group = []
                else:
                    possible_group = expectations[tuple(g["key"])]

                possible = possible_task + possible_subtask + possible_group

                subtasks[-1]["groups"].append({"verdict": (42, ""),
                                               "cases": []})
                min_f = 1.0  # Minimum "score" of a test case in this group

                cases_failed = False

                # List of all results of all test cases in this group
                case_results = []
                extended_results = []

                for idx in g["cases"]:
                    r = UnitTest.get_result(submission_info["limits"],
                                            evaluations[idx])
                    min_f = min(min_f, float(evaluations[idx].outcome))

                    mandatory = case_expectations[idx]

                    l = UnitTest.case_line(r, mandatory, possible)
                    v = (42, "No case-specific expectations.")

                    # Test case expectations
                    if len(mandatory) != 0:
                        accepted, desc = v = \
                            UnitTest.judge_case(r, mandatory, possible)
                        if accepted <= 0:
                            cases_failed = True
                        extended_results += r
                        case_results += \
                            [x for x in r if not UnitTest.ignore(x, mandatory)
                             and x not in mandatory]
                    else:
                        case_results += r

                    v = (v[0],
                         v[1] + "\nGrader output: " +
                         format_status_text((evaluations[idx].text)).strip())

                    subtasks[-1]["groups"][-1]["cases"].\
                        append({"line": l, "verdict": v,
                                "time": evaluations[idx].execution_time,
                                "memory": evaluations[idx].execution_memory})

                group_score += min_f * g["points"]

                status, short, desc = \
                    UnitTest.judge_group(case_results, extended_results,
                                         possible, [])

                if cases_failed:
                    if status > 0:
                        desc = ""
                    else:
                        desc += "\n\n"

                    status = -1
                    desc += "At least one testcase did not behave as " \
                            "expected, cf. the \"test verdict\" column."
                    short = "failed"

                subtasks[-1]["groups"][-1]["verdict"] = (status, desc)
                worst_group = min(worst_group, (status, short))
                group_status.append(status)

            if subtask["for_public_score"]:
                public_score += group_score
            if subtask["for_private_score"]:
                private_score += group_score

            subtasks[-1]["status"] = (worst_group[0], worst_group[1].upper())

            if all(s == 1337 for s in group_status):
                subtasks[-1]["status"] = (1337, "IGNORED")
            elif subtasks[-1]["status"][0] > 0 and any(s == 1337
                                                       for s in group_status):
                    subtasks[-1]["status"] = (1337, "PARTIALLY IGNORED")

            if len(group_status) == 0:
                subtasks[-1]["status"] = (1337, "EMPTY")

            # we ignore partial feedback subtasks (except for the score)
            if subtask["partial"]:
                subtasks.pop()
            elif subtasks[-1]["status"][0] <= 0:
                subtasks_failed = True

        def is_in(x, l):
            return l[0] <= x <= l[1]

        private_score_okay = is_in(private_score, wanted_private)
        public_score_okay = is_in(public_score, wanted_public)

        details = {"unit_test": True, "subtasks": subtasks,
                   "private_score_okay": private_score_okay,
                   "public_score_okay": None if self.feedback() == "full"
                   else public_score_okay,
                   "public": public_score,
                   "wanted_public": wanted_public_info,
                   "private": private_score,
                   "wanted_private": wanted_private_info}

        okay = private_score_okay and \
            (public_score_okay or self.feedback() == "full") \
            and not subtasks_failed

        details["verdict"] = (1, "Okay") if okay else (0, "Failed")

        return json.dumps(details)

    def get_public_outcome(self, outcome):
        """Return a public outcome from an outcome.

        outcome (float): the outcome of the submission.

        return (float): the public output.

        """
        if outcome <= 0.0:
            return N_("Not correct")
        elif outcome >= 1.0:
            return N_("Correct")
        else:
            return N_("Partially correct")
