import info;
import lgstyle;

pair P = (350.794, 102.062);
pair Q = (-P.y, P.x);

label(graphic("logo.eps", "scale=0.55"), (0,0), N+E);

label(rotate(angle(P)/3.1415926*180)*Label("\bfseries " + lg), 68pt * unit(P) + 25pt * unit(Q), align = unit(P), darkgray);
label(rotate(angle(P)/3.1415926*180)*Label("Aufgabe:\enspace\bfseries " + taskname), 68pt * unit(P) + 12pt * unit(Q), align = unit(P), darkgray);
clip(scale(7.5cm)*unitsquare);
