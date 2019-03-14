German System Info
******************
Für neue (und auch für alte) Coaches sind hier einige technische Informationen zu unserem Wettbewerbssystem aufgelistet.

Zugriff auf den Wettbewerbsserver
=================================
Um Zugriff auf den Wettbewerbsserver zu bekommen, musst du einem Coach deinen öffentlichen SSH-Schlüssel schicken.

Den SSH-Schlüssel kann dieser unter ``~/.ssh/authorized_keys`` und ``~cmsserveruser/.ssh/authorized_keys`` hinzufügen.

Du solltest dich jetzt per ``ssh cmsserveruser@contest.ioi-training.de`` auf dem
Server einloggen können.
Wenn du dann ``tmux a`` ausführst, kannst du die dort laufenden shells
bewundern. (``Strg-b``, dann eine Ziffer wechelt den Tab; mit ``Strg-b``, dann ``d``
kommst du wieder raus)

Mit ``git clone cmsserveruser@contest.ioi-training.de:aioi.git`` kannst du das
Aufgabenrepository auf deinen Rechner bekommen. (Siehe z.B. die git-
Dokumentation unter `<https://git-scm.com/book/en/v2>`_.)

Mit ``git clone --recursive https://github.com/ioi-germany/cms.git`` bekommst du
den deutschen Fork des CMS. (Wenn du einen Github-Account hast, kannst du einem der Coaches
auch mal deinen Usernamen schicken, damit du auch selbst Änderungen am CMS
hochladen kannst.)

Dann bitte die Dokumentation `hier <https://contest.ioi-training.de/docs/>`_ (das heißt, hier) lesen und die Installationshinweise befolgen.
Wichtig ist insbesondere `die Beschreibung des deutschen Aufgabenformates <https://contest.ioi-training.de/docs/External%20contest%20formats.html#german-import-format>`_.
Führe testweise einfach mal ``cmsGerMake .`` zum Beispiel im Ordner ``contests/ioi2017_training1`` aus.



Webseiten des Wettbewerbssystems
================================
Die Zugangsdaten für die folgenden Webseiten erhältst du von einem der Coaches -- oder findest sie in der Konfiguration auf dem Server.

Hier sind die internen Interfaces des Wettbewerbssystems (Zugangsdaten A):

- `<https://contest.ioi-training.de/admin/>`_
- `<https://contest.ioi-training.de/taskoverview/>`_
- `<https://contest.ioi-training.de/ranking/Ranking.html>`_

Das Teilnehmerinterface kann mit einem Testaccount (Zugangsdaten B) unter der folgenden Adresse aufgerufen werden:

- `<https://contest.ioi-training.de/>`_


Telegram-Bot
============
Clarification requests can be seen and answered and announcements be made via a telegram bot, providing easy and prompt access to what you regularly need during a contest and notifying you whenever a contestant needs help!

The following is the bot's self-specification containing a list of commands available:

.. sourcecode:: plain

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

.. sourcecode:: plain

    [Ignorierter Teil]
    #Knoten [#Kanten]
    [Ignorierter Teil]
    [Mehrere Listen von Knoten, wobei Knoten auch mehrfach vorkommen dürfen; jede Gruppe wird später eine eigene Markierung bekommen]
    [Je eine Annotation pro Knoten]
    Für jede Kante: Startknoten Endknoten [Gewicht]
    [Ignorierter Teil]

Die Listen von Knoten müssen dabei jeweils das Format

.. sourcecode:: plain

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

    .. sourcecode:: plain

        4 5
        1 2
        1 3
        2 3
        3 4
        4 1

2. Möchte man denselben Graphen als gerichteten Graphen interpretieren, so ist das Flag ``directed`` hinzuzufügen.

3. Wenn man ausdrücklich auf 0-Indizierung besteht, kann man nach Angabe des Flags ``zero_based`` stattdessen das folgende verwenden:

     .. sourcecode:: plain

        4 5
        0 1
        0 2
        1 2
        2 3
        3 0

4. Übergibt man das Flag ``weighted``, so würde die folgende Datei als ein (ungerichteter) gewichteter Graph mit vier Knoten und drei Kanten interpretieren:

    .. sourcecode:: plain

        4 3
        1 2 42
        1 3 1337
        1 4 4711

5. Es wird komplizierter: die folgende Datei wäre eine gültige Codierung für denselben Graphen, wenn es zusätzlich Knotengewichte gibt (die Zahlen an den Knoten können natürlich auch eine andere Bedeutung als Gewichte haben...); hierzu ist neben ``weighted`` zusätzlich noch ``annotated`` anzugeben:

    .. sourcecode:: plain

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

    .. sourcecode:: plain

        4 4
        2 1 2
        3 1 3 4
        1 2
        2 3
        3 4
        4 1

8. Übergibt man das Flag ``tree`` (und natürlich ``weighted``), ließe sich Beispiel 3 auch wie folgt codieren:

    .. sourcecode:: plain

        4
        1 2 42
        1 3 1337
        1 4 4711


Einfache Graphen zeichnen
-------------------------
In den meisten Fällen verwendet man dazu das TeX-Makro ``\drawgraph``; dieses erwartet als Parameter den Pfad zu der Eingabedatei (im Format wie oben), die gelesen werden soll, sowie optional in eckigen Klammern die Flags und Parameter wie oben beschrieben (in beliebiger Reihenfolge, durch Kommata getrennt, Leerzeichensindoptional). Zwei Beispiele:

1. Enthält ``1.in`` den Text aus dem ersten Beispiel oben, so würde ``\drawgraph{1.in}`` diesen zeichnen. Wäre die Datei in einem Unterordner ``inputs`` würde man stattdessen ``\drawgraph{inputs/1.in}`` verwenden.

2. Enthält ``8.in`` das allerletzte Beispiel oben, so würde ``\drawgraph[weighted,tree]{8.in}`` den entsprechenden Graphen zeichnen.

Auf oberster Ebene erzeugt ``\drawgraph`` ein ``tikzpicture``; für ein ansprechendes Layout sollte dieser Befehl also in eine geeignete LaTeX-Umgebung wie ``center`` oder ``wrapfigure`` gesteckt werden.


Fortgeschrittenes
-----------------
Für kompliziertere Graphen, bei denen man von Hand Veränderungen vornehmen möchte, steht die Umgebung ``graphpicture`` zur Verfügung. In dieser stehen die folgenden zusätzlichen Befehle zur Verfügung (viele weitere sollen folgen):

*  ``\load`` besitzt dieselbe Syntax wie ``\drawgraph``. Allerdings wird der entsprechende Graph erst beim Verlassen der Umgebung gezeichnet; bis dahin können mit den restlichen Befehlen Änderungen vorgenommen werden.
*  ``\marknode`` erlaubt das Hinzufügen weiterer Markierungen; als erster Parameter wird der Index des Knotens erwartet, dann die Klasse der Markierung. Eine Besonderheit: als Knotenindex sind auch arithmetische Ausdrücke zulässig, die neben Zahlen auch *N* (die Anzahl der Knoten) und *M* enthalten dürfen. Für einen 1-basierten Graphen könnte man also ``\marknode{N}{1}`` verwenden, um Markierung 1 auf den letzten Knoten anzuwenden und für einen 0-basierten Graphen stattdessen ``\marknode{N-1}{1}``.

Ein Beispiel:

.. sourcecode:: plain

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