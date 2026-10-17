// Plain template header for typst statements.
// Mirrors header.tex as closely as reasonably possible.

// A small helper to typeset numbers like siunitx would (with a thin space
// between digit groups and an optional decimal comma).
#let si(x, unit, decimal-comma: false) = {
  let s = str(x)
  if decimal-comma {
    s = s.replace(".", ",")
  }
  [#s\ #unit]
}

#let basicheader(body) = {
  set page(
    paper: "a4",
    margin: (left: 2.5cm, right: 2.5cm, top: 3.25cm, bottom: 1.5cm),
    footer: context align(center)[
      #text(weight: "bold")[
        #counter(page).at(here()).first()/
        #counter(page).final().first()
      ]
    ],
  )
  set par(spacing: 0.5em, justify: true)
  set par(first-line-indent: 0em)
  set heading(numbering: none, supplement: none)
  body
}

// \heading / \sheading
#let headingx(title) = heading(level: 1, title)
#let sheading(title) = heading(level: 2, title)

// Semantic helpers (see LgTemplate.py): keep styling numbers out of the
// statements. `sep` mirrors TeX's `\vspace{1em}` on top of
// `\parskip=\smallskipamount` (typst par glue is not additive).
#let tasktitle(body) = text(size: 1.4em, weight: "bold")[#body]
#let sep = v(1.45em)
