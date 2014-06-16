#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""A service that prints files.

"""

import json
import logging
import os
import tempfile
import time
import subprocess
from tornado import template
from PyPDF2 import PdfFileReader, PdfFileMerger

import gevent
from gevent.queue import JoinableQueue
from gevent.event import Event

from cms import config
from cms.db.filecacher import FileCacher
from cms.io import Service, rpc_method
from cms.io.GeventUtils import rmtree
from cms.db import SessionGen, PrintJob
from cms.server import format_datetime
from cmscommon.datetime import get_timezone


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


def pretty_print_cmdline(cmdline):
    """Pretty print a command line.

    Take a command line suitable to be passed to a Popen-like call and
    returns a string that represents it in a way that preserves the
    structure of arguments and can be passed to bash as is.

    More precisely, delimitate every item of the command line with
    single apstrophes and join all the arguments separating them with
    spaces.

    """
    return " ".join(["'%s'" % (x) for x in cmdline])


class PrintingService(Service):
    """A service that prepares print jobs and sends them to a printer.

    A submission result is ready to be scored when its compilation is
    unsuccessful (in this case, no evaluation will be performed) or
    after it has been evaluated. The goal of scoring is to use the
    evaluations to determine score, score_details, public_score,
    public_score_details and ranking_score_details (all non-null).
    Scoring is done by the compute_score method of the ScoreType
    defined by the dataset of the result.

    ScoringService keeps a queue of (submission_id, dataset_id) pairs
    identifying submission results to score. A greenlet is spawned to
    consume this queue, one item at a time. The queue is filled by the
    new_evaluation and the invalidate_submissions RPC methods, and by a
    sweeper greenlet, whose duty is to regularly check all submissions
    in the database and put the unscored ones in the queue (this check
    can also be forced by the search_jobs_not_done RPC method).

    """

    # How often we look for printing jobs.
    SWEEPER_TIMEOUT = 347.0

    def __init__(self, shard):
        """Initialize the PrintingService.

        """
        Service.__init__(self, shard)

        if config.printer is None:
            logger.warning("Printing is disabled, so the PrintingService is "
                           "idle.")
            return

        self.file_cacher = FileCacher(self)
        template_dir = os.path.join(os.path.dirname(__file__),
                                    "templates", "printing")
        self.template_loader = template.Loader(template_dir, autoescape=None)

        # Set up and spawn the scorer.
        # TODO Link to greenlet: when it dies, log CRITICAL and exit.
        self._printer_queue = JoinableQueue()
        gevent.spawn(self._printer_loop)

        # Set up and spawn the sweeper.
        # TODO Link to greenlet: when it dies, log CRITICAL and exit.
        self._sweeper_start = None
        self._sweeper_event = Event()
        gevent.spawn(self._sweeper_loop)

    def _printer_loop(self):
        """Monitor the queue, printing its top element.

        This is an infinite loop that, at each iteration, gets an item
        from the queue (blocking until there is one, if the queue is
        empty) and scores it. Any error during the scoring is sent to
        the logger and then suppressed, because the loop must go on.

        """
        while True:
            printjob_id = self._printer_queue.get()
            try:
                self._print(printjob_id)
            except Exception:
                logger.error("Unexpected error when printing job %d.",
                             printjob_id,
                             exc_info=True)
            finally:
                self._printer_queue.task_done()

    def _print(self, printjob_id):
        """Print a print job.

        This is the core of PrintingService.

        printjob_id (int): the id of the print job that has to be
            printed.

        """
        with SessionGen() as session:
            # Obtain print job.
            printjob = PrintJob.get_from_id(printjob_id, session)
            if printjob is None:
                raise ValueError("Print job %d not found in the database." %
                                 printjob_id)
            user = printjob.user
            contest = user.contest
            timezone = get_timezone(user, contest)
            timestr = format_datetime(printjob.timestamp, timezone)
            filename = printjob.filename

            # Check if it's ready to be printed.
            if printjob.done:
                logger.info("Print job %d is already sent to the printer.",
                            printjob_id)

            directory = tempfile.mkdtemp(dir=config.temp_dir)
            logger.info("Preparing print job in directory {}"
                        .format(directory))

            # Take the base name just to be sure
            relname = "source_" + os.path.basename(filename)
            source = os.path.join(directory, relname)
            with open(source, "wb") as f:
                self.file_cacher.get_file_to_fobj(printjob.digest, f)

            if filename.endswith(".pdf") and config.pdf_printing_allowed:
                source_pdf = source
            else:
                # Convert text to ps
                source_ps = os.path.join(directory, "source.ps")
                cmd = ["a2ps",
                       source,
                       "--delegate=no",
                       "--output="+source_ps,
                       "--medium=A4",
                       "--portrait",
                       "--columns=1",
                       "--rows=1",
                       "--pages=1-%d" % (config.max_pages_per_job),
                       "--header=",
                       "--footer=",
                       "--left-footer=",
                       "--right-footer=",
                       "--center-title="+filename,
                       "--left-title="+timestr]
                ret = subprocess.call(cmd, cwd=directory)
                if ret != 0:
                    raise Exception(
                        "Failed to convert text file to ps with command: %s"
                        "(error %d)" % (pretty_print_cmdline(cmd), ret))

                # Convert ps to pdf
                source_pdf = os.path.join(directory, "source.pdf")
                cmd = ["ps2pdf",
                       "-sPAPERSIZE=a4",
                       source_ps]
                ret = subprocess.call(cmd, cwd=directory)
                if ret != 0:
                    raise Exception(
                        "Failed to convert ps file to pdf with command: %s"
                        "(error %d)" % (pretty_print_cmdline(cmd), ret))

            # Find out number of pages
            with open(source_pdf, "rb") as f:
                pdfreader = PdfFileReader(f)
                page_count = pdfreader.getNumPages()

            logger.info("Preparing {} page(s) (plus the title page)"
                        .format(page_count))

            if page_count > config.max_pages_per_job:
                logger.info("Too many pages.")
                printjob.done = True
                printjob.status = json.dumps([
                    N_("Print job has too many pages")])
                session.commit()
                rmtree(directory)
                return

            # Add the title page
            title_tex = os.path.join(directory, "title_page.tex")
            title_pdf = os.path.join(directory, "title_page.pdf")
            with open(title_tex, "w") as f:
                f.write(self.template_loader.load("title_page.tex")
                        .generate(user=user, filename=filename,
                                  timestr=timestr,
                                  page_count=page_count))
            cmd = ["pdflatex",
                   "-interaction",
                   "nonstopmode",
                   title_tex]
            ret = subprocess.call(cmd, cwd=directory)
            if ret != 0:
                raise Exception(
                    "Failed to create title page with command: %s"
                    "(error %d)" % (pretty_print_cmdline(cmd), ret))

            pdfmerger = PdfFileMerger()
            with open(title_pdf, "rb") as f:
                pdfmerger.append(f)
            with open(source_pdf, "rb") as f:
                pdfmerger.append(f)
            result = os.path.join(directory, "document.pdf")
            with open(result, "wb") as f:
                pdfmerger.write(f)

            cmd = ["lpr",
                   "-P",
                   config.printer,
                   result]
            ret = subprocess.call(cmd, cwd=directory)
            if ret != 0:
                raise Exception(
                    "Failed to print pdf file with command: %s"
                    "(error %d)" % (pretty_print_cmdline(cmd), ret))

            printjob.done = True
            printjob.status = json.dumps([N_("Sent to printer")])
            session.commit()

            rmtree(directory)

    def _sweeper_loop(self):
        """Regularly check the database for unprinted print jobs.

        Try to sweep the database once every SWEEPER_TIMEOUT seconds
        but make sure that no two sweeps run simultaneously. That is,
        start a new sweep SWEEPER_TIMEOUT seconds after the previous
        one started or when the previous one finished, whatever comes
        last.

        The search_jobs_not_done RPC method can interfere with this
        regularity, as it tries to run a sweeper as soon as possible:
        immediately, if no sweeper is running, or as soon as the
        current one terminates.

        Any error during the sweep is sent to the logger and then
        suppressed, because the loop must go on.

        """
        while True:
            self._sweeper_start = time.time()
            self._sweeper_event.clear()

            try:
                self._sweep()
            except Exception:
                logger.error("Unexpected error when searching for unprinted "
                             "print jobs.", exc_info=True)

            self._sweeper_event.wait(max(self._sweeper_start +
                                         self.SWEEPER_TIMEOUT -
                                         time.time(), 0))

    def _sweep(self):
        """Check the database for unprinted print jobs.

        Obtain a list of all the print jobs in the database,
        check each of them to see if it's still unprinted and, in case,
        put it in the queue.

        """
        counter = 0

        with SessionGen() as session:
            for pj in session.query(PrintJob) \
                    .filter(PrintJob.done == False).all():
                self._printer_queue.put(pj.id)
                counter += 1

        if counter > 0:
            logger.info("Found %d unprinted print jobs.", counter)

    @rpc_method
    def search_jobs_not_done(self):
        """Make the sweeper loop fire the sweeper as soon as possible.

        """
        self._sweeper_event.set()
