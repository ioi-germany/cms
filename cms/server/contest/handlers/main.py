#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2018 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2021 Manuel Gundlach <manuel.gundlach@gmail.com>
# Copyright © 2021 Grace Hawkins <amoomajid99@gmail.com>
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

"""Non-categorized handlers for CWS.

"""

import ipaddress
import json
import logging
import re

try:
    import tornado4.web as tornado_web
except ImportError:
    import tornado.web as tornado_web
from sqlalchemy.orm.exc import NoResultFound

from cms import config
from cms.db import PrintJob, User, Participation, Team
from cms.grading.steps import COMPILATION_MESSAGES, EVALUATION_MESSAGES
from cms.server import multi_contest
from cms.server.contest.authentication import validate_login
from cms.server.contest.communication import get_communications
from cms.server.contest.printing import accept_print_job, PrintingDisabled, \
    UnacceptablePrintJob
from cmscommon.crypto import hash_password, validate_password
from cmscommon.datetime import make_datetime, make_timestamp
from cmscommon.mimetypes import get_type_for_file_name
from .contest import ContestHandler
from ..phase_management import actual_phase_required

from cms.server.captcha.captcha import Captcha


logger = logging.getLogger(__name__)


# Dummy function to mark translatable strings.
def N_(msgid):
    return msgid


class MainHandler(ContestHandler):
    """Home page handler.

    """
    @multi_contest
    def get(self):
        self.render("overview.html", **self.r_params)

class CaptchaHandler(ContestHandler):
    """Captcha handler.

    Used to get a captcha with an encoded cookie containing its
    solution and a request identifier
    TODO Should probably use something like FileHandler for the png

    """

    MAX_INPUT_LENGTH = 50

    captcha = Captcha()

    def prepare(self):
        super().prepare()
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")

    @multi_contest
    def get(self):
        this_captcha = self.captcha.captcha()
        captcha_clear = ''.join([ str(x) for x in this_captcha[0] ])
        captcha_bs = this_captcha[1]

        mimetype = get_type_for_file_name("captcha.png")
        if mimetype is None:
            mimetype = 'application/octet-stream'

        self.add_header('Content-Type', mimetype)

        #We require an identifier so a captcha's cookie is restricted
        #in use for a specific action.
        try:
            identifier = self.get_argument("identifier")
            if not 1 <= len(identifier) <= self.MAX_INPUT_LENGTH:
                raise ValueError()
            if not re.match(r"^[A-Za-z0-9_-]+$", identifier):
                raise ValueError()
        except (tornado_web.MissingArgumentError, ValueError):
            raise tornado_web.HTTPError(400)

        #We don't use a reference to the running contest, so the answer
        #to a captcha in one contest could be used for the same action in
        #another. Won't fix
        #identifier should be signed so it can't be tempered with, which is taken
        #care of by set_secure_cookie.
        #captcha_clear should additionally not be accessible for the user,
        #so we only include its signature and compare that later to the signature
        #of the user's input
        cookie = self.signature(captcha_clear) + "_" + identifier
        cookie_name = "captcha"
        self.set_secure_cookie(cookie_name, cookie, expires_days=None)

        self.write(captcha_bs)


class RegistrationHandler(ContestHandler):
    """Registration handler.

    Used to create a participation when this is allowed.
    If `new_user` argument is true, it creates a new user too.

    """

    MAX_INPUT_LENGTH = 50
    MIN_PASSWORD_LENGTH = 6
    CAPTCHA_LENGTH = 6

    @multi_contest
    def post(self):
        if not self.contest.allow_registration:
            raise tornado_web.HTTPError(404)

        create_new_user = self.get_argument("new_user") == "true"

        # Get or create user
        if create_new_user:
            user = self._create_user()
        else:
            user = self._get_user()

            # Check if the participation exists
            contest = self.contest
            tot_participants = self.sql_session.query(Participation)\
                                   .filter(Participation.user == user)\
                                   .filter(Participation.contest == contest)\
                                   .count()
            if tot_participants > 0:
                raise tornado_web.HTTPError(409)

        # Create participation
        team = self._get_team()
        participation = Participation(user=user, contest=self.contest,
                                      group=self.contest.main_group, team=team)
        self.sql_session.add(participation)

        self.sql_session.commit()

        self.finish(user.username)

    @multi_contest
    def get(self):
        if not self.contest.allow_registration:
            raise tornado_web.HTTPError(404)

        self.r_params["MAX_INPUT_LENGTH"] = self.MAX_INPUT_LENGTH
        self.r_params["MIN_PASSWORD_LENGTH"] = self.MIN_PASSWORD_LENGTH
        self.r_params["CAPTCHA_LENGTH"] = self.CAPTCHA_LENGTH
        self.r_params["teams"] = self.sql_session.query(Team)\
                                     .order_by(Team.name).all()

        self.render("register.html", **self.r_params)

    def _create_user(self):
        try:
            first_name = self.get_argument("first_name")
            last_name = self.get_argument("last_name")
            username = self.get_argument("username")
            password = self.get_argument("password")
            email = self.get_argument("email")
            if len(email) == 0:
                email = None
            if self.contest.registration_requires_captcha:
                captcha_input = self.get_argument("captcha")
                captcha_input_signature = self.signature(captcha_input)
                captcha_cookie = self.get_secure_cookie("captcha").decode('utf-8')
                captcha_clear_signature, captcha_username = captcha_cookie.split('_',1)

            if not 1 <= len(first_name) <= self.MAX_INPUT_LENGTH:
                raise ValueError()
            if not 1 <= len(last_name) <= self.MAX_INPUT_LENGTH:
                raise ValueError()
            if not 1 <= len(username) <= self.MAX_INPUT_LENGTH:
                raise ValueError()
            if not re.match(r"^[A-Za-z0-9_-]+$", username):
                raise ValueError()
            if not self.MIN_PASSWORD_LENGTH <= len(password) \
                    <= self.MAX_INPUT_LENGTH:
                raise ValueError()
            if self.contest.registration_requires_captcha:
                if not re.match(r"^[0-9]+$", captcha_input):
                    raise ValueError()
                if not captcha_input_signature == captcha_clear_signature:
                    raise ValueError()
                if not username == captcha_username:
                    raise ValueError()
        except (tornado_web.MissingArgumentError, ValueError):
            raise tornado_web.HTTPError(400)

        # Override password with its hash
        password = hash_password(password)

        # Check if the username is available
        tot_users = self.sql_session.query(User)\
                        .filter(User.username == username).count()
        if tot_users != 0:
            # HTTP 409: Conflict
            raise tornado_web.HTTPError(409)

        # Store new user
        user = User(first_name, last_name, username, password, email=email)
        self.sql_session.add(user)

        return user

    def _get_user(self):
        username = self.get_argument("username")
        password = self.get_argument("password")

        # Find user if it exists
        user = self.sql_session.query(User)\
                        .filter(User.username == username)\
                        .first()
        if user is None:
            raise tornado_web.HTTPError(404)

        # Check if password is correct
        if not validate_password(user.password, password):
            raise tornado_web.HTTPError(403)

        return user

    def _get_team(self):
        # If we have teams, we assume that the 'team' field is mandatory
        if self.sql_session.query(Team).count() > 0:
            try:
                team_code = self.get_argument("team")
                team = self.sql_session.query(Team)\
                           .filter(Team.code == team_code)\
                           .one()
            except (tornado_web.MissingArgumentError, NoResultFound):
                raise tornado_web.HTTPError(400)
        else:
            team = None

        return team


class LoginHandler(ContestHandler):
    """Login handler.

    """
    @multi_contest
    def post(self):
        error_args = {"login_error": "true"}
        next_page = self.get_argument("next", None)
        if next_page is not None:
            error_args["next"] = next_page
            if next_page != "/":
                next_page = self.url(*next_page.strip("/").split("/"))
            else:
                next_page = self.url()
        else:
            next_page = self.contest_url()
        error_page = self.contest_url(**error_args)

        username = self.get_argument("username", "")
        password = self.get_argument("password", "")

        try:
            ip_address = ipaddress.ip_address(self.request.remote_ip)
        except ValueError:
            logger.warning("Invalid IP address provided by Tornado: %s",
                           self.request.remote_ip)
            return None

        participation, cookie = validate_login(
            self.sql_session, self.contest, self.timestamp, username, password,
            ip_address)

        cookie_name = self.contest.name + "_login"
        if cookie is None:
            self.clear_cookie(cookie_name)
        else:
            self.set_secure_cookie(cookie_name, cookie, expires_days=None)

        if participation is None:
            self.redirect(error_page)
        else:
            self.redirect(next_page)


class StartHandler(ContestHandler):
    """Start handler.

    Used by a user who wants to start their per_user_time.

    """
    @tornado_web.authenticated
    @actual_phase_required(-1)
    @multi_contest
    def post(self):
        participation = self.current_user

        logger.info("Starting now for user %s", participation.user.username)
        participation.starting_time = self.timestamp
        self.sql_session.commit()

        self.redirect(self.contest_url())


class LogoutHandler(ContestHandler):
    """Logout handler.

    """
    @multi_contest
    def post(self):
        self.clear_cookie(self.contest.name + "_login")
        self.redirect(self.contest_url())


class NotificationsHandler(ContestHandler):
    """Displays notifications.

    """

    refresh_cookie = False

    @tornado_web.authenticated
    @multi_contest
    def get(self):
        participation = self.current_user

        last_notification = self.get_argument("last_notification", None)
        if last_notification is not None:
            last_notification = make_datetime(float(last_notification))

        res = get_communications(self.sql_session, participation,
                                 self.timestamp, after=last_notification)

        # Simple notifications
        notifications = self.service.notifications
        username = participation.user.username
        if username in notifications:
            for notification in notifications[username]:
                res.append({"type": "notification",
                            "timestamp": make_timestamp(notification[0]),
                            "subject": notification[1],
                            "text": notification[2],
                            "level": notification[3]})
            del notifications[username]

        self.write(json.dumps(res))


class PrintingHandler(ContestHandler):
    """Serve the interface to print and handle submitted print jobs.

    """
    @tornado_web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def get(self):
        participation = self.current_user

        if not self.r_params["printing_enabled"]:
            raise tornado_web.HTTPError(404)

        printjobs = self.sql_session.query(PrintJob)\
            .filter(PrintJob.participation == participation)\
            .all()

        remaining_jobs = max(0, config.max_jobs_per_user - len(printjobs))

        self.render("printing.html",
                    printjobs=printjobs,
                    remaining_jobs=remaining_jobs,
                    max_pages=config.max_pages_per_job,
                    pdf_printing_allowed=config.pdf_printing_allowed,
                    **self.r_params)

    @tornado_web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def post(self):
        try:
            printjob = accept_print_job(
                self.sql_session, self.service.file_cacher, self.current_user,
                self.timestamp, self.request.files)
            self.sql_session.commit()
        except PrintingDisabled:
            raise tornado_web.HTTPError(404)
        except UnacceptablePrintJob as e:
            self.notify_error(e.subject, e.text, e.text_params)
        else:
            self.service.printing_service.new_printjob(printjob_id=printjob.id)
            self.notify_success(N_("Print job received"),
                                N_("Your print job has been received."))

        self.redirect(self.contest_url("printing"))


class DocumentationHandler(ContestHandler):
    """Displays the instruction (compilation lines, documentation,
    ...) of the contest.

    """
    @tornado_web.authenticated
    @multi_contest
    def get(self):
        self.render("documentation.html",
                    COMPILATION_MESSAGES=COMPILATION_MESSAGES,
                    EVALUATION_MESSAGES=EVALUATION_MESSAGES,
                    **self.r_params)
