#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2022 Manuel Gundlach <manuel.gundlach@gmail.com>
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

import errno
import jinja2
import jinja2.meta
import json
import logging
import os
import sys
import tomli
from dataclasses import dataclass, field
from datetime import datetime
from collections import namedtuple
from typing import Optional

from .log import set_detailed_logs


logger = logging.getLogger(__name__)


class Address(namedtuple("Address", "ip port")):
    def __repr__(self):
        return "%s:%d" % (self.ip, self.port)


class ServiceCoord(namedtuple("ServiceCoord", "name shard")):
    """A compact representation for the name and the shard number of a
    service (thus identifying it).

    """

    def __repr__(self):
        return "%s,%d" % (self.name, self.shard)


class ConfigError(Exception):
    """Exception for critical configuration errors."""
    pass


class AsyncConfig:
    """This class will contain the configuration for the
    services. This needs to be populated at the initilization stage.

    The *_services variables are dictionaries indexed by ServiceCoord
    with values of type Address.

    Core services are the ones that are supposed to run whenever the
    system is up.

    Other services are not supposed to run when the system is up, or
    anyway not constantly.

    """
    core_services = {}
    other_services = {}


async_config = AsyncConfig()


class Config:
    """This class will contain the configuration for CMS. This needs
    to be populated at the initilization stage. This is loaded by
    default with some sane data. See cms.conf.sample in the config
    directory for information on the meaning of the fields.

    """

    @dataclass
    class Systemwide:
        cmsuser: str = "cmsuser"
        temp_dir: str = "/tmp"
        backdoor: bool = False
        file_log_debug: bool = False
        stream_log_detailed: bool = False

    @dataclass
    class GerMake:
        always_recompute_hash: bool = True

    @dataclass
    class Database:
        database: str = "postgresql+psycopg2://cmsuser@localhost/cms"
        database_debug: bool = False
        twophase_commit: bool = False

    @dataclass
    class Worker:
        keep_sandbox: bool = True
        use_cgroups: bool = True
        sandbox_implementation: str = 'isolate'

    @dataclass
    class Sandbox:
        # Max size of each writable file during an evaluation step, in KiB.
        max_file_size: int = 1024 * 1024  # 1 GiB
        # Max processes, CPU time (s), memory (KiB) for compilation runs.
        compilation_sandbox_max_processes: int = 1000
        compilation_sandbox_max_time_s: float = 10.0
        compilation_sandbox_max_memory_kib: int = 512 * 1024  # 512 MiB
        # Max processes, CPU time (s), memory (KiB)
        # for LaTeX compilation runs
        latex_compilation_sandbox_max_processes: int = \
            compilation_sandbox_max_processes
        latex_compilation_sandbox_max_time_s: float = 3 * 60.0
        latex_compilation_sandbox_max_memory_kib: int = \
            2 * 1024 * 1024  # 2 GiB

        # Where should the LaTeX sandbox look for packages, fonts, etc.?
        def _default_latex_distro():
            now = datetime.now().year
            for s in [str(y) for y in range(now - 10, now + 1)] + [""]:
                if os.path.exists(os.path.join(os.path.expanduser("~"),
                                               ".texlive" + s)):
                    return ".texlive" + s
            return None
        latex_distro: Optional[str] = _default_latex_distro()

        def _default_latex_additional_dirs():
            return [d for d in ["~/.local/share/fonts",
                                "~/texmf"]
                    if os.path.exists(os.path.expanduser(d))]
        latex_additional_dirs: list[str] = \
            field(default_factory=_default_latex_additional_dirs)

        # Max processes, CPU time (s), memory (KiB) for trusted runs.
        trusted_sandbox_max_processes: int = 1000
        trusted_sandbox_max_time_s: float = 10.0
        trusted_sandbox_max_memory_kib: int = 4 * 1024 * 1024  # 4 GiB

    @dataclass
    class WebServers:
        secret_key_default: str = "8e045a51e4b102ea803c06f92841a1fb"
        secret_key: str = secret_key_default
        tornado_debug: bool = False

    @dataclass
    class ContestWebServer:
        listen_address: list[str] = \
            field(default_factory=lambda: [""])
        listen_port: list[int] = \
            field(default_factory=lambda: [8888])
        cookie_duration: int = 30 * 60  # 30 minutes
        submit_local_copy: bool = True
        submit_local_copy_path: str = "%s/submissions/"
        tests_local_copy: bool = True
        tests_local_copy_path: str = "%s/tests/"
        # (deprecated in favor of num_proxies_used)
        is_proxy_used: Optional[bool] = None
        num_proxies_used: Optional[int] = None
        max_submission_length: int = 100_000  # 100 KB
        max_input_length: int = 5_000_000  # 5 MB
        stl_path: str = "/usr/share/cppreference/doc/html/"
        py_sl_path: str = "/usr/share/pyreference/"
        # Prefix of 'shared-mime-info'[1] installation. It can be found
        # out using `pkg-config --variable=prefix shared-mime-info`, but
        # it's almost universally the same (i.e. '/usr') so it's hardly
        # necessary to change it.
        # [1] http://freedesktop.org/wiki/Software/shared-mime-info
        shared_mime_info_prefix: str = "/usr"

    @dataclass
    class AdminWebServer:
        listen_address: str = ""
        listen_port: int = 8889
        cookie_duration: int = 10 * 60 * 60  # 10 hours
        num_proxies_used: Optional[int] = None

    @dataclass
    class ProxyService:
        rankings: list[str] = \
            field(default_factory=lambda:
                  ["http://usern4me:passw0rd@localhost:8890/"])
        https_certfile: Optional[str] = None

    @dataclass
    class PrintingService:
        max_print_length: int = 10_000_000  # 10 MB
        printer: Optional[str] = None
        paper_size: str = "A4"
        max_pages_per_job: int = 10
        max_jobs_per_user: int = 10
        pdf_printing_allowed: bool = False

    @dataclass
    class TaskOverviewWebServer:
        listen_address: str = "127.0.0.1"
        listen_port: int = 8891
        task_repository: Optional[str] = None
        auto_sync: bool = False
        max_compilations: int = 1000

    @dataclass
    class GerTranslateWebServer:
        listen_address: str = "127.0.0.1"
        listen_port: int = 8892
        task_repository: Optional[str] = None
        auto_sync: bool = False
        max_compilations: int = 1000

    @dataclass
    class TelegramBotService:
        telegram_bot_max_error_messages: int = 5
        bot_token: str = ""
        bot_pwd: str = ""

    def __init__(self):
        """Default values for configuration, plus decide if this
        instance is running from the system path or from the source
        directory.

        """
        self.async_config = async_config

        self.systemwide = self.Systemwide()
        self.germake = self.GerMake()
        self.database = self.Database()
        self.worker = self.Worker()
        self.sandbox = self.Sandbox()
        self.webservers = self.WebServers()
        self.cws = self.ContestWebServer()
        self.aws = self.AdminWebServer()
        self.proxyservice = self.ProxyService()
        self.printingservice = self.PrintingService()
        self.taskoverview = self.TaskOverviewWebServer()
        self.gertranslate = self.GerTranslateWebServer()
        self.telegrambot = self.TelegramBotService()

        # Installed or from source?
        # We declare we are running from installed if the program was
        # NOT invoked through some python flavor, and the file is in
        # the prefix (or real_prefix to accommodate virtualenvs).
        bin_path = os.path.join(os.getcwd(), sys.argv[0])
        bin_name = os.path.basename(bin_path)
        bin_is_python = bin_name in ["ipython", "python", "python2", "python3"]
        bin_in_installed_path = bin_path.startswith(sys.prefix) or (
            hasattr(sys, 'real_prefix')
            and bin_path.startswith(sys.real_prefix))
        self.installed = bin_in_installed_path and not bin_is_python

        if self.installed:
            self.log_dir = os.path.join("/", "var", "local", "log", "cms")
            self.cache_dir = os.path.join("/", "var", "local", "cache", "cms")
            self.latex_cache_dir = os.path.join(
                "/", "var", "local", "cache", "cms", "latex"
            )
            self.data_dir = os.path.join("/", "var", "local", "lib", "cms")
            self.run_dir = os.path.join("/", "var", "local", "run", "cms")
            paths = [os.path.join("/", "usr", "local", "etc", "cms.conf"),
                     os.path.join("/", "etc", "cms.conf")]
        else:
            self.log_dir = "log"
            self.cache_dir = "cache"
            self.latex_cache_dir = "cache-latex"
            self.data_dir = "lib"
            self.run_dir = "run"
            paths = [os.path.join(".", "config", "cms.conf")]
            if '__file__' in globals():
                paths += [os.path.abspath(os.path.join(
                          os.path.dirname(__file__),
                          '..', 'config', 'cms.conf'))]
            paths += [os.path.join("/", "usr", "local", "etc", "cms.conf"),
                      os.path.join("/", "etc", "cms.conf")]

        # Allow user to override config file path using environment
        # variable 'CMS_CONFIG'.
        CMS_CONFIG_ENV_VAR = "CMS_CONFIG"
        if CMS_CONFIG_ENV_VAR in os.environ:
            paths = [os.environ[CMS_CONFIG_ENV_VAR]] + paths

        # Attempt to load a config file.
        self._load(paths)

        # If the configuration says to print detailed log on stdout,
        # change the log configuration.
        set_detailed_logs(self.systemwide.stream_log_detailed)

    def _load(self, paths):
        """Try to load the config files one at a time, until one loads
        correctly.

        """
        for conf_file in paths:
            if self._load_unique(conf_file):
                break
        else:
            logging.warning("No valid configuration file found: "
                            "falling back to default values.")

    def _load_unique(self, path):
        """Populate the Config class with everything that sits inside
        the TOML file path (usually something like /etc/cms.conf). The
        only pieces of data treated differently are the elements of
        core_services and other_services that are sent to async
        config.

        Services whose name begins with an underscore are ignored, so
        they can be commented out in the configuration file.

        path (string): the path of the TOML config file.

        """
        # Load config file.
        try:
            with open(path, 'rb') as f:
                data = tomli.load(f)
        except FileNotFoundError:
            logger.debug("Couldn't find config file %s.", path)
            return False
        except OSError as error:
            logger.warning("I/O error while opening file %s: [%s] %s",
                           path, errno.errorcode[error.errno],
                           os.strerror(error.errno))
            return False
        except ValueError as error:
            logger.warning("Invalid syntax in file %s: %s", path, error)
            return False

        logger.info("Using configuration file %s.", path)

        import json
        print(json.dumps(data,indent=2))

        if "is_proxy_used" in data:
            logger.warning("The 'is_proxy_used' setting is deprecated, please "
                           "use 'num_proxies_used' instead.")

        # Put core and test services in async_config, ignoring those
        # whose name begins with "_".
        for part in ("core_services", "other_services"):
            for service in data[part]:
                if service.startswith("_"):
                    continue
                for shard_number, shard in \
                        enumerate(data[part][service]):
                    coord = ServiceCoord(service, shard_number)
                    getattr(self.async_config, part)[coord] = Address(*shard)
            del data[part]

        # Put everything else in self.
        for key, value in data.items():
            for key2, value2 in value.items():
                setattr(getattr(self, key), key2, value2)

        return True


config = Config()
