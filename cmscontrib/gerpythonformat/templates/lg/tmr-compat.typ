// task-maker-rust statement API aliases (see the tmr docs
// ioi-task-format.typ); embedded into taskinfo.typ after contestheader
// (its content wraps it). tmr takes this data from gen.toml/task.toml;
// here it comes from our taskinfo instead, so tmr arguments that carry
// such data are accepted and ignored (noted per alias). The statement
// content itself (titles, constraint values) still uses our taskinfo
// accessors.

// tmr wraps the statement body in `#statement[...]`; that is our
// taskheader.
#let statement(body) = taskheader(body)

// Localized section headings. tmr uses bare content values (#constraints,
// not #constraints()); the heading elements are created at definition
// time, i.e. before taskheader's `set heading(numbering: none)` applies,
// so numbering is disabled explicitly here.
#let implementation = heading(level: 2, numbering: none)[#t-implementation]
#let constraints = heading(level: 2, numbering: none)[#t-constraints]
#let scoring = heading(level: 2, numbering: none)[#t-scoring]
#let explanation = heading(level: 2, numbering: none)[#t-explanation]
#let samplegrader = heading(level: 2, numbering: none)[#t-samplegrader]

// tmr renders a format line under "Input format"/"Output format"; we
// mirror the lg section headings and place the body underneath.
#let inputformat(body) = {
  heading(level: 2, numbering: none)[#t-input]
  body
}
#let outputformat(body) = {
  heading(level: 2, numbering: none)[#t-output]
  body
}

// Highlight boxes (plain typst stand-ins for the tmr template boxes).
#let note(body) = {
  v(0.5em)
  block(width: 100%, inset: (x: 8pt, y: 6pt), fill: luma(245),
        stroke: 0.5pt + luma(180))[#body]
  v(0.5em)
}
#let warn(body) = {
  v(0.5em)
  block(width: 100%, inset: (x: 8pt, y: 6pt), fill: rgb("#fff4f4"),
        stroke: 0.8pt + highlightcolor)[#body]
  v(0.5em)
}

// tmr reads the sample count from gen.toml; here it is numsamples, so
// any argument is accepted and ignored.
#let examples(..args) = showcases()

// tmr passes each subtask's gen.toml constants to its lambda; there are
// no named constants here, so the lambda gets an empty dict and reads
// values via currconstraints()/currconstraint(name). index-start is
// accepted but ignored: lg numbers subtasks from 1.
#let subtasks(fs, index-start: 0) = {
  for f in fs {
    subtask(f((:)))
  }
}

// OIS-style subtasks with explicit points; the points come from the task
// config here, so the second argument is ignored.
#let ois-subtasks(fs, points) = subtasks(fs)

// Grader function signatures: one boxed raw line per (lang, signature).
#let signatures(sigs) = {
  v(0.5em)
  for s in sigs {
    block(width: 100%, inset: (x: 6pt, y: 3pt),
          stroke: 0.5pt + luma(180))[#raw(s.at(1))]
    v(0.3em)
  }
}

// tmr hides the editorial unless show_solutions=true is passed; we have
// no such switch here, so it is always shown.
#let editorial(body) = {
  heading(level: 1, numbering: none)[Editorial]
  body
}
