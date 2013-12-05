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
pair W = 2.4cm*(-V.y, V.x);
pair C = .5P + .5W;
path rect = (0,0)--P--(P+W)--(W)--cycle;

pen lightor = (244/255)+red + (159/255)*green + (102/255)*blue;
pen orange = (234/255)*red + (96/255)*green + (21/255)*blue;

real f(real x, real y) { return (length((x,y)-C))**.75; }
pen []pal = Gradient(NColors=700 ... new pen[]{white,lightor,orange, orange}); 
pair initial = (2W.x,0), final = (P.x-W.x,P.y+W.y);
image(f, initial, final, pal, antialias = true,nx=300,ny=300);

clip(rect);
draw(rect, dashed);

usepackage("fontenc", "T1");
usepackage("libertine");
defaultpen(fontsize(10pt));
label(rotate(angle(P)/3.1415926*180)*Label("\sffamily\bfseries" + lg), 12pt * (unit(P) + unit(W)), align = unit(P));
