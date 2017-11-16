pen darkgray = .4 * white;
pen lightgray = .8 * white;
pen highlight = .761 * red + .055 * green + .102 * blue;

usepackage("FiraSans", "sfdefault,tabular,lining,scaled=.9");
usepackage("mathastext", "italic,nolessnomore,noplusnominus,noequal");

texpreamble("\makeatletter
\count1=\the\catcode`\.
\catcode`\.=11
\let\ver@FiraSans.sty = \undefined
\let\opt@FiraSans.sty = \undefined
\let\FiraSans@scale = \undefined
\let\FiraSansOT@scale = \undefined
\catcode`\.=\count1
\makeatother");

usepackage("FiraSans", "sfdefault,tabular,scaled=.9");
usepackage("fontenc", "T1");
defaultpen(fontsize(10pt));
