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
