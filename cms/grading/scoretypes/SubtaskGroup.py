#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2014 Fabian Gundlach <320pointsguy@gmail.com>
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
import json


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
{% for st in details %}
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
        <span class="title">
            {{ st["name"] }}
        </span>
    {% if "score" in st and "max_score" in st %}
        <span class="score">
            {{ '%g' % round(st["score"], 2) }} / {{ st["max_score"] }}
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
{% end %}"""

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
            if subtask["public"]:
                public_score += st_score
            else:
                private_score += st_score
            headers += ["%s (%g)" % (subtask["name"], st_score)]

        return private_score, public_score, headers

    def compute_score(self, submission_result, public):
        """Compute the score of a submission.

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
            if subtask["public"] or not public:
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
                if public == subtask["public"]:
                    score += st_score
                subtasks.append({
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

        if public:
            return score, json.dumps(subtasks)
        else:
            return score, json.dumps(subtasks), \
                json.dumps(ranking_details)

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
