#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2015 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2013-2019 Tobias Lenz <t_lenz94@web.de>
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

from . import ScoreType
from cms.grading import format_status_text
from cms.grading.scoring import UnitTest

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
{% if not details["unit_test"] %}{# Normal submission #}
{% if details["evaluated"] %}
{% for st in details["subtasks"] %}
    {% with %}
        {% set show_full_feedback = (feedback_level == FEEDBACK_LEVEL_FULL or st["sample"]) %}
        {% if st["score"] >= st["max_score"] %}
<div class="subtask correct">
        {% elif st["score"] <= 0.0 %}
<div class="subtask notcorrect">
        {% else %}
<div class="subtask partiallycorrect">
        {% endif %}
    <div class="subtask-head">
        <span class="title" style="margin-top:-2px;">
            {{ st["name"] }}
        </span>
        <span class="score">
            {% if st["sample"] %}({% endif %}
            {{ st["score"]|round(2)|format_decimal }} / {{ st["max_score"]|format_decimal }}
            {% if st["sample"] %}){% endif %}
        </span>
    </div>
    <div class="subtask-body">
        <table class="testcase-list">
            <thead>
                <tr>
                    <th class="idx">{% trans %}Case{% endtrans %}</th>
                    <th class="outcome">{% trans %}Outcome{% endtrans %}</th>
                    <th class="details">{% trans %}Details{% endtrans %}</th>
        {% if show_full_feedback %}
                    <th class="execution-time">{% trans %}Execution time{% endtrans %}</th>
                    <th class="memory-used">{% trans %}Memory used{% endtrans %}</th>
        {% endif %}
                    <th class="group">{% trans %}Group{% endtrans %}</th>
                </tr>
            </thead>
            <tbody>
        {% for group in st["groups"] %}
            {% with %}
                {% set grouploop = loop %}
                {% if show_full_feedback %}
                    {% set shown_cases = group["testcases"] %}
                {% else %}
                    {% set shown_cases = group["first_worst_testcases"] %}
                {% endif %}
                {% for tc in shown_cases %}
                    {% if tc["outcome"] == "Correct" %}
                <tr class="correct">
                    {% elif tc["outcome"] == "Not correct" %}
                <tr class="notcorrect">
                    {% else %}
                <tr class="partiallycorrect">
                    {% endif %}
                    <td class="idx">{{ tc["number_in_group"] }}</td>
                    <td class="outcome">{{ _(tc["outcome"]) }}</td>
                    <td class="details">{{ tc["text"]|format_status_text }}</td>
                    {% if show_full_feedback %}
                    <td class="execution-time">
                        {% if tc["time"] is not none %}
                        {{ tc["time"]|format_duration }}
                        {% else %}
                        {% trans %}N/A{% endtrans %}
                        {% endif %}
                    </td>
                    <td class="memory-used">
                        {% if tc["memory"] is not none %}
                        {{ tc["memory"]|format_size }}
                        {% else %}
                        {% trans %}N/A{% endtrans %}
                        {% endif %}
                    </td>
                    {% endif %}
                    {% if loop.first %}
                    <td class="group" rowspan="{{ shown_cases|length }}">{{ grouploop.index }}</td>
                    {% endif %}
                </tr>
                {% endfor %}
                {% if shown_cases|length == 0 and not show_full_feedback %}
                <tr class="correct">
                    <td class="outcome" colspan="3">{% trans %}All correct{% endtrans %}</td>
                    <td class="group">{{ grouploop.index }}</td>
                </tr>
                {% endif %}
            {% endwith %}
        {% endfor %}
            </tbody>
        </table>
    </div>
</div>
    {% endwith %}
{% endfor %}
{% endif %}
{% else %}{# Unit test #}
<div class="subtask {% if details["sample_score_okay"] %}correct{% else %}notcorrect{% endif %}">
    <div class="subtask-head">
        <span class="title" style="margin-top:-2px">
            Sample score
        </span>
        <span class="score">
            {% if details["sample_score_okay"] %}OKAY{% else %}FAILED{% endif %}
        </span>
    </div>
    <div class="subtask-body">
        <table class="table table-bordered table-striped">
            <tr>
            <td>
                Expected: {{details["expected_sample_score"]}}
            </td>
            <td>
                Got: {{details["sample_score"]}}
            </td>
            </tr>
        </table>
    </div>
</div>
{% if details["partial_feedback_enabled"] %}
<div class="subtask {% if details["partial_feedback_score_okay"] %}correct{% else %}notcorrect{% endif %}">
    <div class="subtask-head">
        <span class="title" style="margin-top:-2px">
            Partial feedback score
        </span>
        <span class="score">
            {% if details["partial_feedback_score_okay"] %}OKAY{% else %}FAILED{% endif %}
        </span>
    </div>
    <div class="subtask-body">
        <table class="table table-bordered table-striped">
            <tr>
            <td>
                Expected: {{details["expected_partial_feedback_score"]}}
            </td>
            <td>
                Got: {{details["partial_feedback_score"]}}
            </td>
            </tr>
        </table>
    </div>
</div>
{% endif %}
<div class="subtask {% if details["final_score_okay"] %}correct{% else %}notcorrect{% endif %}">
    <div class="subtask-head">
        <span class="title" style="margin-top:-2px">
            Final score
        </span>
        <span class="score">
            {% if details["final_score_okay"] %}OKAY{% else %}FAILED{% endif %}
        </span>
    </div>
    <div class="subtask-body">
        <table class="table table-bordered table-striped">
            <tr>
            <td>
                Expected: {{details["expected_final_score"]}}
            </td>
            <td>
                Got: {{details["final_score"]}}
            </td>
            </tr>
        </table>
    </div>
</div>
<br><br>

{% for st in details["subtasks"] %}
    {% if st["status"][0] == 1337%}
<div class="subtask partiallycorrect">
    {% elif st["status"][0] > 0 %}
<div class="subtask correct">
    {% else %}
<div class="subtask notcorrect">
    {% endif %}
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
                    <th class="short">{% trans %}T{% endtrans %}</th>
                    <th class="short">{% trans %}M{% endtrans %}</th>
                    <th class="short">{% trans %}A{% endtrans %}</th>
                    <th>{% trans %}Testcase verdict{% endtrans %}</th>
                    <th>{% trans %}Group verdict{% endtrans %}</th>
                </tr>
            </thead>
            <tbody>
    {% for g in st["groups"] %}
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
                     title="{{ c["memory"]|format_size }}">
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

            {% set x = c["verdict"][1].split("\n") %}
            {% for t in x %}
                {% if not loop.first %}
                        <br>
                {% endif %}
                        {{t}}
            {% endfor %}
                    </td>
            {% if loop.first %}
                    <td rowspan={{g["cases"]|length}}
                     class="{{"unit_test_mid" if g["verdict"][0] == 1337 else \
                              "unit_test_ok" if g["verdict"][0] > 0 else \
                              "unit_test_failed"}}">

                {% set x = g["verdict"][1].split("\n") %}
                {% for t in x %}
                    {% if not loop.first %}
                        <br>
                    {% endif %}
                        {{t}}
                {% endfor %}
                    </td>
            {% endif %}
                </tr>
        {% endfor %}
    {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endfor %}
{% endif %}
"""

    def feedback(self):
        return self.parameters["feedback"]

    def max_scores(self):
        """Compute the maximum score of a submission.

        See the same method in ScoreType for details.

        """
        final_score = 0.0
        sample_score = 0.0
        headers = list()

        for subtask in self.parameters["subtasks"]:
            st_score = 0.0
            for group in subtask["groups"]:
                st_score += group["points"]
            if subtask["sample"]:
                sample_score += st_score
            else:
                final_score += st_score
                headers += ["%s (%g)" % (subtask["name"], st_score)]

        # TODO Also show sample subtasks and detailed feedback in RWS?

        private_score = final_score
        if self.parameters["feedback"] in ["full", "no", "token"]:
            public_score = sample_score
        elif self.parameters["feedback"] == "partial":
            public_score = final_score
        else:
            raise Exception("Unknown feedback type '{}'".format(
                self.parameters["feedback"]))

        return private_score, public_score, headers

    def score_column_headers(self):
        """Returns the headers of the two (public, private) score columns in
        the submissions list in CWS.

        return (string, string): public score header, private score header

        """
        if self.parameters["feedback"] in ["full", "no", "token"]:
            public_score_header = "Sample score"
        elif self.parameters["feedback"] == "partial":
            public_score_header = "Partial feedback score"
        else:
            raise Exception("Unknown feedback type '{}'".format(
                self.parameters["feedback"]))

        private_score_header = \
            "Tokened score" if self.parameters["feedback"] == "token" \
            else "Actual score"

        return public_score_header, private_score_header

    def _compute_score(self, submission_result, score_type):
        assert score_type in ["sample", "partial", "final"]

        evaluated = submission_result.evaluated()

        evaluations = dict((ev.codename, ev)
                           for ev in submission_result.evaluations)
        score = 0.0
        details_sts = []

        for subtask in self.parameters["subtasks"]:
            if score_type != "sample" or subtask["sample"]:
                st_max_score = 0.0
                st_score = 0.0
                details_grs = []
                for group in subtask["groups"]:
                    gr_max_score = group["points"]

                    used_cases = [
                        testcase
                        for testcase in group["testcases"]
                        if score_type == "final" \
                            or subtask["sample"] \
                            or testcase["in_partial_feedback"]
                        ]

                    if evaluated:
                        gr_relative_score = 1.0
                        first_worst_itc = None
                        for itc, testcase in enumerate(used_cases):
                            codename = testcase["codename"]
                            tc_relative_score = \
                                float(evaluations[codename].outcome)
                            if gr_relative_score > tc_relative_score:
                                gr_relative_score = tc_relative_score
                                first_worst_itc = itc
                        gr_score = gr_relative_score * gr_max_score
                    else:
                        gr_score = 0.0

                    st_max_score += gr_max_score
                    st_score += gr_score

                    if evaluated:
                        details_tcs = []
                        details_first_worst_tcs = []
                        for itc, testcase in enumerate(used_cases):
                            codename = testcase["codename"]
                            outcome = self.get_public_outcome(
                                float(evaluations[codename].outcome))
                            details_tc = {
                                "number_in_group": itc + 1,
                                "outcome": outcome,
                                "text": evaluations[codename].text,
                                "time": evaluations[codename].execution_time,
                                "memory": evaluations[codename].execution_memory,
                                }
                            details_tcs.append(details_tc)
                            if itc == first_worst_itc:
                                details_first_worst_tcs.append(details_tc)

                        details_gr = {
                            "score": gr_score,
                            "max_score": gr_max_score,
                            "testcases": details_tcs,
                            "first_worst_testcases": details_first_worst_tcs,
                            }
                        details_grs.append(details_gr)

                if score_type == "sample" or not subtask["sample"]:
                    score += st_score

                if score_type == "partial" and not subtask["sample"]:
                    name = subtask["name"] + " (partial feedback)"
                else:
                    name = subtask["name"]

                if evaluated:
                    details_sts.append({
                        "name": name,
                        "sample": subtask["sample"],
                        "score": st_score,
                        "max_score": st_max_score,
                        "groups": details_grs,
                        })
                else:
                    details_sts.append({
                        "name": name,
                        "sample": subtask["sample"],
                        "score": st_score,
                        "max_score": st_max_score,
                        })

        details = {
            "unit_test": False,
            # Whether compilation succeeded
            "evaluated": evaluated,
            "subtasks": details_sts,
            }

        return score, details

    def compute_score(self, submission_result):
        """Compute the score of a normal submission.

        See the same method in ScoreType for details.

        """
        if self.parameters["feedback"] in ["full", "no", "token"]:
            public_score, public_score_details = \
                self._compute_score(submission_result, "sample")
        elif self.parameters["feedback"] == "partial":
            public_score, public_score_details = \
                self._compute_score(submission_result, "partial")
        else:
            raise Exception("Unknown feedback type '{}'".format(
                self.parameters["feedback"]))

        score, score_details = \
            self._compute_score(submission_result, "final")

        ranking_score_details = [
            "%lg" % round(subtask["score"], 2)
            for subtask in score_details["subtasks"]
            if not subtask["sample"]
            ]

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
            return {"unit_test": True,
                    "verdict": (-1, "Not a Unit Test")}

        submission_info = json.loads(submission_info)

        expected_sample_score = submission_info["expected_sample_score"]
        expected_partial_feedback_score = submission_info["expected_partial_feedback_score"]
        expected_final_score = submission_info["expected_final_score"]
        expected_sample_score_info = submission_info["expected_sample_score_info"]
        expected_partial_feedback_score_info = submission_info["expected_partial_feedback_score_info"]
        expected_final_score_info = submission_info["expected_final_score_info"]

        expectations = {tuple(json.loads(key)): val for key, val
                        in iteritems(submission_info["expected"])}
        case_expectations = submission_info["expected_case"]
        possible_task = expectations[()]

        # Actually, this means it didn't even compile
        if not submission_result.evaluated():
            subtasks_failed = True
            subtasks = []
        else:
            evaluations = dict((ev.codename, ev)
                            for ev in submission_result.evaluations)

            subtasks = []
            subtasks_failed = False

            for subtask in self.parameters["subtasks"]:
                subtasks.append({
                    "name": subtask["name"],
                    "groups": []
                    })

                possible_subtask = expectations[tuple(subtask["key"])]

                worst_group = (1, "okay")
                group_status = []

                for i, g in enumerate(subtask["groups"]):
                    possible_group = expectations[tuple(g["key"])]

                    possible = possible_task + possible_subtask + possible_group

                    subtasks[-1]["groups"].append({"verdict": (42, ""),
                                                "cases": []})
                    min_f = 1.0  # Minimum "score" of a test case in this group

                    cases_failed = False

                    # List of all results of all test cases in this group
                    case_results = []
                    extended_results = []

                    for testcase in g["testcases"]:
                        idx = testcase["codename"]
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

                subtasks[-1]["status"] = (worst_group[0], worst_group[1].upper())

                if all(s == 1337 for s in group_status):
                    subtasks[-1]["status"] = (1337, "IGNORED")
                elif subtasks[-1]["status"][0] > 0 and any(s == 1337
                                                        for s in group_status):
                        subtasks[-1]["status"] = (1337, "PARTIALLY IGNORED")

                if len(group_status) == 0:
                    subtasks[-1]["status"] = (1337, "EMPTY")

                if subtasks[-1]["status"][0] <= 0:
                    subtasks_failed = True

        def is_in(x, l):
            return l[0] <= x <= l[1]

        sample_score = self._compute_score(submission_result, "sample")[0]
        partial_feedback_score = self._compute_score(submission_result, "partial")[0]
        final_score = self._compute_score(submission_result, "final")[0]

        sample_score_okay = is_in(sample_score, expected_sample_score)
        partial_feedback_score_okay = is_in(partial_feedback_score, expected_partial_feedback_score)
        final_score_okay = is_in(final_score, expected_final_score)

        partial_feedback_enabled = self.parameters["feedback"] == "partial"

        okay = not subtasks_failed \
            and sample_score_okay \
            and (partial_feedback_score_okay or not partial_feedback_enabled) \
            and final_score_okay \

        details = {
            "unit_test": True,
            "subtasks": subtasks,
            "verdict": (1, "Okay") if okay else (0, "Failed"),

            "sample_score_okay": sample_score_okay,
            "sample_score": sample_score,
            "expected_sample_score": expected_sample_score_info,

            "partial_feedback_enabled": partial_feedback_enabled,
            "partial_feedback_score_okay": partial_feedback_score_okay,
            "partial_feedback_score": partial_feedback_score,
            "expected_partial_feedback_score": expected_partial_feedback_score_info,

            "final_score_okay": final_score_okay,
            "final_score": final_score,
            "expected_final_score": expected_final_score_info,
            }

        return details

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
