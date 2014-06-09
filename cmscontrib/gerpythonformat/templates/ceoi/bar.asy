import palette;
import info;

// Pythagoras and Euclid have been here
real a = 4cm, b = 1.2cm;
real c = sqrt(a*a + b*b);
real p = a^2 / c;
real q = b^2 / c;
real h = sqrt(p * q);

pair P = 2 * (p,h);
pair V = unit(P);
pair W = 5cm*(-V.y, V.x);
pair C = .5P + .5W;
path rect = (0,0)--P--(P+W)--(W)--cycle;

pen lightor = (188/255)*red + (209/255)*green + (228/255)*blue;
pen orange = (82/255)*red + (151/255)*green + (192/255)*blue;

real f(real x, real y) { return (length((x,y)-C))**.75; }
pen []pal = Gradient(NColors=700 ... new pen[]{white,lightor,orange,orange});
pair initial = (2W.x,0), final = (P.x-W.x,P.y+W.y);
image(f, initial, final, pal, antialias = true,nx=300,ny=300);

clip(rect);
draw(rect, dashed);

usepackage("fontenc", "T1");
usepackage("libertine");
defaultpen(fontsize(10pt));
//label("\sffamily\bfseries " + lg, 12pt * (unit(P) + 3*unit(W)) - (1.5pt,3pt), (18/255)*green + (98/255)*blue, align = N+E);
