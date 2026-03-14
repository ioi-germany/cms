#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2026 Erik Sünderhauf <erik.suenderhauf@gmx.de>
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

import logging

from sched import scheduler
from sys import exc_info
from traceback import format_exception
from typing import Callable

logger = logging.getLogger(__name__)


class BackgroundScheduler(scheduler):
    def __init__(self):
        super().__init__()

    def every(self, interval: float, func: Callable, priority: int = 0, skip_first: bool = True, args=(), **kwargs) -> None:
        def wrapped():
            try:
                func(*args, **kwargs)
            except Exception:
                logger.error("Failed to execute background task",
                             "\n".join(format_exception(*exc_info())))
            finally:
                self.enter(interval, priority, wrapped)
        delay = 0
        if skip_first:
            delay = interval
        self.enter(delay, priority, wrapped)
