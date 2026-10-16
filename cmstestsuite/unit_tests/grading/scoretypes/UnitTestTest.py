#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
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


import unittest

from cms.grading.scoretypes.GroupMin import GroupMin
from cms.grading.scoretypes.abc import ScoreTypeGroup, ScoreTypeGroupParametersDict


class UnitTestTest(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self._public_testcases = {
            "0_0": True,
            "1_0": True,
            "1_1": True,
            "2_0": True,
            "2_1": False,
            "2_2": False,
        }
        self._parameters: list[ScoreTypeGroupParametersDict] = [
            {
                "name": f"st{i}",
                "key": [f"st{i}_key"],
                "max_score": 10.0 * i,
                "testcases": i + 1,
            }
            for i in range(3)
        ]
        self._score_type = GroupMin(self._parameters, self._public_testcases, 2)

    def test_arbitrary_is_ignored(self):
        verdict, missing = self._score_type.compute_group_verdict(
            ["arbitrary"],
            [["time"], ["0.3", "memory?"]],
            [0.0, 0.3],
            self._parameters[1],
        )
        self.assertEqual(verdict[0], 1337)
        self.assertEqual(verdict[1], ScoreTypeGroup.IGN)
        self.assertEqual(missing, [])

    def test_unexpected_reason(self):
        for r in ["time", "memory"]:
            verdict, _ = self._score_type.compute_group_verdict(
                [r],
                [["time"], ["time", "memory"], ["0.5"]],
                [0.0, 0.0, 0.5],
                self._parameters[2],
            )
            self.assertEqual(verdict[0], -1)
            self.assertEqual(verdict[1], ScoreTypeGroup.FAILED)

    def test_score_too_low(self):
        verdict, _ = self._score_type.compute_group_verdict(
            [(0.5, 0.5)],
            [["0.0"], ["0.5"], ["time"]],
            [0.0, 0.5, 0.0],
            self._parameters[2],
        )
        self.assertEqual(verdict[0], -1)
        self.assertEqual(verdict[1], ScoreTypeGroup.FAILED)

    def test_ambiguous_result(self):
        verdict, _ = self._score_type.compute_group_verdict(
            [(1.0, 1.0)],
            [["time?", "1.0"]],
            [1.0],
            self._parameters[1],
        )
        self.assertEqual(verdict[0], 0)
        self.assertEqual(verdict[1], ScoreTypeGroup.AMBIG)

    def test_missing_expectation(self):
        for r in ["time", "memory"]:
            verdict, missing = self._score_type.compute_group_verdict(
                [r, (0.0, 0.0)],
                [["0.0"]],
                [0.0],
                self._parameters[0],
            )
            self.assertEqual(verdict[0], -1)
            self.assertEqual(verdict[1], ScoreTypeGroup.FAILED)
            self.assertEqual(missing, [r])

    def test_all_good(self):
        verdict, missing = self._score_type.compute_group_verdict(
            [(1.0, 1.0)],
            [["1.0"], ["1.0"]],
            [1.0, 1.0],
            self._parameters[1],
        )
        self.assertEqual(verdict[0], 1)
        self.assertEqual(verdict[1], ScoreTypeGroup.OKAY)
        self.assertEqual(missing, [])

    def test_all_tle_mle(self):
        verdict, missing = self._score_type.compute_group_verdict(
            ["time", "memory"],
            [["time"], ["time"], ["memory"]],
            [0.0, 0.0, 0.0],
            self._parameters[2],
        )
        self.assertEqual(verdict[0], 1)
        self.assertEqual(verdict[1], ScoreTypeGroup.OKAY)
        self.assertEqual(missing, [])

    def test_impossible_expectations_sanity_check(self):
        verdict, _ = self._score_type.compute_group_verdict(
            ["time", (0.5, 1.0)],
            [["time"], ["time"]],
            [0.0, 0.0],
            self._parameters[1],
        )
        self.assertIn(ScoreTypeGroup.IMPOSSIBLE_EXPECTATIONS, verdict[2])


if __name__ == "__main__":
    unittest.main()
