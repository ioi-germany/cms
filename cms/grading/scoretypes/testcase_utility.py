from dataclasses import dataclass, field
from enum import Enum

from cms.db.submission import SubmissionResult
from cms.grading.scoretypes.abc import ScoreTypeGroup


class Relevance(Enum):
    essential = "Essential"
    probably_useful = "Probably useful"
    to_inspect = "To inspect"
    probably_useless = "Probably useless"
    useless = "Useless"
    strong_sample = "Strong sample testcase"

RELEVANCE_DESCRIPTIONS = {
    Relevance.essential: (
        "E",
        "Removing this testcase would change the score of at least one unit test.",
    ),
    Relevance.probably_useful: (
        "P+",
        "This testcase is useful, but not essential from what I can tell (that's great!)",
    ),
    Relevance.to_inspect: (
        "I",
        "This testcase gives a very similar score as some other testcases for every"
        + "unit test; you might want to have a closer look whether you need it.",
    ),
    Relevance.probably_useless: (
        "P?",
        "This testcases is probably useless as there are other testcases which are at least as "
        + "strong across all unit tests (i.e. which always produce scores which are lower or at least "
        + "close to the score of this testcase)",
    ),
    Relevance.useless: (
        "U",
        "This testcase is useless, i.e. removing it does not even come close to "
        + "affecting scoring (for example because every unit test succeeds on them)",
    ),
    Relevance.strong_sample: (
        "!",
        "This sample testcase is relevant for scoring—that's... kind of disturbing to be honest.",
    ),
}


@dataclass
class TestcaseRelevance:
    relevance: Relevance
    sample: bool
    essential_for: list[str] = field(default_factory=list)
    strictly_dominated_by: list[str] = field(default_factory=list)
    similar_to: list[str] = field(default_factory=list)

    @property
    def badge_letter(self) -> str:
        return RELEVANCE_DESCRIPTIONS[self.relevance][0]

    @property
    def description(self) -> str:
        return RELEVANCE_DESCRIPTIONS[self.relevance][1]

    @property
    def strong_sample(self) -> bool:
        return self.relevance == Relevance.strong_sample


def evaluate_testcase_relevance(
    unit_test_results: list[SubmissionResult], score_type: ScoreTypeGroup
):
    targets = score_type.retrieve_target_testcases()
    cases = sorted({c for target in targets for c in target})
    essential_for: dict[str, list[str]] = {}
    useful: set[str] = set()
    dominated = {d: {c for c in cases if c != d} for d in cases}

    for u in unit_test_results:
        details = u.unit_test_score_details
        if details is None:
            continue
        useful |= set(details["useful"])

        for e in details["essential"]:
            if e not in essential_for:
                essential_for[e] = []
            essential_for[e].append(u.submission.comment)

        for tc in dominated:
            if tc in details["dominated"]:
                dominated[tc] &= set(details["dominated"][tc])

    sample_cases: set[str] = set()
    for st_idx, parameter in enumerate(score_type.parameters):
        if score_type.is_sample_subtask(parameter):
            sample_cases |= set(targets[st_idx])

    potentially_useful_cases = sorted(c for c in useful if c not in essential_for)
    probably_useless: set[str] = set()
    probably_useful: set[str] = set()
    to_inspect: set[str] = set()
    strictly_dominated: dict[str, list[str]] = {}
    similar_to: dict[str, list[str]] = {}

    for tc in potentially_useful_cases:
        strict_dominators = [d for d in dominated[tc] if tc not in dominated[d]]
        if strict_dominators:
            probably_useless.add(tc)
            strictly_dominated[tc] = sorted(strict_dominators[:])
        elif len(dominated[tc]) == 0:
            probably_useful.add(tc)
        else:
            to_inspect.add(tc)
            component = {d for d in dominated[tc] if tc in dominated[d]}
            similar_to[tc] = sorted(component)

    stats: dict[str, TestcaseRelevance] = {}
    for tc in cases:
        if tc in sample_cases and (tc in essential_for or tc in probably_useful):
            relevance = Relevance.strong_sample
        elif tc in essential_for:
            relevance = Relevance.essential
        elif tc in probably_useful:
            relevance = Relevance.probably_useful
        elif tc in to_inspect:
            relevance = Relevance.to_inspect
        elif tc in probably_useless:
            relevance = Relevance.probably_useless
        else:
            relevance = Relevance.useless
        stats[tc] = TestcaseRelevance(
            relevance,
            sample=tc in sample_cases,
            essential_for=essential_for.get(tc, []),
            strictly_dominated_by=strictly_dominated.get(tc, []),
            similar_to=similar_to.get(tc, []),
        )
    return stats
