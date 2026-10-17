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

import glob
import os
import re
import shutil

from cmscontrib.gerpythonformat.CommonConfig import exported_function
from cmscontrib.gerpythonformat.Messenger import box, green, yellow, bold


def _tmr_warn(self, feature, detail):
    """Loudly report a tmr construct (in)compatibility and record it."""
    msg = bold("task-maker-rust: ") + feature + " — " + detail
    box(" TMR INCOMPATIBLE ", yellow(msg))
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
    # tmr export: produce a task-maker-rust task folder from this config
    # ------------------------------------------------------------------

    @exported_function
    def tmr_export(self, dest="tmr", template=None):
        """Export a task-maker-rust compatible task folder.

        Writes <wdir>/<dest>/ containing task.toml, task.yaml (which the
        official statement template reads), gen/gen.toml + validator stub,
        sol/, and statement/english.typ with the sample files in tmr's
        naming scheme. The statement is GENERATED from the task's data;
        prose is carried over from statement-en.typ when it exists (prose
        cannot be generated from data). Everything that cannot be
        represented LOUDLY warns and is recorded.

        dest (string): target folder name relative to the task's wdir
        template (string): path to the official typst-statement-template
                       template.typ, copied into statement/; defaults to
                       $TMR_TEMPLATE; a loud warning is emitted if absent

        """
        from cmscontrib.gerpythonformat.ConstraintParser import Constraint

        out = os.path.join(self.wdir, dest)
        box(" TMR EXPORT ", "writing task-maker-rust task to {}".format(
            os.path.relpath(out, os.getcwd())))
        for d in ("statement", "gen", "sol", os.path.join("gen", "static")):
            dd = os.path.join(out, d)
            if not os.path.isdir(dd):
                os.makedirs(dd)

        name = self.name
        title = getattr(self, "_title", None) or name
        timelimit = getattr(self, "_timelimit", 1.0)
        memlimit = getattr(self, "_memorylimit", 256)

        # --- task.toml (tmr input) + task.yaml (template input) --------
        limits = ["title = \"{}\"".format(title),
                  "time_limit = {}".format(float(timelimit)),
                  "memory_limit = {}".format(int(memlimit))]
        if self._has_restricted_feedback_level():
            limits.append("feedback_level = \"oi_restricted\"")
        with open(os.path.join(out, "task.toml"), "w") as f:
            f.write("\n".join(limits) + "\n")
        with open(os.path.join(out, "task.yaml"), "w") as f:
            f.write("name: {}\n".format(name))
            f.write("\n".join(l.replace(" = ", ": ").replace("\"", "")
                              for l in limits) + "\n")

        # --- constraints: global constants ------------------------------
        def consts(scope):
            d = {}
            for cl in scope.constraints:
                if cl.silent:
                    continue
                for c in cl.constraints:
                    for var, (lo, hi) in c.uncompress().items():
                        d["MIN_" + var.upper()] = lo
                        d["MAX_" + var.upper()] = hi
            return d

        def toml_val(v):
            if isinstance(v, int):
                return str(v)
            if isinstance(v, float) and v == int(v):
                return str(int(v))
            if isinstance(v, float):
                return str(v)
            _tmr_warn(self, "constant %r" % (v,),
                     "non-numeric bound; emitted quoted")
            return "\"%s\"" % v

        samples = list(self.saved)

        # --- statement samples: statement/<name>.(input|output)<i>.txt -
        for i, case in enumerate(samples):
            shutil.copy(case.infile, os.path.join(
                out, "statement", "%s.input%d.txt" % (name, i)))
            shutil.copy(case.outfile, os.path.join(
                out, "statement", "%s.output%d.txt" % (name, i)))

        # --- static testcases: gen/static/<name>_<codename>.in ---------
        copied = {}
        for s in self.subtasks:
            if s.sample:
                continue
            for case in s.cases:
                if case is None:
                    _tmr_warn(self, "testcase %s" % s.name,
                             "dummy case (minimal mode); SKIPPED")
                    continue
                if case.codename not in copied:
                    shutil.copy(case.infile, os.path.join(
                        out, "gen", "static",
                        "%s_%s.in" % (name, case.codename)))
                    copied[case.codename] = case

        # --- gen/gen.toml ------------------------------------------------
        g = ["# generated by cmsGerMakeTask tmr_export from config.py",
             "# ger testcases are static files (no generator pipeline);",
             "# see validator.py",
             "samples = %d" % len(samples)]
        g += ["%s = %s" % (k, toml_val(v))
              for k, v in sorted(consts(self).items())]
        if any(s.sample for s in self.subtasks):
            g += ["", "[subtask.samples]", "include = [\"samples\"]",
                  "score = 0"]
        for s in self.subtasks:
            if s.sample:
                continue
            g += ["", "[subtask.%s]" % s.name,
                  "score = %s" % toml_val(s.points)]
            g += ["%s = %s" % (k, toml_val(v))
                  for k, v in sorted(consts(s).items())]
            g += ["copy = [%s]" % ", ".join(
                "\"gen/static/%s_%s.in\"" % (name, c.codename)
                for c in s.cases if c is not None)]
        with open(os.path.join(out, "gen", "gen.toml"), "w") as f:
            f.write("\n".join(g) + "\n")

        # --- validator stub -----------------------------------------------
        with open(os.path.join(out, "gen", "validator.py"), "w") as f:
            f.write("#!/usr/bin/env python3\n"
                    "# generated stub: gerpythonformat validates testcases "
                    "with its own C++\n"
                    "# input checker at generation time; this stub accepts "
                    "everything.\n"
                    "# Port the checker()/add_checker logic here for real "
                    "validation.\n"
                    "import sys\n\n"
                    "if __name__ == \"__main__\":\n    sys.exit(0)\n")
        if self._get_checkers():
            _tmr_warn(self, "input checker(s)",
                     "ger C++ input checker NOT exported (tmr validator.py "
                     "is a stub); port constraint checks there")
        if self.managers.get("checker"):
            _tmr_warn(self, "output comparator",
                     "CMS comparator not exported; tmr checker convention "
                     "(score on stdout, never non-zero exit) differs from "
                     "CMS exit-code verdicts")
        _tmr_warn(self, "generator pipeline",
                  "testcases exported as static files (copy=), not "
                  "generator+args+seed")

        # --- sol/ --------------------------------------------------------
        sols = [p for p in glob.glob(os.path.join(self.wdir, "solution.*"))
                if os.path.isfile(p)
                and os.path.splitext(p)[1] in (".c", ".cpp", ".py", ".pas",
                                               ".java")]
        for p in sols:
            shutil.copy(p, os.path.join(out, "sol", os.path.basename(p)))
        if not sols:
            _tmr_warn(self, "master solution",
                     "no solution.* source found; tmr tasks require "
                     "sol/solution.<ext>")

        # --- statement/english.typ (generated; prose carried over) -----
        src = os.path.join(self.wdir, "statement-en.typ")
        if os.path.isfile(src):
            with open(src, encoding="utf-8") as f:
                body = self._tmr_convert_statement(f.read(),
                                                  len(samples) > 0)
        else:
            _tmr_warn(self, "statement-en.typ",
                     "no typst statement source; prose CANNOT be generated "
                     "from data; exporting data sections only")
            body = ""
        with open(os.path.join(out, "statement", "english.typ"), "w",
                  encoding="utf-8") as f:
            f.write("#import \"template.typ\": *\n\n"
                    "#set text(lang: \"en\")\n\n"
                    "#show: statement\n\n" + body)

        # --- official template --------------------------------------------
        tmpl = template or os.environ.get("TMR_TEMPLATE")
        if tmpl and os.path.isfile(tmpl):
            shutil.copy(tmpl, os.path.join(out, "statement", "template.typ"))
        else:
            _tmr_warn(self, "template.typ",
                     "official typst-statement-template not provided "
                     "(set TMR_TEMPLATE or pass template=); statement/"
                     "english.typ needs it")

        box(" TMR EXPORT ", green("exported to {}".format(out)))
        return out

    # -- statement conversion helpers (typst -> typst, data-driven) ----

    def _tmr_scope_math(self, scope, names=None):
        """Join the scope's displayable constraints as typst math."""
        items = []
        for cl in scope.constraints:
            if cl.silent:
                continue
            for c in cl.constraints:
                vals = [v.val for v in c.variables]
                if names and not set(names).intersection(vals):
                    continue
                items.append(c.typst())
        return " and ".join(items)

    def _tmr_cc(self, scope, names):
        """currconstraint(...) equivalent: the matching constraint math."""
        fallback = None
        for cl in scope.constraints:
            if cl.silent:
                continue
            for c in cl.constraints:
                vals = set(v.val for v in c.variables)
                if vals == set(names):
                    return c.typst()
                if fallback is None and vals.intersection(names):
                    fallback = c.typst()
        if fallback:
            return fallback
        _tmr_warn(self, "currconstraint(\"%s\")" % ",".join(names),
                  "no matching constraint in scope; rendered empty")
        return ""

    def _tmr_bound(self, scope, name, which):
        """Math fragment ('$…$'): one bound of one variable, like our
        currconstraintlower/upper accessors return."""
        for cl in scope.constraints:
            for c in cl.constraints:
                if any(v.val == name for v in c.variables):
                    b = c.min if which == "min" else c.max
                    if b is None:
                        return ""
                    from cmscontrib.gerpythonformat.ConstraintParser \
                        import Constraint
                    return "$%s$" % Constraint.typst_bound(b)
        return ""

    def _tmr_sub_accessors(self, s, scope):
        """Replace our constraint accessors by generated typst math."""
        s = re.sub(r'#currconstraints-simple\(\)',
                   lambda m: self._tmr_scope_math(scope), s)
        s = re.sub(r'#currconstraints\(\)',
                   lambda m: self._tmr_scope_math(scope), s)
        s = re.sub(r'#currconstraint\("([^"]*)"\)',
                   lambda m: self._tmr_cc(
                       scope, [x.strip() for x in m.group(1).split(",")]), s)
        s = re.sub(r'#currconstraintlower\("([^"]*)"\)',
                   lambda m: self._tmr_bound(scope, m.group(1), "min"), s)
        s = re.sub(r'#currconstraintupper\("([^"]*)"\)',
                   lambda m: self._tmr_bound(scope, m.group(1), "max"), s)
        return s

    @staticmethod
    def _tmr_block(text, start):
        """Extract a [...] block (start at '['); returns
        (content, index_after)."""
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    return text[start + 1:i], i + 1
        raise Exception("unbalanced [ ] in statement")

    def _tmr_convert_statement(self, text, has_samples):
        """Convert our typst statement to the official template API.

        Prose passes through (it is typst already); all taskinfo-specific
        commands are replaced by generated calls/math; subtask blocks are
        collected into one #subtasks(...) call."""
        non_samples = [s for s in self.subtasks if not s.sample]
        out = []
        descs = []
        i = 0
        n = len(text)
        while i < n:
            line_end = text.find("\n", i)
            if line_end == -1:
                line_end = n
            line = text[i:line_end]
            s = line.strip()

            if s.startswith("#subtask["):
                content, after = self._tmr_block(text,
                                                 text.index("[", i))
                scope = non_samples[len(descs)] if len(descs) < \
                    len(non_samples) else self
                body = self._tmr_sub_accessors(
                    content.strip(), scope).strip()
                descs.append("  subtask => [%s]," % body)
                if len(descs) == 1:
                    out.append("@@SUBTASKS@@")
                i = after
                continue

            if s.startswith("#note[") or s.startswith("#warn["):
                content, after = self._tmr_block(text, text.index("[", i))
                cmd = "#note" if "#note" in s[:6] else "#warn"
                out.append("%s[%s]" % (cmd, self._tmr_sub_accessors(
                    content.strip(), self).strip()))
                i = after
                continue

            # simple line rules
            if s.startswith("#import") or s.startswith("#show:"):
                i = line_end + 1
                continue
            if s.startswith("#tasktitle") or s == "#sep":
                i = line_end + 1
                continue
            if s.startswith("= ") and not s.startswith("== "):
                i = line_end + 1  # template prints the title
                continue
            if s == "== Input":
                out.append("=== Input:")
            elif s == "== Output":
                out.append("=== Output:")
            elif s == "== Constraints" or s.startswith("#t-constraints:"):
                rest = s.split(":", 1)[1].strip() \
                    if s.startswith("#t-constraints:") else ""
                if rest:
                    out.append("#constraints\n- " +
                               self._tmr_sub_accessors(rest, self))
                else:
                    out.append("#constraints")
            elif s == "== Subtasks":
                out.append("#scoring")
            elif s in ("#standardpart()", "#showcases()"):
                out.append("#examples()")
            elif s == "#showlimits():":
                pass  # limits are rendered by the template from task.yaml
            elif s == "#showlimits()":
                pass
            else:
                out.append(self._tmr_sub_accessors(line, self))
            i = line_end + 1

        body = "\n".join(out)
        if has_samples:
            descs.insert(0, "  subtask => [Sample test cases.],")
        subs = "#subtasks((\n" + "\n".join(descs) + "\n))" \
            if descs else ""
        body = body.replace("@@SUBTASKS@@", subs)

        # warn about remaining taskinfo-specific commands
        for m in re.finditer(r'#([a-z][\w-]*)', body):
            tok = m.group(1)
            if tok not in ("note", "warn", "constraints", "scoring",
                           "explanation", "examples", "subtasks", "raw",
                           "text", "set", "show", "image", "link", "align",
                           "table", "figure", "h", "v"):
                _tmr_warn(self, "#%s" % tok,
                         "unknown command passed through; may not compile "
                         "under the official template")
        if "#examples" not in body:
            body += "\n\n#examples()\n"
        # collapse runs of blank lines left by dropped commands
        body = re.sub(r"\n{3,}", "\n\n", body)
        return body + "\n"

    # ------------------------------------------------------------------
    # reporting
    # ------------------------------------------------------------------

    @exported_function
    def report_tmr_incompatibilities(self):
        """Print a summary of all tmr incompatibilities hit so far."""
        entries = getattr(self, "tmr_incompatibilities", [])
        self.tmr_incompatibilities = []  # report once
        if not entries:
            box(" TMR ", green("no task-maker-rust incompatibilities "
                "detected"))
            return
        body = "\n".join("- " + e for e in entries)
        box(" TMR INCOMPATIBILITIES (%d) " % len(entries), yellow(body))
