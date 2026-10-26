// Typst functions of the lg template (mirrors contestheader.tex).
// Embedded into taskinfo.typ after all generated data, so the functions
// can refer to taskinfo's definitions in their scope.

#let highlightcolor = rgb("#c20e1a")

// Semantic helpers so statements stay free of styling numbers (mirrors the
// official IOI typst template's philosophy: statements are pure semantics).
// TeX statements write `{\LARGE\bfseries \taskname}` and an explicit
// `\vspace{1em}` on top of `\parskip=\smallskipamount`; typst has no
// additive par glue, so the absorbed total is defined once here and
// statements only call `#tasktitle[...]` / `#sep`.
#let tasktitle(body) = text(size: 1.4em, weight: "bold")[#body]
#let sep = v(1.45em)

#let taskheader(body) = {
  // Fira Sans text + Fira Math, mirroring the latex template.
  set text(font: "Fira Sans", size: 10pt)
  // NOTE: `set math(font:)` inside a function body is rejected by the
  // trimmed typst binary ("expected function, found module"); setting the
  // text font on equations achieves the same (math picks up the family's
  // OpenType MATH table).
  show math.equation: set text(font: "Fira Math")
  set par(spacing: 0.5em, justify: true)
  set par(first-line-indent: 0em)
  set heading(numbering: none, supplement: none)
  // NOTE: the trimmed binary rejects heading above/below overrides; the
  // heading's built-in spacing is used as-is (same for every heading,
  // including Samples and Limits, so their above-gaps match by structure).
  // The trimmed typst binary ignores above/below spacing on blocks around
  // headings; explicit v() skips restore the latex template's rhythm.
  show heading: it => {
    v(if it.level == 1 { 1.2em } else { 0.9em })
    it
    v(0.45em)
  }
  show raw: set text(font: "Fira Mono", size: 9pt)
  set page(
    paper: "a4",
    margin: (left: 2.5cm, right: 2.5cm, top: 3.25cm, bottom: 1.5cm),
    header: context align(right)[
      // Fixed-height box pins the header bottom to match the TeX
      // reference (ink bottom ~74pt from page top); v(1fr) pushes the
      // grid down inside it (grid align inside the header is unreliable
      // in the trimmed binary).
      #box(height: 65pt)[
        #v(1fr)
        #grid(
          columns: (auto, 1pt, auto),
          // gaps measured from the TeX render: logo->bar ~13pt,
          // bar->text ~1em (tikz outer xsep)
          column-gutter: (13pt, 1em),
          inset: 0pt,
          align: horizon,
          // NOTE: scale() inside a header grid cell gets applied twice
          // (image is fitted to the cell first); set the width directly.
          if lg-logo != none { image("logo-typst.pdf", width: 44.1pt) },
          box(width: 100%, height: 2.9em, fill: highlightcolor),
          text(fill: luma(102), size: 10pt)[
            // paragraph line breaks give the same leading as TeX's \\
            #align(start)[
              #text(weight: "bold")[#contestname]\
              #t-task:#h(0.5em)#text(weight: "bold")[#taskname]
            ]
          ],
        )
      ]
    ],
    footer: context {
      // NOTE: do not raise the footer with v() — negative skips here
      // overflow the footer box and collide with full pages (e.g. the
      // sample table reaching the bottom margin).
      align(center)[
        #counter(page).at(here()).first()/#counter(page).final().first()
      ]
    },
  )
  set list(marker: box(width: 4pt, height: 4pt, fill: highlightcolor))
  body
}

// Fancy testcase table: the box wraps ONLY the header row (like TeX's
// \hline above/below the header with | at the outer column edges), an
// empty spacer column between Input and Output, and gray-filled sample
// cells (mirrors mktestcasetable / \cellcolor[gray]{.9}). The trimmed
// typst binary draws stroke dicts on table cells as FULL outlines, so
// the header rules are strokes on the header cell blocks themselves.
#let testcasetable() = {
  // raw blocks have their own padding by default; drop it so the cell
  // inset alone controls the text padding (like verbatim in latex).
  show raw: set block(inset: 0pt)
  table(
    // gray cells fill to the margins, gap between them == vertical
    // row gutter (3.3pt), centered by the symmetric 1fr columns
    columns: (1fr, 3.3pt, 1fr),
    inset: 0pt,
    row-gutter: 3.3pt,
    stroke: none,
    fill: (x, y) => if y > 0 and x != 1 { luma(229) },
    table.header(
      block(width: 100%, inset: (x: 4pt, y: 3pt),
            stroke: (top: 0.5pt + black, bottom: 0.5pt + black,
                    left: 0.5pt + black))[#align(center)[#text(font: "Fira Sans", weight: "regular")[#t-input]]],
      // spacer header cell: nbsp keeps its height in sync with the labels
      block(width: 100%, inset: (x: 4pt, y: 3pt),
            stroke: (top: 0.5pt + black, bottom: 0.5pt + black))[#text(size: 10pt)[#sym.space.nobreak]],
      block(width: 100%, inset: (x: 4pt, y: 3pt),
            stroke: (top: 0.5pt + black, bottom: 0.5pt + black,
                    right: 0.5pt + black))[#align(center)[#text(font: "Fira Sans", weight: "regular")[#t-output]]],
    ),
    ..{
      for i in range(numsamples) {
        (
          // box() makes the cell atomic so an input/output pair never
          // splits across pages (the trimmed binary rejects block
          // breakable:/blocked: arguments)
          box(block(width: 100%, inset: (x: 4pt, y: 5pt))[#{tc-in.at(i)}]),
          [],
          box(block(width: 100%, inset: (x: 4pt, y: 5pt))[#{tc-out.at(i)}]),
        )
      }
    },
  )
}

#let showcases() = {
  // TeX: caption is a \subsection* in the longtable firsthead with
  // LTpre=0pt and no \bigskip in \showcases, so the space above
  // "Samples" equals the space above any other heading (e.g. Limits).
  heading(level: 2, numbering: none)[
    #(if numsamples == 1 { t-sample } else { t-samples })
  ]
  testcasetable()
}

#let showlimits() = {
  heading(level: 2, numbering: none)[#t-limits]
  // paragraph line breaks (natural leading) match TeX's \\
  align(start)[
    #t-time: #timelimit\
    #t-memory: #memlimit
  ]
}

#let standardpart() = {
  showcases()
  showlimits()
}

// Subtask headings with hanging layout (mirrors \subtask/\sthelper)
#let subtask(body) = {
  sub-counter.step()
  context {
    let n = sub-counter.get().first()
    let pts = subtaskpoints(n)
    let unit = if pts == "1" { t-point } else { t-points }
    // Run-in label, like \st@sk in the lg template: bold label, then body;
    // continuation lines get a hanging indent so they align under the body.
    // (block above/below spacing is ignored by the trimmed binary -> v())
    v(0.7em)
    block({
      set par(hanging-indent: 4.2em, first-line-indent: 0em)
      text(weight: "bold", [#t-subtask #n (#pts #unit).])
      h(0.5em)
      body
    })
  }
}
