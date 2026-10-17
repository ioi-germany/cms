# -*- coding: UTF-8 -*-

"""
task-maker-rust (tmr) compatibility aliases for the german python format.

This mixin exposes task-maker-rust command names (from task.toml and
gen/gen.toml, see olimpiadi-informatica/task-maker-rust
docs/ioi-task-format.typ) inside a task's config.py and maps them to the
corresponding gerpythonformat functionality.

Every alias that cannot faithfully represent its tmr semantics LOUDLY
warns and states what information is discarded — this layer never drops
information silently. The warnings are collected and summarized when the
config finishes (see TaskConfig.report_tmr_incompatibilities).

Known systematic incompatibilities (warned about on use):
  * checker exit-code convention: tmr checkers must never exit non-zero
    and write the score to stdout; CMS/gerpythonformat judges by exit
    code (0 ok / 1 partial / 2 wrong) and the gerpythonformat
    checker() registers an INPUT checker (C++ only).
  * Python validators: gerpythonformat input checkers must be C++.
  * subtask auto-inclusion (include=["*"]), repeat, auto subtasks,
    per-subtask generators reuse, score_precision, syllabuslevel,
    controller limits, interactive/communication tasks: no equivalent.
"""

import os

from cmscontrib.gerpythonformat.CommonConfig import exported_function
from cmscontrib.gerpythonformat.Messenger import box, red, yellow, bold


def _tmr_warn(self, feature, detail):
    """Loudly report a tmr construct (in)compatibility and record it."""
    msg = bold("task-maker-rust: ") + feature + " — " + detail
    box(red(" TMR INCOMPATIBLE "), msg)
    if not hasattr(self, "tmr_incompatibilities"):
        self.tmr_incompatibilities = []
    self.tmr_incompatibilities.append(feature + ": " + detail)


class TmrCompat(object):
    """task-maker-rust name aliases; mixed into TaskConfig.

    Native names (title, checker, constraint, testcase, ...) keep their
    gerpythonformat meaning; the aliases below follow tmr semantics.
    """

    # ------------------------------------------------------------------
    # task.toml keys
    # ------------------------------------------------------------------

    @exported_function
    def time_limit(self, t):
        """tmr `time_limit` (seconds) -> timelimit()."""
        return self.timelimit(t)

    @exported_function
    def memory_limit(self, m):
        """tmr `memory_limit` (MiB) -> memorylimit()."""
        return self.memorylimit(m)

    @exported_function
    def score_precision(self, n):
        """tmr `score_precision`: no per-task equivalent in CMS here."""
        _tmr_warn(self, "score_precision=%s" % n,
                 "CMS score rounding must be set in the contest; DISCARDED")

    @exported_function
    def syllabuslevel(self, n):
        """tmr `syllabuslevel`: not part of the german format."""
        _tmr_warn(self, "syllabuslevel=%s" % n,
                 "no equivalent in gerpythonformat; DISCARDED")

    @exported_function
    def feedback_level(self, level):
        """tmr `feedback_level`: feedback is a contest-level setting in
        gerpythonformat (full_feedback / restricted_feedback)."""
        if level not in ("full",):
            _tmr_warn(self, "feedback_level=%s" % level,
                     "set feedback at contest level instead; DISCARDED")

    @exported_function
    def user_io(self, mode):
        """tmr `user_io`: communication tasks are not supported."""
        if mode != "std_io":
            _tmr_warn(self, "user_io=%s" % mode,
                     "communication tasks unsupported; DISCARDED")

    @exported_function
    def interactive_concurrent(self, b):
        _tmr_warn(self, "interactive_concurrent",
                  "interactive tasks unsupported; DISCARDED")

    @exported_function
    def controller_time_limit(self, t):
        _tmr_warn(self, "controller_time_limit=%s" % t,
                  "interactive tasks unsupported; DISCARDED")

    @exported_function
    def controller_wall_time_limit(self, t):
        _tmr_warn(self, "controller_wall_time_limit=%s" % t,
                  "interactive tasks unsupported; DISCARDED")

    @exported_function
    def controller_memory_limit(self, m):
        _tmr_warn(self, "controller_memory_limit=%s" % m,
                  "interactive tasks unsupported; DISCARDED")

    @exported_function
    def controller_process_limit(self, n):
        _tmr_warn(self, "controller_process_limit=%s" % n,
                  "interactive tasks unsupported; DISCARDED")

    # ------------------------------------------------------------------
    # gen.toml: solutions, generators, checkers
    # ------------------------------------------------------------------

    @exported_function
    def solution(self, filename):
        """tmr master solution -> output_generator(compile())."""
        # native compile() works on basenames
        exe = self.compile(os.path.splitext(filename)[0])
        self.output_generator(exe)
        return exe

    @exported_function
    def generator(self, filename):
        """tmr `generator` -> compile() of the generator source."""
        return self.compile(os.path.splitext(filename)[0])

    @exported_function
    def output_checker(self, filename):
        """tmr `checker.<ext>` (judges contestant output) ->
        batch(comparator=...).

        WARNING: convention mismatch — tmr checkers never exit non-zero
        and print the score (0.0..1.0) on stdout; CMS comparators signal
        the verdict via exit code (0 ok / 1 partial / 2 wrong, optional
        score on stdout). A tmr-style checker silently misgrades as
        'correct' for every testcase. gerpythonformat's own checker()
        registers an INPUT checker (C++ only).
        """
        _tmr_warn(self, "output_checker(%s)" % filename,
                  "tmr stdout-score checker vs CMS exit-code comparator: "
                  "adapt the checker before use")
        exe = self.compile(os.path.splitext(filename)[0])
        self.batch(comparator=exe)
        return exe

    @exported_function
    def validator(self, filename, args=None):
        """tmr `validator.<ext>`: gerpythonformat input checkers must be
        C++; a Python validator has no equivalent."""
        if filename.endswith(".py") or os.path.isfile(filename + ".py"):
            _tmr_warn(self, "validator(%s)" % filename,
                     "Python validators unsupported by gerpythonformat "
                     "(C++ input checkers only); DISCARDED")
            return None
        return self.checker(self.compile(os.path.splitext(filename)[0]))

    @exported_function
    def grader(self, filename):
        _tmr_warn(self, "grader(%s)" % filename,
                  "graders/stubs are contest-attached in CMS; not compiled "
                  "here; DISCARDED")

    stub = grader

    # ------------------------------------------------------------------
    # gen.toml: constraints
    # ------------------------------------------------------------------

    @exported_function
    def constraints(self, **specs):
        """tmr-style constraint spec -> constraint() strings.

        Accepts {var: {"min": a, "max": b}, ...} (tmr gen.toml constants
        as used by validators); also the gerpythonformat shorthand
        {var: "[a,b]"} or {var: ("a", "b")}. Anything else (lists of
        constraint dicts, expressions) is reported as incompatible.
        """
        for var in sorted(specs):
            spec = specs[var]
            if isinstance(spec, dict):
                lo = spec.get("min", "")
                hi = spec.get("max", "")
                rest = set(spec) - {"min", "max"}
                if rest:
                    _tmr_warn(self, "constraint %s: %s" % (var, sorted(rest)),
                             "only min/max map to constraint ranges; "
                             "DISCARDED")
                self.constraint("%s:[%s,%s]" % (var, lo, hi))
            elif isinstance(spec, (tuple, list)) and len(spec) == 2:
                self.constraint("%s:[%s,%s]" % (var, spec[0], spec[1]))
            elif isinstance(spec, str):
                self.constraint("%s:%s" % (var, spec))
            else:
                _tmr_warn(self, "constraint %s=%r" % (var, spec),
                         "unsupported constraint spec form; DISCARDED")

    @exported_function
    def samples(self, num=None, group_name=None, pattern=None):
        """tmr `samples`: samples must be explicit saved testcases
        (testcase(explicit(...), save=True)) in gerpythonformat."""
        _tmr_warn(self, "samples(num=%s)" % num,
                  "declare samples as testcase(explicit(...), save=True); "
                  "DISCARDED")

    @exported_function
    def include(self, names):
        """tmr group/subtask `include` (incl. ["*"]): no equivalent."""
        _tmr_warn(self, "include=%s" % (names,),
                  "gerpythonformat subtasks list their testcases explicitly;"
                  " DISCARDED")

    @exported_function
    def copy(self, paths):
        """tmr static input files `copy` -> testcase(explicit(...))."""
        if isinstance(paths, str):
            paths = [paths]
        return [self.testcase(self.explicit(p)) for p in paths]

    @exported_function
    def repeat(self, n):
        """tmr `repeat`: call the testcase definition n times yourself."""
        _tmr_warn(self, "repeat=%s" % n,
                  "must be unrolled explicitly in gerpythonformat; "
                  "DISCARDED")

    # ------------------------------------------------------------------
    # reporting
    # ------------------------------------------------------------------

    @exported_function
    def report_tmr_incompatibilities(self):
        """Print a summary of all tmr incompatibilities hit so far."""
        entries = getattr(self, "tmr_incompatibilities", [])
        self.tmr_incompatibilities = []  # report once
        if not entries:
            box(yellow(" TMR "), "no task-maker-rust incompatibilities "
                "detected")
            return
        body = "\n".join("- " + e for e in entries)
        box(red(" TMR INCOMPATIBILITIES (%d) " % len(entries)), body)
