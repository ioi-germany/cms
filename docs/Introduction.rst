Introduction
************

CMS (Contest Management System) is a software for organizing programming contests similar to well-known international contests like the IOI (International Olympiad in Informatics). It was written by and it received contributions from people involved in the organization of similar contests on a local, national and international level, and it is regularly used for such contests in many different countries. It is meant to be secure, extendable, adaptable to different situations and easy to use.

CMS is a complete, tested and well proved solution for managing a contest. However, it only provides limited tools for the development of the task data belonging to the contest (task statements, solutions, testcases, etc.). Also, the configuration of machines and network resources that host the contest is a responsibility of the contest administrators.


General structure
=================
The system is organized in a modular way, with different services running (potentially) on different machines, and providing extendability via service replications on several machines.

The state of the contest is wholly kept on a PostgreSQL database (other DBMSs are not supported, as CMS relies on the Large Object (LO) feature of PostgreSQL). It is unlikely that in the future we will target different databases.

As long as the database is operating correctly, all other services can be started and stopped independently. For example, the administrator can quickly replace a broken machine with an identical one, which will take its roles (without having to move information from the broken machine). Of course, this also means that CMS is completely dependent on the database to run. In critical contexts, it is necessary to configure the database redundantly and be prepared to rapidly do a fail-over in case something bad happens. The choice of PostgreSQL as the database to use should ease this part, since there are many different, mature and well-known solutions to provide such redundance and fail-over procedures.


Services
========

CMS is composed of several services, that can be run on a single or on many servers. The core services are:

- LogService: collects all log messages in a single place;

- ResourceService: collects data about the services running on the same server, and takes care of starting all of them with a single command;

- Checker: simple heartbeat monitor for all services;

- EvaluationService: organizes the queue of the submissions to compile or evaluate on the testcases, and dispatches these jobs to the workers;

- Worker: actually runs the jobs in a sandboxed environment;

- ScoringService: collects the outcomes of the submissions and computes the score;

- ProxyService: sends the computed scores to the rankings;

- PrintingService: processes files submitted for printing and sends them to a printer;

- ContestWebServer: the webserver that the contestants will be interacting with;

- AdminWebServer: the webserver to control and modify the parameters of the contests.

TaskOverviewWebServer is a webserver showing an overview of all tasks in a directory (mainly to simplify task selection). ResourceService doesn't start the TaskOverviewWebServer, so it has to be started manually.

You can use GerTranslateWebServer to provide an intuitive interface for handling the translation of statements, intended for use by team leaders at olympiads.

Finally, RankingWebServer, whose duty is of course to show the ranking. This webserver is - on purpose - separated from the inner core of CMS in order to ease the creation of mirrors and restrict the number of people that can access services that are directly connected to the database.

Each of the core services is designed to be able to be killed and reactivated in a way that keeps the consistency of data, and does not block the functionalities provided by the other services.

Some of the services can be replicated on several machine: these are ResourceService (designed to be run on every machine), ContestWebServer and Worker.

In addition to services, CMS includes many command line tools. They help with importing, exporting and managing of contest data, and with testing.

Security considerations
=======================

With the exception of RWS, there are no cryptographic or authentication schemes between the various services or between the services and the database. Thus, it is mandatory to keep the services on a dedicated network, properly isolating it via firewalls from contestants or other people's computers. This sort of operations, like also preventing contestants from communicating and cheating, is responsibility of the administrator and is not managed by CMS itself.

.. _installation_security:

A basic firewall
----------------
One hassle-free way of setting up a firewall is by using ``nftables``. Once installed, you should put the necessary rules into ``/etc/nftables.conf``, and then run ``systemctl start nftables`` and ``systemctl enable nftables``. On a home computer, usually you can just use the following configuration. It basically blocks all ingoing connections. If the computer should be accessible via ``ssh``, ``http`` or ``https`` ports (e.g., because it's a server), uncomment the ``tcp dport {ssh, http, https} accept`` line and only keep the respective keywords. If you experience any issues, e.g. because your computer is running a remote printing server, just add the port numbers that have to remain open to that line.

.. sourcecode:: text

    #!/usr/bin/nft -f
    # ipv4/ipv6 Simple & Safe Firewall
    # you can find examples in /usr/share/nftables/

    table inet filter {
        chain input {
            type filter hook input priority 0;

            # allow established/related connections
            ct state {established, related} accept

            # early drop of invalid connections
            ct state invalid drop

            # allow from loopback
            iifname lo accept

            # allow icmp
            ip protocol icmp accept
            meta l4proto ipv6-icmp accept

            # allow ssh, http, https
            # tcp dport {ssh, http, https} accept

            # everything else
            reject with icmpx type port-unreachable
        }
        chain forward {
            type filter hook forward priority 0;
            drop
        }
        chain output {
            type filter hook output priority 0;
        }
    }

