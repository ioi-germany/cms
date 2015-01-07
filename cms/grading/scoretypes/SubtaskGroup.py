#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2015 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2013-2014 Tobias Lenz <t_lenz94@web.de>
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

from cms.grading.ScoreType import ScoreType
from cms.grading import UnitTest, mem_human, time_human

import json
import logging


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
{% if not details["unit_test"] %}
{% for st in details["subtasks"] %}
    {% if "score" in st and "max_score" in st %}
        {% if st["score"] >= st["max_score"] %}
<div class="subtask correct">
        {% elif st["score"] <= 0.0 %}
<div class="subtask notcorrect">
        {% else %}
<div class="subtask partiallycorrect">
        {% end %}
    {% else %}
<div style="height:0px;display:none;">
    {% end %}
    <div class="subtask-head">
        <span class="title" style="margin-top:-2px;">
            {{ st["name"] }}
        </span>
    {% if "score" in st and "max_score" in st %}
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
    {% else %}
        <span class="score">
            {{ _("N/A") }}
        </span>
    {% end %}
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
{% else %}
{% for st in details["subtasks"] %}
    {% if st["status"][0] > 0 %}
<div class="subtask correct">
    {% else %}
<div class="subtask notcorrect">
    {% end %}
    <div class="subtask-head">
        <span class="title" style="margin-top:-2px;">
            {{ st["name"] }}
        </span>
        <span class="score">
            {{st["status"][1].upper()}}
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
                     title="{{c["time"]}}">
                        {{c["line"][0][0]}}
                    </td>
                    <td class="{{"unit_test_ok" if c["line"][1][1] > 0 else \
                                 "unit_test_failed" if c["line"][1][1] < 0 \
                                 else ""}} short" style="cursor:default;"
                     title="{{c["memory"]}}">
                        {{c["line"][1][0]}}
                    </td>
                    <td class="{{"unit_test_ok" if c["line"][2][1] > 0 else \
                                 "unit_test_failed" if c["line"][2][1] < 0 \
                                 else ""}} short">
                        {{c["line"][2][0]}}
                    </td>
            {% if c["verdict"][0] != 42 %}
                    <td class="{{"unit_test_ok" if c["verdict"][0] > 0 else \
                                 "unit_test_failed"}}">
                        {{c["verdict"][1]}}
                    </td>
            {% else %}
                    <td class="no_expectations"> {{c["verdict"][1]}} </td>
            {% end %}
            {% if first %}
                    <td rowspan={{g["grouplen"]}} class="{{"unit_test_ok" if \
                                  g["verdict"][0] > 0 else \
                                  "unit_test_failed"}}">
                        {% raw g["verdict"][1] %}
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

    def __init__(self, parameters, public_testcases):
        self._feedback = parameters['feedback']
        super(SubtaskGroup, self).__init__(parameters['tcinfo'],
                                           public_testcases)

    def feedback(self):
        return self._feedback

    def unit_test_expected_scores(self, submission_info):
        submission_info = json.loads(submission_info)

        public = submission_info.get("expected_public_score", 0)
        private = submission_info.get("expected_score", 0)

        return public, private

    def max_scores(self):
        """Compute the maximum score of a submission.

        See the same method in ScoreType for details.

        """
        private_score = 0.0
        public_score = 0.0
        headers = list()

        for subtask in self.parameters:
            st_score = 0
            for group in subtask["groups"]:
                st_score += group["points"]
            if subtask["for_public_score"]:
                public_score += st_score
            if subtask["for_private_score"]:
                private_score += st_score
            headers += ["%s (%g)" % (subtask["name"], st_score)]

        return private_score, public_score, headers

    def compute_score(self, submission_result, public):
        """Compute the score of a normal submission.

        See the same method in ScoreType for details.

        """
        # Actually, this means it didn't even compile!
        if not submission_result.evaluated(public):
            if public:
                return 0.0, json.dumps([])
            else:
                return 0.0, json.dumps([]), \
                    json.dumps(["%lg" % 0.0 for _ in self.parameters])

        evaluations = dict((ev.codename, ev)
                           for ev in submission_result.evaluations)
        subtasks = []
        score = 0
        if not public:
            ranking_details = []

        for subtask in self.parameters:
            if subtask["public"] or not public:  # Shakespeare has been here
                st_score = 0
                st_maxscore = 0
                testcases = []
                for groupnr, group in enumerate(subtask["groups"]):
                    outcomes = [float(evaluations[idx].outcome)
                                for idx in group["cases"]]
                    gr_score = self.reduce(outcomes) * group["points"]
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
                            tc["groupnr"] = groupnr+1
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
            return score, json.dumps(details), \
                json.dumps(ranking_details)

    def compute_unit_test_score(self, submission_result,
                                submission_info):
        """Compute the score of a unit test.

        """
        public = False

        if submission_info is None:
            return json.dumps({"verdict": (-1, "Not a Unit Test")})

        wanted_public, wanted_private = \
            self.unit_test_expected_scores(submission_info)

        submission_info = json.loads(submission_info)

        # Actually, this means it didn't even compile!
        if not submission_result.evaluated(public):
            D = {'subtasks': [], 'info': submission_info,
                 'verdict': (-1, "Compilation failed")}
            return json.dumps(D)

        evaluations = dict((ev.codename, ev)
                           for ev in submission_result.evaluations)
        subtasks = []
        public_score = 0
        private_score = 0

        expectations = {tuple(json.loads(key)): val for key, val
                        in submission_info["expected"].iteritems()}
        possible_task = expectations[()]
        possible_subtask = []
        possible_group = []
        extra = []
        case_results = []
        subtasks_failed = False

        symbol_table = ['✓', '≈', '✗', '―']

        for subtask in self.parameters:
            subtasks.append({"name": subtask["name"], "status": (0, "okay"),
                             "groups": []})
            possible_subtask = expectations[tuple(subtask["key"])]

            group_score = 0

            worst_group = (1, "okay")

            for i, g in enumerate(subtask["groups"]):
                possible_group = expectations[tuple(g["key"])]
                possible = possible_task + possible_subtask + possible_group

                subtasks[-1]["groups"].append({"verdict": (42, ""),
                                               "cases": [],
                                               "grouplen": 0})
                min_f = 1.0
                extra = []

                cases_failed = False
                worst_case = (2, "")
                case_results = []

                for idx, unique in zip(g["cases"], g["case_keys"]):
                    subtasks[-1]["groups"][-1]["grouplen"] += 1
                    r = UnitTest.get_result(submission_info["limits"],
                                            evaluations[idx])
                    t = time_human(evaluations[idx].execution_time)
                    m = mem_human(evaluations[idx].execution_memory) + "B"
                    min_f = min(min_f, UnitTest.score(r) if
                                UnitTest.meaningful_score(r) else 0)

                    mandatory = expectations[tuple(unique)]

                    l = UnitTest.case_line(r, mandatory,
                                           possible + mandatory,
                                           symbol_table)
                    v = (42, "No explicit expectations given for "
                             "this testcase.")

                    subtasks[-1]["groups"][-1]["cases"].\
                        append({"line": l, "verdict": v, "time": t,
                                "memory": m})

                    accepted, desc = \
                        UnitTest.judge_case(r, mandatory, mandatory + possible)

                    if len(mandatory) == 0:
                        worst_case = min(worst_case, (accepted, desc))
                    else:
                        subtasks[-1]["groups"][-1]["cases"][-1]["verdict"] = \
                            (accepted, desc)
                        if accepted <= 0:
                            cases_failed = True

                    case_results += r
                    extra += mandatory

                group_score += min_f * g["points"]

                status, short, desc = \
                    UnitTest.judge_group(case_results, possible,
                                         possible + extra)
                c_st = "failed" if worst_case[0] < 0 else \
                       "ambiguous" if worst_case[0] == 0 else "okay"
                status, short, desc = min((status, short, desc),
                                          (worst_case[0], c_st, worst_case[1]))

                if cases_failed:
                    if status > 0:
                        desc = ""
                    else:
                        desc += "<br><br>"

                    status = -1
                    desc += "At least one testcase did not behave as " \
                            "expected, cf. the \"test verdict\" column."

                subtasks[-1]["groups"][-1]["verdict"] = (status, desc)
                worst_group = min(worst_group, (status, short))

            if subtask["for_public_score"]:
                public_score += group_score
            if subtask["for_private_score"]:
                private_score += group_score

            subtasks[-1]["status"] = worst_group

            if subtasks[-1]["status"][0] <= 0:
                subtasks_failed = True

        details = {"unit_test": True, "subtasks": subtasks,
                   "more": self.parameters, "verdict": (1, "Okay")}

        okay = private_score == wanted_private and \
            (public_score == wanted_public or self._feedback == "full") \
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

    def reduce(self, outcomes):
        return min(outcomes)
