#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2021 Tobias Lenz <t_lenz94@web.de>
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

import os

from cms import config
from cms.grading.Sandbox import IsolateSandbox
from cmscontrib.gerpythonformat import copyrecursivelyifnecessary

class LaTeXSandbox(IsolateSandbox):
    """
    A sandbox for compiling statements with (Lua)LaTeX
    """
    def __init__(self, *args, **kwargs):
        bid = 1000 + (os.getpid() % 8999) # 8999 is prime

        IsolateSandbox.__init__(self, *args, box_id=bid, **kwargs)

        copyrecursivelyifnecessary(os.path.join(os.path.expanduser("~"),
                                                config.latex_distro),
                                   os.path.join(self.get_home_path(),
                                                config.latex_distro),
                                   mode=0o777)

        self.preserve_env = True
        self.max_processes = config.latex_compilation_sandbox_max_processes
        self.timeout = config.latex_compilation_sandbox_max_time_s
        self.wallclock_timeout = 2 * self.timeout + 1
        self.address_space = config.latex_compilation_sandbox_max_memory_kib * 1024

        self.stdout_file = "LaTeX_out.txt"
        self.stderr_file = "LaTeX_err.txt"
        self.add_mapped_directory("/usr/share/texmf")
        self.add_mapped_directory("/etc/texmf")
        self.add_mapped_directory("/var/lib/texmf")
        self.add_mapped_directory(os.path.expanduser("~/texmf"))

        for d in config.latex_additional_dirs:
            self.add_mapped_directory(os.path.expanduser(d))

    def maybe_add_mapped_directory(self, src, dest=None, options=None):
        """
        We disable access to certain directories like /etc, that are unnecessary
        for TeX compilation but create potential security risks, by overwriting
        this method
        """
        pass

    def get_home_path(self):
        return os.path.join(self.get_root_path(), "home")

    def failed(self):
        return self.get_exit_status() != self.EXIT_OK

    def get_file_contents(self, filename, decoding="latin_1"):
        return self.get_file_to_string(filename, maxlen=None)\
                   .decode(decoding, errors="replace").strip()

    def get_stdout(self):
        return self.get_file_contents(self.stdout_file)

    def get_stderr(self):
        return self.get_file_contents(self.stderr_file)

    def get_log_file_contents(self):
        return self.get_file_contents("%s.%d" % (self.info_basename,
                                                 self.exec_num))
