German System Info
******************
Für neue (und auch für alte) Coaches sind hier einige technische Informationen zu unserem Wettbewerbssystem aufgelistet.

Zugriff auf den Wettbewerbsserver
=================================
Um Zugriff auf den Wettbewerbsserver zu bekommen, musst du einem Coach deinen öffentlichen SSH-Schlüssel schicken.

Den SSH-Schlüssel kann dieser unter ``/root/.ssh/authorized_keys`` und ``/home/cms/.ssh/authorized_keys`` hinzufügen.

Du solltest dich jetzt per ``ssh cms@contest.informatik-olympiade.de`` auf dem
Server einloggen können.
Wenn du dann ``tmux a`` ausführst, kannst du etwaige dort laufende shells
bewundern. (``Strg-b``, dann eine Ziffer wechelt den Tab; mit ``Strg-b``, dann ``d``
kommst du wieder raus)

Mit ``git clone cms@contest.informatik-olympiade.de:aioi.git`` kannst du das
Aufgabenrepository auf deinen Rechner bekommen. (Siehe z.B. die git-
Dokumentation unter `<https://git-scm.com/book/en/v2>`_.)

Mit ``git clone --recursive https://github.com/ioi-germany/cms.git`` bekommst du
den deutschen Fork des CMS. (Wenn du einen Github-Account hast, kannst du einem der Coaches
auch mal deinen Usernamen schicken, damit du auch selbst Änderungen am CMS
hochladen kannst.)

Dann bitte die Dokumentation `hier <https://contest.informatik-olympiade.de/docs/>`_ (das heißt, hier) lesen und die Installationshinweise befolgen.
Wichtig ist insbesondere `die Beschreibung des deutschen Aufgabenformates <https://contest.informatik-olympiade.de/docs/External%20contest%20formats.html#german-import-format>`_.
Führe testweise einfach mal ``cmsGerMake .`` zum Beispiel im Ordner ``contests/ioi2017_training1`` aus.

Richte auf jeden Fall auf dem eigenen Computer :ref:`eine Firewall ein <installation_security>`!

.. warning::

  CMS funktioniert nur mit manchen Versionen von Python und manchen Versionen bestimmter Python-Pakete. Damit sich keine falschen Versionen einschleichen, führen wir es (jedenfalls auf dem Server) in einer virtuellen Umgebung (``venv``) aus. Auf dem Server muss dazu das Kommando ``prep`` in jeder neu geöffneten shell ausgeführt werden, bevor ein CMS-Kommando verwendet wird; mit ``deactivate`` verlässt man ``venv`` wieder (üblicherweise nicht nötig).

  Auf anderen Rechnern sind auch häufig inkompatible Versionen installiert. Dann muss man dort auch ein ``venv`` einrichten; siehe auch :ref:`hier <installation_venv>` für Details zu ``venv``. U.U. scheitert sonst die Installation der in ``requirements.txt`` festgelegten Python-Pakete oder es treten Fehler beim Ausführen von CMS auf.

Um auf dem Server mit dem Aufgabenrepository zu arbeiten (z.B. einen Contest zu kompilieren oder zu importieren), verwenden wir dort den Ordner ``aioi_repo`` (dieser folgt ``aioi.git``, mit ``git pull`` bekommt man also den "aktuellen Stand").

Webseiten des Wettbewerbssystems
================================
Die Zugangsdaten für die folgenden Webseiten erhältst du von einem der Coaches -- oder findest sie in der Konfiguration auf dem Server.

Hier sind die internen Interfaces des Wettbewerbssystems (Zugangsdaten A):

- `<https://contest.informatik-olympiade.de/admin/>`_
- `<https://contest.informatik-olympiade.de/taskoverview/>`_
- `<https://contest.informatik-olympiade.de/ranking/Ranking.html>`_

Das Teilnehmerinterface kann mit einem Testaccount (Zugangsdaten B) unter der folgenden Adresse aufgerufen werden:

- `<https://contest.informatik-olympiade.de/>`_

Technische Informationen
========================
Auf unserem Server ist das CMS grundsätzlich in systemd-Services integriert, die ``enabled`` sind. Das bedeutet insbesondere, dass das CMS bei jedem Start des Servers automatisch gestartet wird (der Log-Service immer zuerst).

====================  ===========
systemd-Service       CMS-Service
====================  ===========
``cms-log``           ``cmsLogService``
``cms-resource``      ``cmsResourceService -a $CONTEST_ID``
``cms-ranking``       ``cmsRankingWebServer``
``cms-taskoverview``  ``cmsTaskOverviewWebServer``
====================  ===========

Gestoppt bzw. (neu) gestartet wird ein Service mit ``sudo systemctl [stop|restart] cms-[log|resource|ranking|taskoverview]``. (Tab Completion funktioniert.)
Den Status und Logs bekommt man mit ``sudo systemctl status cms-[log|resource|ranking|taskoverview] -ocat``.

Welcher Contest auf dem Server läuft, wird durch ``CONTEST_ID`` in ``/home/cms/resource-service.conf`` definiert. Sollen alle importierten Contests laufen, muss in der Datei ``CONTEST_ID=ALL`` stehen. Will man nur einen einzelnen starten, muss dort statt ``ALL`` die ID des Contests stehen. (Wenn man die ID nicht weiß: Manuell ``prep`` und ``cmsResourceService -a`` ausführen, mit ``Strg+C`` abbrechen, aus der angezeigten Liste der importierten Contests ablesen. Nicht mit der Zeilennummer verwechseln!)
Sobald man die ``resource-service.conf`` geändert hat: Service mit ``sudo systemctl restart cms-resource`` neustarten.


Telegram-Bot
============
Clarification requests can be seen and answered and announcements be made via a telegram bot, providing easy and prompt access to what you regularly need during a contest and notifying you whenever a contestant needs help!

The following is the bot's self-specification containing a list of commands available:

.. sourcecode:: text

    A bot allowing to access clarification requests and announcements
    of a CMS contest via Telegram.

    /start 〈pwd〉 — tries to bind the bot to the current chat when
    used with the correct password; the bot can only be bound to a
    single chat at a time and all further binding attempts will be
    rejected until the bot service has been restarted
    /announce — adds the rest of the message as an announcement to
    the current contest; everything before the first line break will
    be used as header
    /openquestions — shows all unanswered questions of the current
    contest
    /allquestions — shows all questions of the current contest
    (use this with care as it tends to produce quite a lot of output!)
    /allannouncements — shows all announcements of the current contest
    (use this with care as it could produce quite a lot of output)
    /help — prints this message
    /purge — deletes all messages sent by the bot during the current
    session (standard restrictions apply: no messages older than 48h
    will be deleted)

    In addition this bot will post all new questions appearing in the
    system. You can answer them by replying to the corresponding post
    or using the respective inline buttons. Moreover, all answers
    given and announcements made via the web interface will also
    be posted and you can edit answers by replying to
    the corresponding message


Constraints
===========
Die Limits für die einzelnen Teilaufgaben sowie die globalen Limits sollte man *nicht* in Aufgabenstellung und Checker einzeln hardcoden, sondern einzig und allein in die ``config.py``-Datei schreiben. Dazu steht der Befehl ``constraint`` zur Verfügung, dessen Syntax unten erläutert wird. Die Semantik ist hingegen die folgende: ein Constraint legt für eine *Variable* optional obere und untere Schranken fest. Diese Schranken sind (beliebig große) ganze Zahlen. Constraints sind kumulativ, was auch oft genutzt wird: hat man z.B. eine Aufgabe, bei der in allen Testfällen 1 ≤ N ≤ 1000 garantiert ist und in einer Teilaufgabe N ≤ 100, so würde man den ersten Constraint global festlegen und den zweiten in der entsprechenden Teilaufgabe. Während im Aufgabenstatement für die entsprechende Teilaufgabe tatsächlich nur N ≤ 100 abgedruckt würde, würde der Checker trotzdem auch 1 ≤ N überprüfen. Beachte allerdings, dass die Bedingung N ≤ 100 *nur für die entsprechende Teilaufgabe* gilt, nicht für die nächste – aber das ist ja auch das, was man haben möchte.

Zur Syntax: Constraints werden mit dem Befehl ``constraint`` erzeugt. Dieser kann global (d.h. außerhalb aller ``with subtask``-Blocks von ``config.py``) oder für eine Teilaufgabe (dementsprechend in ihrem entsprechenden ``with subtask``-Block) hinzugefügt werden. Manchmal möchte man einen Constraint *stumm* stellen. Dieser taucht dann nicht automatisch im Statement auf, sondern nur, wenn man ihn explizit abfragt. Das kann man erreichen, indem man den Schlüsselwortparameter ``silent`` auf ``True`` setzt. Dieser Mechanismus ist besonders hilfreich, um irgendwelche aufgabenspezifischen Konstanten zu spezifizieren.

Der Befehl ``constraint`` erwartet als Argument einen String, der eine durch Kommata getrennte Liste von *Constraints* enthält, wobei ein Constraint wiederum die folgende Syntax benutzt:

.. sourcecode:: text

    [Durch Kommata getrennte Liste von Variablen]: [Beschreibung der zulässigen Werte]

Eine *Variable* wird dabei wie folgt beschrieben: zunächst der Name der Variable, dann *optional* in Klammern eingeschlossen TeX-Code, der angibt, wie diese Variable in der Aufgabenstellung gesetzt werden soll (ansonsten wird hierfür der Name selbst als TeX-Code interpretiert). Setzt man den TeX-Code global, wird derselbe Code auch für die entsprechenden Teilaufgaben verwendet, sofern man dort selbst nicht anderen Code dafür spezifiziert. Das ist auch der Grund, warum dieses Feature überhaupt hilfreich sein kann: ist der TeX-Code aufwendig, muss man ihn trotzdem nur einmal spezifizieren (außerdem müsste man bei Layout-Änderungen diese nur an einer Stelle vornehmen). Leerraum um Variablennamen oder TeX-Code wird standardmäßig ignoriert; möchte man ihn aus irgendwelchen Gründen trotzdem verwenden, kann man wieder die Variante mit Anführungszeichen verwenden.

Beachte, dass aus technischen Gründen weder Name noch TeX-Code weder öffnende oder schließende runde oder eckige Klammern enthalten dürfen noch Kommata, einen Doppelpunkt oder normale Anführungszeichen ``"``. Möchte man irgendwelche dieser Zeichen außer dem Anführungszeichen verwenden, kann man den entsprechenden Teil in Anführungszeichen einschließen. Hier sind ein paar Beispiele für gültige Variablendefitionen:

.. sourcecode:: text

    dij("d_{i,j}")
    "d_{i,j}"
    sum l_i(\ell_1+\cdots+\ell_k)
    \ell_1+\cdots+\ell_k

Die ersten beiden Beispiele und die letzten beiden werden im Statement jeweils gleich gesetzt. Ich würde im ersten Fall vermutlich die erste Notation verwenden und im zweiten die zweite.

Die folgenden Beispiele wären hingegen *nicht* zulässig:

.. sourcecode:: text

    d_{i,j}
    (x_1-y_1)(x_2-y_2)
    diffprod((x_1-y_2)(x_2-y_2))

Im ersten Beispiel würde dies als zwei getrennte Variablen ``d_{i`` und ``j}`` interpretiert; der Constraint-Parser selbst würde sich dementsprechend auch gar nicht beschweren, aber es würde evtl. ungültiger TeX-Code erzeugt. Im zweiten und dritten Beispiel würden die Klammern jeweils als Zeichen, dass eine Spezifikation von TeX-Code folgt, interpretiert werden und der Parser würde sich beschweren.

Die Schranken werden in der Form ``[untere Schranke, obere Schranke]`` spezifiziert. Hierbei gilt für ``untere Schranke`` und ``obere Schranke`` dieselbe Syntax wie für Variablennamen: man spezifiziert den Wert (üblicherweise als Ziffernfolge) und optional in Klammern TeX-Code, wie die entsprechende Schranke gesetzt werden soll. Hierbei gelten auch wieder die Einschränkungen zu besonderen Zeichen und man kann wieder auf ``"`` zurückgreifen, um diese zu umgehen. Wird kein TeX-Code spezifiziert, wird die entsprechende Schranke automatisch schön gesetzt: Lange Zahlen werden in Ziffernblöcke mit kleinem Leerraum dazwischen aufgeteilt.

Möchte man nur untere oder nur obere Schranke verwenden, kann man die entsprechende andere Grenze einfach weglassen. Die folgenden Beispiele wären also alle zulässig:

.. sourcecode:: text

    N: [,100000]
    N: [3,]
    N: [3,100000]

Im Fall, dass obere und untere Schranke übereinstimmen, kann man das Komma (und auch die eckigen Klammern nach Wunsch) einfach weglassen:

.. sourcecode:: text

    N: [42,42]
    N: [42]
    N: 42

wären alle zulässig und haben denselben Effekt. Natürlich sind die beiden unteren Notationen zu empfehlen (besonders, wenn der entsprechende Wert komplizierter ist oder man TeX-Code spezifizieren möchte...).

Oft hilfreich in der Praxis: In einem begrenzten Umfang ist auch für den Wert selbst TeX-Code zulässig. Dieser wird dann automatisch (wenn auch etwas heuristisch) in Python-Code umgewandelt, der dann wiederum ausgewertet wird, um eine Zahl zu erhalten. Damit ist einfache Arithmetik möglich. Zulässig und korrekt interpretiert würden z.B.

.. sourcecode:: text

    10^{15}
    5\cdot 10^8
    1+2+3+4
    4/2

Nicht erlaubt wären hingegen z.B.

.. sourcecode:: text

    1/2
    \frac{4}{2}
    {4\over2}
    {5\choose 2}

Im ersten Fall haben wir das Problem, dass 1/2 keine ganze Zahl ist, in den anderen schlägt schon das Parsen fehl. In diesen (sehr exotischen) letzten drei Fällen würde es sich empfehlen, den entsprechenden Wert in config.py auszurechnen und die Formel als TeX-Code zu spezifizieren.

Damit ist die Beschreibung des Formats abgeschlossen und die Interpretation als abstrakter Constraint (für den Checker) sollte hinreichend klar sein. Die folgenden Beispiele zeigen noch, wie die Darstellung in TeX aussehen würde:

* ``constraint("N: [,1000]")`` erzeugt den TeX-Code ``$N\le 1000$``
* ``constraint("M,N: [1,4]")`` erzeugt den TeX-Code ``$1\le M,N\le 4$``
* ``constraint("M: [1,4], N: [1,4]")`` erzeugt den TeX-Code ``$1\le M\le 4,1\le N\le 4$``
* ``constraint("A,B: 1")`` erzeugt den TeX-Code ``$A=B=1$``
* ``constraint("A: 1, N: [,1000]")`` erzeugt den TeX-Code ``$A=1, N\le 1000$``
* ``constraint("X: 3000", silent=True)`` erzeugt gar keinen TeX-Code (s.o.)

Natürlich muss man die spezifizierten Constraints auch in Statement und Checker wieder abfragen. Das wird jetzt erklärt:

Constraints im Checker verwenden
--------------------------------

Möchte man die Constraints für seinen Checker verwenden (und das sollte man!), muss man *vor* ``#include<checkframework.h>`` noch ``#include"constraints.h"`` hinzufügen. (Führt man den Checker aus, wird man dann mit einem ``Constraints loaded`` begrüßt.)

In den meisten Fällen benutzt man die Constraints automatisch mit den Methoden des globalen ``token_stream``-Objekts ``t``, das man zum Parsen der Eingabedatei verwendet. Genauer verwendet man fast immer die Methode ``parse_and_auto_check<Typ>(Name, nächster Whitespace)``: Ist ``Name`` der Name einer Variable, die mit dem Constraint-System definiert wurde, prüft das automatisch, ob:

* obere und untere Schranke (sofern vorhanden) sowie das tatsächliche Eingabetoken im Datentyp ``Typ`` gespeichert werden können (``Typ`` sollte irgendein ganzzahliger Typ sein)
* ob die Zahl in der Eingabe die spezifizierten Beschränkungen erfüllt

Neben den Standardtypen ist dabei auch ``big_int`` (für beliebig lange ganze Zahlen) als Wert für ``Typ`` zulässig.

Es gibt alternativ auch die Möglichkeit, irgendeine Zahl (z.B. eine, die sich per Rechnung aus der Eingabe ergibt), anhand der Constraints zu überprüfen. Dazu verwendet man ``auto_check_bounds<Typ>(Name, zu prüfender Wert)``. Schließlich besteht die Möglichkeit, die Schranken eines Constraints selbst abzufragen. Die grundlegende Funktion dazu ist ``get_constraint<Typ>(Name)``, welche ein Paar von ``my_optional<Typ>`` zurückgibt, wobei ``my_optional`` eine sehr primitive Implementierung von C++17-``optional`` ist. Das prüft auch direkt, ob die Schranken in den Typ ``Typ`` passen. Möchte man nur eine der beiden Schranken, kann man ``get_constraint_lower<Typ>(Name)`` bzw. ``get_constraint_upper<Typ>(Name)`` verwenden. Diese geben einfach ein Element vom Typ ``Typ`` zurück und prüfen auch gleich, ob die entsprechende Schranke nicht doch leer ist. Sind obere und untere Schranke auch noch identisch, steht schließlich der Befehl ``get_constraint_value<Typ>(Name)`` zur Verfügung.


Constraints im Statement
------------------------
Wie man Constraints im Statement verwendet, ist unten im Kapitel *Automatische Teile des Statements* erklärt.


Teilaufgaben mit Spezialfällen
------------------------------
Oft gibt es auch Teilaufgaben, in denen zwar die Limits genauso groß sind wie im Rest der Aufgabe, dafür aber die Eingabe auf irgendwelche Spezialfälle eingeschränkt wird; z.B. könnte es in einer Graphenaufgabe eine Teilaufgabe geben, in der die Eingabe ein Baum ist.

Um dies auf einfache und durchsichtige Weise zu bewerkstelligen, steht der Befehl ``special_case`` zur Verfügung, den man üblicherweise in einem ``with subtask``-Block aufruft. Dieser erwartet einfach nur einen String als Parameter und hat die Semantik *dieser Subtask gehört zu diesem Spezialfall*. Im obigen Beispiel würde man etwa ``special_case("tree")`` schreiben.

Die Überprüfung, ob dieser Spezialfall dann auch gilt, ist Aufgabe des Checkers. In jedem Checker, der wie oben beschrieben das Constraint-System lädt, steht der Befehl ``is_special_case`` zur Verfügung. Dieser erwartet wiederum nur einen String ``Fall`` als Parameter und gibt einen Boolean zurück: ob der entsprechende Testfall in einer Teilaufgabe verwendet wird, für die in ``config.py`` der Befehl ``special_case(Fall)`` ausgeführt wurde.

Als Alias für ``is_special_case`` steht auch ``ought_to_be`` zur Verfügung. Das typische Idiom wäre dann

.. sourcecode:: C++

    if(ought_to_be("tree"))
    {
        // prüfe, ob die Eingabe einen Baum spezifiziert
    }

Ich möchte ausdrücklich und wiederholt davon abraten, das alte Idiom eines Checkers ``chk``, der einen oder mehrere Integer auf der Kommandozeile erwartet und dann in jeder Teilaufgabe neu gesetzt wird (``checker(chk.p(1))`` o.ä.), zu verwenden!

Aktuell hat ``special_case`` keinerlei Auswirkung auf das TeX-Statement, da mir keine Lösung einfällt, die das sinnvoll mit der Möglichkeit verschiedener Sprachen (z.B. bei Olympiaden) in Einklang bringt.


Automatische Teile des Statements
=================================
Viele Teile der Struktur einer Aufgabe, die in der ``config.py``-Datei spezifiziert werden, möchte man auch im Statement wiederholen. Dazu gehören insbesondere die Limits für Zeit und Speicher oder die Beschränkungen für die Eingabe. Wenn man an irgendetwas rumschraubt (z.B. weil der Server langsamer ist als der eigene Rechner), möchte man diese natürlich nicht an allen möglichen Stellen ändern, sondern am besten nur an einer: der ``config.py``-Datei selbst. Unser Aufgabensystem hat mehrere Features, die dabei helfen, solche Redundanzen zu vermeiden, und die man *unbedingt* nutzen sollte. Ein Beispiel dafür ist das ``constraint``-System, das wegen seiner eigenen Syntax oben bereits diskutiert wurde und auf das wir unten noch einmal zu sprechen kommen.


Teilaufgaben
------------
Quasi alle Aufgaben bestehen aus mehreren Teilaufgaben. Dazu erstellt man üblicherweise einen Abschnitt *Beschränkungen*, in dem zunächst die globalen Constraints geschildert werden ("Stets gilt 1 ≤ N ≤ 1000", mehr dazu gleich) und dann die einzelnen Teilaufgaben gelistet werden. Für jede dieser Teilaufgaben ruft man das Makro ``\subtask`` auf. Dieses zählt automatisch einen Zähler, um die wievielte Teilaufgabe es sich handelt hoch, und fügt die Zwischenüberschrift ``Teilaufgabe <Nummer> (<Punkte> Punkte).`` hinzu; die Punktzahl für die Teilaufgabe wird dabei automatisch aus der ``config.py`` übernommen. Danach kann man im Freitext die Beschränkungen dieser Teilaufgabe beschreiben, also z.B.

.. sourcecode:: TeX

    \section*{Beschränkungen}
    Stets gilt $M,N\le 100\,000$. % Das sollte man eigentlich nicht ins Statement hardcoden, s.u.

    \subtask Zwei Knoten $i,j$ sind genau dann direkt verbunden, wenn $|i-j|=1$.
    \subtask $M=N-1$
    \subtask Keine weiteren Beschränkungen.

Es gibt eine Fehlermeldung, wenn ``\subtask`` nicht genauso oft aufgerufen wird, wie es (nicht-öffentliche) Subtasks gibt. Möchte man aus irgendeinem Grund ``\subtask`` weniger oft aufrufen, muss man irgendwann nach dem letzten Aufruf von ``\subtask`` den Befehl ``\flushsubtasks`` einfügen.

Der alte Befehl ``\st``, dem man als Parameter die Punktzahl für die entsprechende Teilaufgabe übergeben muss, ist als *deprecated* anzusehen. Er wird also nicht empfohlen und eventuell bald entfernt.

Constraints
-----------
Wie bereits erwähnt, besteht die Möglichkeit, vom Statement aus auf die Constraints zuzugreifen, und man sollte dringend davon Gebrauch machen.

Die Makros, welche üblicherweise die Ausgabe der Constraints übernehmen, lauten ``\currconstraint#1``, ``\currconstraints`` und ``\currconstraints*`` (das ``curr`` steht für *current*). Ihre Semantik hängt dabei jeweils davon ab, wo im Programm sie aufgerufen werden:

* Benutzt man den entsprechenden Befehl vor irgendeinem Aufruf von ``\subtask``, bezieht sich der Befehl auf die globalen Constraints.
* Benutzt man den Befehl nach insgesamt *k* Aufrufen von ``\subtask`` bezieht sich der Befehl auf die Constraints in Teilaufgabe *k*.

Sowohl ``\currconstraints`` als auch ``\currconstraints*`` erwarten keine Parameter und geben alle Constraints des jeweiligen Subtasks (bzw. alle globalen Constraints) aus. Hierbei trennt ``\currconstraints`` diese einfach nur durch Kommata, während ``\currconstraint`` stattdessen den letzten Eintrag mit *und* abtrennt (bei einer englischsprachigen Aufgabenstellung wird dementsprechend *and* verwendet; das Oxford-Komma wird gesetzt). In einer idealen Welt sieht der Beschränkungen-Abschnitt also einfach nur so aus:

.. sourcecode:: TeX

    \section*{Beschränkungen}
    Stets gilt \currconstraints. % In Fließtext möchte man den üblichen Konventionen für Aufzählungen folgen

    \subtask \currconstraints*   % Wenn nur die Ungleichungen aufgelistet werden, sind Kommata schöner
    \subtask \currconstraints*
    \subtask Keine weiteren Beschränkungen.

In manchen Fällen möchte man nicht alle Constraints, sondern nur einen einzigen ausgeben. Dazu steht der Befehl ``\currconstraint`` zur Verfügung. Dieser erwartet als Parameter eine durch Kommata getrennte Liste von Variablennamen; *Leerzeichen vor oder nach den Kommata sind nicht erlaubt* (wohl aber als Teil von Variablennamen). Wichtig ist, dass es sich hierbei um einen einzigen Constraint handeln muss; nach

.. sourcecode:: Python

    constraint("N,M: [,10000]")
    constraint("A, [,10000], B: [,10000]")

wären die folgenden Aufrufe erlaubt:

.. sourcecode:: TeX

    \currconstraint{N}    % Ausgabe ist $N\le 10\,000$
    \currconstraint{M}    % Ausgabe ist $M\le 10\,000$
    \currconstraint{N,M}  % Ausgabe ist $N,M\le 10\,000$
    \currconstraint{M,N}  % Ausgabe ist $M,N\le 10\,000$
    \currconstraint{A}    % Ausgabe ist $A\le 10\,000$
    \currconstraint{B}    % Ausgabe ist $B\le 10\,000$

Nicht erlaubt wären hingegen:

.. sourcecode:: TeX

    \currconstraint{N, M} % Leerzeichen!
    \currconstraint{A,B}  % A und B zählen als unterschiedliche Constraints

Die Leerzeicheneinschränkung könnte später fallengelassen werden (dazu müsste man echtes Argumentparsing auf der TeX-Seite implementieren), die Einschränkung in Bezug auf Constraints ist Teil des Designs.

Schließlich gibt es auch noch die Möglichkeit, auf die Schranken eines Constraints einzeln zuzugreifen; die entsprechenden Makros lauten ``\currconstraintupper``, ``\currconstraintlower``  und ``\currconstraintvalue``. Wie bei ``\currconstraint`` erwarten diese als Parameter den entsprechenden Variablennamen; dabei darf es sich aber nur um eine einzige Variable und nicht um eine Liste handeln; alles andere ergäbe aber auch keinen Sinn. Diese Makros prüfen nicht extra, ob die entsprechenden Grenzen definiert sind (und im Falle von ``\currconstraintvalue`` übereinstimmen), sondern sind andernfalls einfach nicht definiert. Die typische Verwendung sind *stumme Constraints* (s.o.), um z.B. eine aufgabenweite Konstante zu definieren, ein Beispiel wäre folgender Python-Code

.. sourcecode:: Python

    constraint("max_n: [,30000]", silent=True)
    constraint("M: [1, 3000]")

und dem folgenden TeX-Code

.. sourcecode:: TeX

    Deine Lösung darf aus höchstens \currconstraintupper{max_n} Knoten bestehen.
    % Ausgabe: Deine Lösung darf aus höchstens $30\,000$ Knoten bestehen.

    % ...
    \section*{Beschränkungen}
    Stets gilt \currconstraints. % Ausgabe: Stets gilt $M\le 3\,000$.

Aus historischen Gründen gibt es noch das Makro ``\constraint``, das als Parameter den "Index" des Constraints erwartet; ``\constraint1`` würde also z.B. den ersten Constraint aus der ``config.py`` ausgeben. *Dieses Makro sollte man vermeiden, da das Hinzufügen neuer Constraints natürlich die ganze Nummerierung durcheinanderwerfen kann* und es gilt aus diesem Grund auch als *deprecated*.

Der Standardteil
----------------
Fast alle Aufgabenstellungen enden auf die gleiche Weise:

* Zunächst gibt es einen Abschnitt mit den Beispieltestfällen. Dazu kann man den Befehl ``\showcases`` verwenden, der überprüft, ob es mehr als einen öffentlichen Testfall gibt, dementsprechend die passende Überschrift für den Abschnitt wählt, und dann eine ``\longtable`` der Testfälle ausgibt. *Dieser Befehl ist nicht für interaktive Aufgaben geeignet, bei denen es wohl keine sinnvolle Alternative dazu gibt, die Kommunikation von Hand zu erstellen!*
* Daraufhin werden Speicher- und Zeitlimit ausgegeben. Dies kann einfach mit ``\showlimits`` geschehen.
* Ganz zum Schluss wird auf das Feedback hingewiesen (beachte, dass dies zum Zeitpunkt, an dem man die Aufgabe schreibt, eigentlich noch gar nicht feststeht, da er von der Verwendung der Aufgabe in ``contest-config.py`` abhängt!); dies geschieht mit ``\showfeedback``.

Da diese Befehle fast immer so aufgerufen werden, kann man stattdessen einfach ``\standardpart`` schreiben. Beachte aber, dass man die Makros einzeln aufrufen muss, wenn man z.B. erläuternde Worte zu einem der Beispieltestfälle hinzufügen möchte.


Graphdrawing
============
Unser System ist in der Lage, halbautomatisch Graphenbilder aus den meisten Eingabedateien zu erstellen. Dazu greift es auf TikZ' Fähigkeiten zurück, bietet aber ein für unsere Anwendungen optimiertes Interface und (hoffentlich) einige Layoutverbesserungen.


Welche Graphen können gezeichnet werden?
----------------------------------------
Es werden sowohl ungerichtete als auch gerichtete Graphen unterstützt, wobei die Indizierung der Knoten wahlweise bei 0 oder 1 beginnen kann. Mehrfachkanten sind zulässig; Schleifen werden allerdings leider noch nicht korrekt dargestellt.

Darüber hinaus unterstützt unser System:

* Kantengewichte
* Annotations (Zahlen, die als zusätzliche Labels neben der Knotennummer angezeigt werden)
* Knotenmarkierungen (besondere Styles, die zum Zeichnen der Knoten verwendet werden)


Graphenformat
-------------
Für eine Graphenspezifikation sind zwei Teile erforderlich: eine Datei, die den eigentlichen Graphen darstellt (z.B. eine der Beispieleingaben einer Aufgabe), sowie optional eine Liste von Flags und Parametern, die dem System mitteilen, wie es die Datei interpretieren soll.

Die möglichen Parameter sind im nächsten Abschnitt beschrieben:

Das erwartete Format der Graphendatei ist wie folgt (Teile in eckigen Klammern sind je nach überreichten Flags und Parametern optional):

.. sourcecode:: text

    [Ignorierter Teil]
    #Knoten [#Kanten]
    [Ignorierter Teil]
    [Mehrere Listen von Knoten, wobei Knoten auch mehrfach vorkommen dürfen; jede Gruppe wird später eine eigene Markierung bekommen]
    [Je eine Annotation pro Knoten]
    Für jede Kante: Startknoten Endknoten [Gewicht]
    [Ignorierter Teil]

Die Listen von Knoten müssen dabei jeweils das Format

.. sourcecode:: text

    #Knoten
    Liste der Knoten

verwenden (generell ist es egal, welche Art von Leerraum verwendet wird). Aktuell werden bis zu drei Markierungen (d.h. drei Listen von Knoten) unterstützt.

Im Moment kann das System nur mit Eingabedateien umgehen, die vollkommen aus Zahlen bestehen. Eventuell wird dies in der Zukunft auf ein Tokensystem umgestellt.

Da dies sehr allgemein ist, finden sich unten praktische Beispiele.

Die möglichen Flags, die das Parsen des Eingabegraphens beeinflussen, sind wie folgt:

* Standardmäßig werden die Graphen als ungerichtet interpretiert; dies kann geändert werden, indem man das Flag ``directed`` angibt.
* Die Indizierung der Knoten beginnt bei 1; dies kann geändert werden, indem man das Flag ``zero_based`` hinzufügt.
* Möchte man Kantengewichte verwenden, so ist das Flag ``weighted`` anzugeben.
* Möchte man Annotations verwenden, so ist dies mit dem Flag ``annotated`` anzukündigen.
* Standardmäßig werden keine Markierungen verwendet; möchte man hingegen *k* verschiedene Markierungen, so ist der Parameter ``markings`` auf den entsprechenden Wert zu setzen, also z.B. ``markings=4`` für vier Markierungen
* Im Falle eines Baumes ist es nicht nötig, dass die Eingabedatei die Anzahl der Kanten enthält; in diesem Fall muss man aber das Flag ``tree`` hinzufügen.
* Normalerweise beginnt das System direkt am Anfang der Datei mit dem Parsen. Möchte man hingegen die ersten *k* Zahlen in der Eingabe ignorieren, so ist ``skip_before`` auf den entsprechenden Wert zu setzen, also z.B. ``skip_before=1``, um die erste Zahl in der Eingabe zu überspringen
* Möchte man nach der Knoten- und (optional) Kantenanzahl *k* Zahlen überspringen, so ist ``skip`` entsprechend zu setzen. Ein klassisches Beispiel wäre eine Kürzeste-Wege-Aufgabe, bei der so Start und Ziel spezifiziert werden; hier würde man also ``skip=2`` übergeben.

Darüber hinaus gibt es noch weitere Parameter, welche die Darstellung des Graphens beeinflussen:

* Üblicherweise werden alle Kantenlabel horizontal platziert. Möchte man das ändern, so kann man ``follow_edges`` spezifizieren, was dazu führt, dass die Labels parallel zur Kante verlaufen. Dies ist im Grunde nur bei sehr langen Labels notwendig.
* Der Parameter ``node_distance`` kann spezifiziert werden, um den Abstand der einzelnen Knoten zu verändern. Der Effekt ist allerdings nur indirekt, denn er bestimmt den *Gleichgewichtszustand* einer isolierten Kante innerhalb des Graphdrawing-Algorithmus. Mit diesem Parameter sollte man spielen, wenn Knoten kollidieren (in diesem Fall sollte man ihn vergrößern), oder das Graphenbild unerwartet groß ist (dann sollte man ihn verkleinern). TikZ setzt diesen Parameter standardmäßig auf ca. 28,4 (1cm).
* Wenn der erzeugte Graph unschön ist, kann man versuchen, den Parameter ``random_seed`` auf einen, nun ja, zufälligen Wert zu setzen. Dieser bestimmt die Anfangsposition der Knoten im Graphdrawing-Algorithmus; TikZ setzt ihn standardmäßig auf 42.


Beispiele
---------
1. Ein ungewichteter Graph mit vier Knoten und fünf Kanten ließe sich z.B. wie folgt codieren (keine Parameter nötig):

    .. sourcecode:: text

        4 5
        1 2
        1 3
        2 3
        3 4
        4 1

2. Möchte man denselben Graphen als gerichteten Graphen interpretieren, so ist das Flag ``directed`` hinzuzufügen.

3. Wenn man ausdrücklich auf 0-Indizierung besteht, kann man nach Angabe des Flags ``zero_based`` stattdessen das Folgende verwenden:

     .. sourcecode:: text

        4 5
        0 1
        0 2
        1 2
        2 3
        3 0

4. Übergibt man das Flag ``weighted``, so würde die folgende Datei als ein (ungerichteter) gewichteter Graph mit vier Knoten und drei Kanten interpretiert:

    .. sourcecode:: text

        4 3
        1 2 42
        1 3 1337
        1 4 4711

5. Es wird komplizierter: die folgende Datei wäre eine gültige Codierung für denselben Graphen, wenn es zusätzlich Knotengewichte gibt (die Zahlen an den Knoten können natürlich auch eine andere Bedeutung als Gewichte haben...); hierzu ist neben ``weighted`` zusätzlich noch ``annotated`` anzugeben:

    .. sourcecode:: text

        4 3
        2
        4
        8
        16
        1 2 42
        1 3 1337
        1 4 4711

6. Spezifiziert man stattdessen ``weighted`` und ``skip=4`` würde diese Datei genauso interpretiert werden wie in Beispiel 4; hierbei würden die Zeilen 2 bis 5 als ``[Ignorierter Teil]`` anstatt als Annotations geparst werden.

7. Hier ist ein Beispiel mit zwei Arten von Knotenmarkierungen, wofür ``markings=2`` anzugeben ist. Knoten 1 und 2 tragen die erste Markierung, Knoten 1, 3 und 4 die zweite:

    .. sourcecode:: text

        4 4
        2 1 2
        3 1 3 4
        1 2
        2 3
        3 4
        4 1

8. Übergibt man das Flag ``tree`` (und natürlich ``weighted``), ließe sich Beispiel 3 auch wie folgt codieren:

    .. sourcecode:: text

        4
        1 2 42
        1 3 1337
        1 4 4711


Einfache Graphen zeichnen
-------------------------
In den meisten Fällen verwendet man dazu das TeX-Makro ``\drawgraph``; dieses erwartet als Parameter den Pfad zu der Eingabedatei (im Format wie oben), die gelesen werden soll, sowie optional in eckigen Klammern die Flags und Parameter wie oben beschrieben (in beliebiger Reihenfolge, durch Kommata getrennt, Leerzeichensindoptional). Zwei Beispiele:

1. Enthält ``1.in`` den Text aus dem ersten Beispiel oben, so würde ``\drawgraph{1.in}`` diesen zeichnen. Wäre die Datei in einem Unterordner ``inputs``, würde man stattdessen ``\drawgraph{inputs/1.in}`` verwenden.

2. Enthält ``8.in`` das allerletzte Beispiel oben, so würde ``\drawgraph[weighted,tree]{8.in}`` den entsprechenden Graphen zeichnen.

Auf oberster Ebene erzeugt ``\drawgraph`` ein ``tikzpicture``; für ein ansprechendes Layout sollte dieser Befehl also in eine geeignete LaTeX-Umgebung wie ``center`` oder ``wrapfigure`` gesteckt werden.


Fortgeschrittenes
-----------------
Für kompliziertere Graphen, bei denen man von Hand Veränderungen vornehmen möchte, steht die Umgebung ``graphpicture`` zur Verfügung. In dieser stehen die folgenden zusätzlichen Befehle zur Verfügung (viele weitere sollen folgen):

*  ``\load`` besitzt dieselbe Syntax wie ``\drawgraph``. Allerdings wird der entsprechende Graph erst beim Verlassen der Umgebung gezeichnet; bis dahin können mit den restlichen Befehlen Änderungen vorgenommen werden.
*  ``\marknode`` erlaubt das Hinzufügen weiterer Markierungen; als erster Parameter wird der Index des Knotens erwartet, dann die Klasse der Markierung. Eine Besonderheit: als Knotenindex sind auch arithmetische Ausdrücke zulässig, die neben Zahlen auch *N* (die Anzahl der Knoten) und *M* enthalten dürfen. Für einen 1-basierten Graphen könnte man also ``\marknode{N}{1}`` verwenden, um Markierung 1 auf den letzten Knoten anzuwenden und für einen 0-basierten Graphen stattdessen ``\marknode{N-1}{1}``.

Ein Beispiel:

.. sourcecode:: text

    \begin{graphpicture}
    \load[weighted]{1.in}
    \marknode{1}{1}
    \marknode{N}{1}
    \end{graphpicture}

zeichnet den gewichteten ungerichteten Graphen aus der Datei ``1.in`` und markiert zusätzlich den ersten und den letzten Knoten (mit dem ersten Markierungsstyle).

Auch ``graphpicture`` erzeugt auf oberster Ebene ein ``tikzpicture`` und sollte dementsprechend für ein ansprechendes Layout in einer geeigneten Umgebung verwendet werden.


Weitere Beispiele
-----------------
Puh, das ist vermutlich ziemlich viel auf einmal! Aber kein Grund zu verzagen: als IOI-Coach kannst du in unserem Aufgabenrepo im Ordner ``samples`` eine Beispiel-TeX-Datei mit zugehörigem PDF-Output finden, die zahlreiche Beispielgraphen aus unseren Aufgaben enthält. Darüber hinaus verwenden immer mehr unserer Graphenaufgaben das Graphdrawing-System. In fast allen Fällen solltest du bereits durch einfache Anpassungen an so einem Beispiel zum gewünschten Ergebnis kommen.

Übersichtszettel
================
Auf Wunsch erzeugt unser System auch automatisch *Übersichtszettel* für jeden Teilnehmer in einem gegebenen Wettbewerb. Diese enthalten allgemeine Informationen, eine Übersicht der Wettbewerbsaufgaben sowie die Anmeldedaten des Teilnehmers. Dieses Feature ist vor allem für Olympiaden gedacht, bei der jeder Teilnehmer einen Umschlag mit ausgedruckten Aufgabenstellungen bekommt; das Layout ist so gewählt, dass bei Verwendung einer DIN C4-Versandtasche genau der Nutzer- und tatsächliche Name im Fenster sichtbar wären, nicht aber Passwort oder wettbewerbsspezifische Informationen.

Um die Übersichtszettel zu erzeugen, kann man den Befehl ``make_overview_sheets()`` in ``contest-config.py`` verwenden. **Wichtig: der Befehl sollte erst möglichst am Ende der Konfigurationsdatei verwendet werden, definitiv aber erst nachdem alle Aufgaben und alle Nutzer erstellt wurden.**

Die Übersichtszettel werden in einem eigenen Ordner ``overview`` innerhalb des ``build``-Ordners angelegt. Auf Wunsch (Schlüsselwertargument ``attach_statements`` auf ``True`` setzen) können hinter jedem Übersichtszettel auch die "primären Statements" für den entsprechenden Nutzer eingebunden werden. Auf diese Weise kann man einfach die entsprechenden PDF ausdrucken und ohne Umsortieren direkt den Teamleitern zur Kontrolle geben und/oder sie in Umschläge stecken (das Template geht in diesem Fall von beidseitigem Druck aus und fügt wo nötig leere Seiten ein).