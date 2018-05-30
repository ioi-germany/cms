#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2015 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import iteritems, with_metaclass

import io
import logging
import os
import resource
import select
import stat
import tempfile
from abc import ABCMeta, abstractmethod
from functools import wraps, partial

import gevent
from gevent import subprocess

from cms import config, rmtree
from cmscommon.commands import pretty_print_cmdline
from cmscommon.datetime import monotonic_time


logger = logging.getLogger(__name__)


class SandboxInterfaceException(Exception):
    pass


def with_log(func):
    """Decorator for presuming that the logs are present.

    """
    @wraps(func)
    def newfunc(self, *args, **kwargs):
        """If they are not present, get the logs.

        """
        if self.log is None:
            self.get_log()
        return func(self, *args, **kwargs)

    return newfunc


def wait_without_std(procs):
    """Wait for the conclusion of the processes in the list, avoiding
    starving for input and output.

    procs (list): a list of processes as returned by Popen.

    return (list): a list of return codes.

    """
    def get_to_consume():
        """Amongst stdout and stderr of list of processes, find the
        ones that are alive and not closed (i.e., that may still want
        to write to).

        return (list): a list of open streams.

        """
        to_consume = []
        for process in procs:
            if process.poll() is None:  # If the process is alive.
                if process.stdout and not process.stdout.closed:
                    to_consume.append(process.stdout)
                if process.stderr and not process.stderr.closed:
                    to_consume.append(process.stderr)
        return to_consume

    # Close stdin; just saying stdin=None isn't ok, because the
    # standard input would be obtained from the application stdin,
    # that could interfere with the child process behaviour
    for process in procs:
        if process.stdin:
            process.stdin.close()

    # Read stdout and stderr to the end without having to block
    # because of insufficient buffering (and without allocating too
    # much memory). Unix specific.
    to_consume = get_to_consume()
    while len(to_consume) > 0:
        to_read = select.select(to_consume, [], [], 1.0)[0]
        for file_ in to_read:
            file_.read(8192)
        to_consume = get_to_consume()

    return [process.wait() for process in procs]


class Truncator(io.RawIOBase):
    """Wrap a file-like object to simulate truncation.

    This file-like object provides read-only access to a limited prefix
    of a wrapped file-like object. It provides a truncated version of
    the file without ever touching the object on the filesystem.

    This class is only able to wrap binary streams as it relies on the
    readinto method which isn't provided by text (unicode) streams.

    """
    def __init__(self, fobj, size):
        """Wrap fobj and give access to its first size bytes.

        fobj (fileobj): a file-like object to wrap.
        size (int): the number of bytes that will be accessible.

        """
        self.fobj = fobj
        self.size = size

    def close(self):
        """See io.IOBase.close."""
        self.fobj.close()

    @property
    def closed(self):
        """See io.IOBase.closed."""
        return self.fobj.closed

    def readable(self):
        """See io.IOBase.readable."""
        return True

    def seekable(self):
        """See io.IOBase.seekable."""
        return True

    def readinto(self, b):
        """See io.RawIOBase.readinto."""
        # This is the main "trick": we clip (i.e. mask, reduce, slice)
        # the given buffer so that it doesn't overflow into the area we
        # want to hide (that is, out of the prefix) and then we forward
        # it to the wrapped file-like object.
        b = memoryview(b)[:max(0, self.size - self.fobj.tell())]
        return self.fobj.readinto(b)

    def seek(self, offset, whence=io.SEEK_SET):
        """See io.IOBase.seek."""
        # We have to catch seeks relative to the end of the file and
        # adjust them to the new "imposed" size.
        if whence == io.SEEK_END:
            if self.fobj.seek(0, io.SEEK_END) > self.size:
                self.fobj.seek(self.size, io.SEEK_SET)
            return self.fobj.seek(offset, io.SEEK_CUR)
        else:
            return self.fobj.seek(offset, whence)

    def tell(self):
        """See io.IOBase.tell."""
        return self.fobj.tell()

    def write(self, _):
        """See io.RawIOBase.write."""
        raise io.UnsupportedOperation('write')


class SandboxBase(with_metaclass(ABCMeta, object)):
    """A base class for all sandboxes, meant to contain common
    resources.

    """

    EXIT_SANDBOX_ERROR = 'sandbox error'
    EXIT_OK = 'ok'
    EXIT_SIGNAL = 'signal'
    EXIT_TIMEOUT = 'timeout'
    EXIT_TIMEOUT_WALL = 'wall timeout'
    EXIT_NONZERO_RETURN = 'nonzero return'

    def __init__(self, file_cacher, name=None, temp_dir=None):
        """Initialization.

        file_cacher (FileCacher): an instance of the FileCacher class
            (to interact with FS), if the sandbox needs it.
        name (string|None): name of the sandbox, which might appear in the
            path and in system logs.
        temp_dir (unicode|None): temporary directory to use; if None, use the
            default temporary directory specified in the configuration.

        """
        self.file_cacher = file_cacher
        self.name = name if name is not None else "unnamed"
        self.temp_dir = temp_dir if temp_dir is not None else config.temp_dir

        self.cmd_file = "commands.log"

        # These are not necessarily used, but are here for API compatibility
        # TODO: move all other common properties here.
        self.box_id = 0
        self.fsize = None
        self.cgroup = False
        self.dirs = []
        self.preserve_env = False
        self.inherit_env = []
        self.set_env = {}
        self.verbosity = 0

        self.max_processes = 1

        # Set common environment variables.
        # Specifically needed by Python, that searches the home for
        # packages.
        self.set_env["HOME"] = "./"

    def set_multiprocess(self, multiprocess):
        """Set the sandbox to (dis-)allow multiple threads and processes.

        multiprocess (bool): whether to allow multiple thread/processes or not.

        """
        if multiprocess:
            # Max processes is set to 1000 to limit the effect of fork bombs.
            self.max_processes = 1000
        else:
            self.max_processes = 1

    def get_stats(self):
        """Return a human-readable string representing execution time
        and memory usage.

        return (string): human-readable stats.

        """
        execution_time = self.get_execution_time()
        if execution_time is not None:
            time_str = "%.3f sec" % (execution_time)
        else:
            time_str = "(time unknown)"
        memory_used = self.get_memory_used()
        if memory_used is not None:
            mem_str = "%.2f MB" % (memory_used / (1024 * 1024))
        else:
            mem_str = "(memory usage unknown)"
        return "[%s - %s]" % (time_str, mem_str)

    @abstractmethod
    def get_root_path(self):
        """Return the toplevel path of the sandbox.

        return (string): the root path.

        """
        pass

    @abstractmethod
    def get_execution_time(self):
        """Return the time spent in the sandbox.

        return (float): time spent in the sandbox.

        """
        pass

    @abstractmethod
    def get_memory_used(self):
        """Return the memory used by the sandbox.

        return (int): memory used by the sandbox (in bytes).

        """
        pass

    @abstractmethod
    def get_killing_signal(self):
        """Return the signal that killed the sandboxed process.

        return (int): offending signal, or 0.

        """
        pass

    @abstractmethod
    def get_exit_status(self):
        """Get information about how the sandbox terminated.

        return (string): the main reason why the sandbox terminated.

        """
        pass

    @abstractmethod
    def get_exit_code(self):
        """Return the exit code of the sandboxed process.

        return (float): exitcode, or 0.

        """
        pass

    @abstractmethod
    def get_human_exit_description(self):
        """Get the status of the sandbox and return a human-readable
        string describing it.

        return (string): human-readable explaination of why the
                         sandbox terminated.

        """
        pass

    def relative_path(self, path):
        """Translate from a relative path inside the sandbox to a
        system path.

        path (string): relative path of the file inside the sandbox.

        return (string): the absolute path.

        """
        return os.path.join(self.get_root_path(), path)

    def create_file(self, path, executable=False):
        """Create an empty file in the sandbox and open it in write
        binary mode.

        path (string): relative path of the file inside the sandbox.
        executable (bool): to set permissions.

        return (file): the file opened in write binary mode.

        """
        if executable:
            logger.debug("Creating executable file %s in sandbox.", path)
        else:
            logger.debug("Creating plain file %s in sandbox.", path)
        real_path = self.relative_path(path)
        try:
            file_fd = os.open(real_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            file_ = io.open(file_fd, "wb")
        except OSError as e:
            logger.error("Failed create file %s in sandbox. Unable to "
                         "evalulate this submission. This may be due to "
                         "cheating. %s", real_path, e, exc_info=True)
            raise
        mod = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
        if executable:
            mod |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        os.chmod(real_path, mod)
        return file_

    def create_file_from_storage(self, path, digest, executable=False):
        """Write a file taken from FS in the sandbox.

        path (string): relative path of the file inside the sandbox.
        digest (string): digest of the file in FS.
        executable (bool): to set permissions.

        """
        with self.create_file(path, executable) as dest_fobj:
            self.file_cacher.get_file_to_fobj(digest, dest_fobj)

    def create_file_from_string(self, path, content, executable=False):
        """Write some data to a file in the sandbox.

        path (string): relative path of the file inside the sandbox.
        content (string): what to write in the file.
        executable (bool): to set permissions.

        """
        with self.create_file(path, executable) as dest_fobj:
            dest_fobj.write(content)

    def get_file(self, path, trunc_len=None):
        """Open a file in the sandbox given its relative path.

        path (str): relative path of the file inside the sandbox.
        trunc_len (int|None): if None, does nothing; otherwise, before
            returning truncate it at the specified length.

        return (file): the file opened in read binary mode.

        """
        logger.debug("Retrieving file %s from sandbox.", path)
        real_path = self.relative_path(path)
        file_ = io.open(real_path, "rb")
        if trunc_len is not None:
            file_ = Truncator(file_, trunc_len)
        return file_

    def get_file_text(self, path, trunc_len=None):
        """Open a file in the sandbox given its relative path, in text mode.

        Assumes encoding is UTF-8. The caller must handle decoding errors.

        path (str): relative path of the file inside the sandbox.
        trunc_len (int|None): if None, does nothing; otherwise, before
            returning truncate it at the specified length.

        return (file): the file opened in read binary mode.

        """
        logger.debug("Retrieving text file %s from sandbox.", path)
        real_path = self.relative_path(path)
        file_ = io.open(real_path, "rt", encoding="utf-8")
        if trunc_len is not None:
            file_ = Truncator(file_, trunc_len)
        return file_

    def get_file_to_string(self, path, maxlen=1024):
        """Return the content of a file in the sandbox given its
        relative path.

        path (str): relative path of the file inside the sandbox.
        maxlen (int): maximum number of bytes to read, or None if no
            limit.

        return (string): the content of the file up to maxlen bytes.

        """
        with self.get_file(path) as file_:
            if maxlen is None:
                return file_.read()
            else:
                return file_.read(maxlen)

    def get_file_to_storage(self, path, description="", trunc_len=None):
        """Put a sandbox file in FS and return its digest.

        path (str): relative path of the file inside the sandbox.
        description (str): the description for FS.
        trunc_len (int|None): if None, does nothing; otherwise, before
            returning truncate it at the specified length.

        return (str): the digest of the file.

        """
        with self.get_file(path, trunc_len=trunc_len) as file_:
            return self.file_cacher.put_file_from_fobj(file_, description)

    def stat_file(self, path):
        """Return the stats of a file in the sandbox.

        path (string): relative path of the file inside the sandbox.

        return (stat_result): the stat results.

        """
        return os.stat(self.relative_path(path))

    def file_exists(self, path):
        """Return if a file exists in the sandbox.

        path (string): relative path of the file inside the sandbox.

        return (bool): if the file exists.

        """
        return os.path.exists(self.relative_path(path))

    def remove_file(self, path):
        """Delete a file in the sandbox.

        path (string): relative path of the file inside the sandbox.

        """
        os.remove(self.relative_path(path))

    @abstractmethod
    def execute_without_std(self, command, wait=False):
        """Execute the given command in the sandbox using
        subprocess.Popen and discarding standard input, output and
        error. More specifically, the standard input gets closed just
        after the execution has started; standard output and error are
        read until the end, in a way that prevents the execution from
        being blocked because of insufficient buffering.

        command ([string]): executable filename and arguments of the
            command.
        wait (bool): True if this call is blocking, False otherwise

        return (bool|Popen): if the call is blocking, then return True
            if the sandbox didn't report errors (caused by the sandbox
            itself), False otherwise; if the call is not blocking,
            return the Popen object from subprocess.

        """
        pass

    @abstractmethod
    def translate_box_exitcode(self, _):
        """Translate the sandbox exit code to a boolean sandbox success.

        _ (int): the exit code of the sandbox.

        return (bool): False if the sandbox had an error, True if it
            terminated correctly (regardless of what the internal process
            did).

        """
        pass

    @abstractmethod
    def cleanup(self):
        """Cleanup the sandbox.

        To be called at the end of the execution, regardless of
        whether the sandbox should be deleted or not.

        """
        pass

    @abstractmethod
    def delete(self):
        """Delete the directory where the sandbox operated.

        """
        pass


class StupidSandbox(SandboxBase):
    """A stupid sandbox implementation. It has very few features and
    is not secure against things like box escaping and fork
    bombs. Yet, it is very portable and has no dependencies, so it's
    very useful for testing. Using in real contests is strongly
    discouraged.

    """

    def __init__(self, file_cacher, name=None, temp_dir=None):
        """Initialization.

        For arguments documentation, see SandboxBase.__init__.

        """
        SandboxBase.__init__(self, file_cacher, name, temp_dir)

        # Make box directory
        self.path = tempfile.mkdtemp(
            dir=self.temp_dir,
            prefix="cms-%s-" % (self.name))

        self.exec_num = -1
        self.popen = None
        self.popen_time = None
        self.exec_time = None

        logger.debug("Sandbox in `%s' created, using stupid box.", self.path)

        # Box parameters
        self.chdir = self.path
        self.stdin_file = None
        self.stdout_file = None
        self.stderr_file = None
        self.stack_space = None
        self.address_space = None
        self.timeout = None
        self.wallclock_timeout = None
        self.extra_timeout = None

    def get_root_path(self):
        """Return the toplevel path of the sandbox.

        return (string): the root path.

        """
        return self.path

    # TODO - It returns wall clock time, because I have no way to
    # check CPU time (libev doesn't have wait4() support)
    def get_execution_time(self):
        """Return the time spent in the sandbox.

        return (float): time spent in the sandbox.

        """
        return self.get_execution_wall_clock_time()

    # TODO - It returns the best known approximation of wall clock
    # time; unfortunately I have no way to compute wall clock time
    # just after the child terminates, because I have no guarantee
    # about how the control will come back to this class
    def get_execution_wall_clock_time(self):
        """Return the total time from the start of the sandbox to the
        conclusion of the task.

        return (float): total time the sandbox was alive.

        """
        if self.exec_time:
            return self.exec_time
        if self.popen_time:
            self.exec_time = monotonic_time() - self.popen_time
            return self.exec_time
        return None

    # TODO - It always returns None, since I have no way to check
    # memory usage (libev doesn't have wait4() support)
    def get_memory_used(self):
        """Return the memory used by the sandbox.

        return (int): memory used by the sandbox (in bytes).

        """
        return None

    def get_killing_signal(self):
        """Return the signal that killed the sandboxed process.

        return (int): offending signal, or 0.

        """
        if self.popen.returncode < 0:
            return -self.popen.returncode
        return 0

    # This sandbox only discriminates between processes terminating
    # properly or being killed with a signal; all other exceptional
    # conditions (RAM or CPU limitations, ...) result in some signal
    # being delivered to the process
    def get_exit_status(self):
        """Get information about how the sandbox terminated.

        return (string): the main reason why the sandbox terminated.

        """
        if self.popen.returncode >= 0:
            return self.EXIT_OK
        else:
            return self.EXIT_SIGNAL

    def get_exit_code(self):
        """Return the exit code of the sandboxed process.

        return (float): exitcode, or 0.

        """
        return self.popen.returncode

    def get_human_exit_description(self):
        """Get the status of the sandbox and return a human-readable
        string describing it.

        return (string): human-readable explaination of why the
                         sandbox terminated.

        """
        status = self.get_exit_status()
        if status == self.EXIT_OK:
            return "Execution successfully finished (with exit code %d)" % \
                self.get_exit_code()
        elif status == self.EXIT_SIGNAL:
            return "Execution killed with signal %s" % \
                self.get_killing_signal()

    def _popen(self, command,
               stdin=None, stdout=None, stderr=None,
               preexec_fn=None, close_fds=True):
        """Execute the given command in the sandbox using
        subprocess.Popen, assigning the corresponding standard file
        descriptors.

        command ([string]): executable filename and arguments of the
            command.
        stdin (file|None): a file descriptor/object or None.
        stdout (file|None): a file descriptor/object or None.
        stderr (file|None): a file descriptor/object or None.
        preexec_fn (function|None): to be called just before execve()
            or None.
        close_fds (bool): close all file descriptor before executing.

        return (object): popen object.

        """
        self.exec_time = None
        self.exec_num += 1

        logger.debug("Executing program in sandbox with command: `%s'.",
                     " ".join(command))
        with io.open(self.relative_path(self.cmd_file), 'at') as commands:
            commands.write("%s\n" % (pretty_print_cmdline(command)))
        try:
            p = subprocess.Popen(command,
                                 stdin=stdin, stdout=stdout, stderr=stderr,
                                 preexec_fn=preexec_fn, close_fds=close_fds)
        except OSError:
            logger.critical("Failed to execute program in sandbox "
                            "with command: `%s'.",
                            " ".join(command), exc_info=True)
            raise

        return p

    def execute_without_std(self, command, wait=False):
        """Execute the given command in the sandbox using
        subprocess.Popen and discarding standard input, output and
        error. More specifically, the standard input gets closed just
        after the execution has started; standard output and error are
        read until the end, in a way that prevents the execution from
        being blocked because of insufficient buffering.

        command ([string]): executable filename and arguments of the
            command.

        return (bool): True if the sandbox didn't report errors
            (caused by the sandbox itself), False otherwise

        """
        def preexec_fn(self):
            """Set limits for the child process.

            """
            if self.chdir:
                os.chdir(self.chdir)

            # TODO - We're not checking that setrlimit() returns
            # successfully (they may try to set to higher limits than
            # allowed to); anyway, this is just for testing
            # environment, not for real contests, so who cares.
            if self.timeout:
                rlimit_cpu = self.timeout
                if self.extra_timeout:
                    rlimit_cpu += self.extra_timeout
                rlimit_cpu = int(rlimit_cpu) + 1
                resource.setrlimit(resource.RLIMIT_CPU,
                                   (rlimit_cpu, rlimit_cpu))

            if self.address_space:
                rlimit_data = int(self.address_space * 1024)
                resource.setrlimit(resource.RLIMIT_DATA,
                                   (rlimit_data, rlimit_data))

            if self.stack_space:
                rlimit_stack = int(self.stack_space * 1024)
                resource.setrlimit(resource.RLIMIT_STACK,
                                   (rlimit_stack, rlimit_stack))

            # TODO - Doesn't work as expected
            # resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))

        # Setup std*** redirection
        if self.stdin_file:
            stdin_fd = os.open(os.path.join(self.path, self.stdin_file),
                               os.O_RDONLY)
        else:
            stdin_fd = subprocess.PIPE
        if self.stdout_file:
            stdout_fd = os.open(os.path.join(self.path, self.stdout_file),
                                os.O_WRONLY | os.O_TRUNC | os.O_CREAT,
                                stat.S_IRUSR | stat.S_IRGRP |
                                stat.S_IROTH | stat.S_IWUSR)
        else:
            stdout_fd = subprocess.PIPE
        if self.stderr_file:
            stderr_fd = os.open(os.path.join(self.path, self.stderr_file),
                                os.O_WRONLY | os.O_TRUNC | os.O_CREAT,
                                stat.S_IRUSR | stat.S_IRGRP |
                                stat.S_IROTH | stat.S_IWUSR)
        else:
            stderr_fd = subprocess.PIPE

        # Note down execution time
        self.popen_time = monotonic_time()

        # Actually call the Popen
        self.popen = self._popen(command,
                                 stdin=stdin_fd,
                                 stdout=stdout_fd,
                                 stderr=stderr_fd,
                                 preexec_fn=partial(preexec_fn, self),
                                 close_fds=True)

        # Close file descriptors passed to the child
        if self.stdin_file:
            os.close(stdin_fd)
        if self.stdout_file:
            os.close(stdout_fd)
        if self.stderr_file:
            os.close(stderr_fd)

        if self.wallclock_timeout:
            # Kill the process after the wall clock time passed
            def timed_killer(timeout, popen):
                gevent.sleep(timeout)
                # TODO - Here we risk to kill some other process that gets
                # the same PID in the meantime; I don't know how to
                # properly solve this problem
                try:
                    popen.kill()
                except OSError:
                    # The process had died by itself
                    pass

            # Setup the killer
            full_wallclock_timeout = self.wallclock_timeout
            if self.extra_timeout:
                full_wallclock_timeout += self.extra_timeout
            gevent.spawn(timed_killer, full_wallclock_timeout, self.popen)

        # If the caller wants us to wait for completion, we also avoid
        # std*** to interfere with command. Otherwise we let the
        # caller handle these issues.
        if wait:
            return self.translate_box_exitcode(
                wait_without_std([self.popen])[0])
        else:
            return self.popen

    def translate_box_exitcode(self, _):
        """Translate the sandbox exit code to a boolean sandbox success.

        This sandbox never fails.

        """
        return True

    def cleanup(self):
        """Cleanup the sandbox.

        This sandbox needs no cleanup.

        """
        pass

    def delete(self):
        """Delete the directory where the sandbox operated.

        """
        logger.debug("Deleting sandbox in %s.", self.path)

        # Delete the working directory.
        rmtree(self.path)


class IsolateSandbox(SandboxBase):
    """This class creates, deletes and manages the interaction with a
    sandbox. The sandbox doesn't support concurrent operation, not
    even for reading.

    The Sandbox offers API for retrieving and storing file, as well as
    executing programs in a controlled environment. There are anyway a
    few files reserved for use by the Sandbox itself:

     * commands.log: a text file with the commands ran into this
       Sandbox, one for each line;

     * run.log.N: for each N, the log produced by the sandbox when running
       command number N.

    """
    next_id = 0

    # If the command line starts with this command name, we are just
    # going to execute it without sandboxing, and with all permissions
    # on the current directory.
    SECURE_COMMANDS = ["/bin/cp", "/bin/mv", "/usr/bin/zip", "/usr/bin/unzip"]

    def __init__(self, file_cacher, name=None, temp_dir=None):
        """Initialization.

        For arguments documentation, see SandboxBase.__init__.

        """
        SandboxBase.__init__(self, file_cacher, name, temp_dir)

        # Isolate only accepts ids between 0 and 999 (by default). We assign
        # the range [(shard+1)*10, (shard+2)*10) to each Worker and keep the
        # range [0, 10) for other uses (command-line scripts like cmsMake or
        # direct console users of isolate). Inside each range ids are assigned
        # sequentially, with a wrap-around.
        # FIXME This is the only use of FileCacher.service, and it's an
        # improper use! Avoid it!
        if file_cacher is not None and file_cacher.service is not None:
            box_id = ((file_cacher.service.shard + 1) * 10
                      + (IsolateSandbox.next_id % 10)) % 1000
        else:
            box_id = IsolateSandbox.next_id % 10
        IsolateSandbox.next_id += 1

        # We create a directory "tmp" inside the outer temporary directory,
        # because the sandbox will bind-mount the inner one. The sandbox also
        # runs code as a different user, and so we need to ensure that they can
        # read and write to the directory. But we don't want everybody on the
        # system to, which is why the outer directory exists with no read
        # permissions.
        self.inner_temp_dir = "/tmp"
        self.outer_temp_dir = tempfile.mkdtemp(
            dir=self.temp_dir,
            prefix="cms-%s-" % (self.name))
        # Don't use os.path.join here, because the absoluteness of /tmp will
        # bite you.
        self.path = self.outer_temp_dir + self.inner_temp_dir
        os.mkdir(self.path)
        self.allow_writing_all()

        self.exec_name = 'isolate'
        self.box_exec = self.detect_box_executable()
        self.info_basename = "run.log"   # Used for -M
        self.log = None
        self.exec_num = -1
        logger.debug("Sandbox in `%s' created, using box `%s'.",
                     self.path, self.box_exec)

        # Default parameters for isolate
        self.box_id = box_id           # -b
        self.cgroup = config.use_cgroups  # --cg
        self.chdir = self.inner_temp_dir  # -c
        self.dirs = []                 # -d
        self.dirs += [(self.inner_temp_dir, self.path, "rw")]
        self.preserve_env = False      # -e
        self.inherit_env = []          # -E
        self.set_env = {}              # -E
        self.fsize = None              # -f
        self.stdin_file = None         # -i
        self.stack_space = None        # -k
        self.address_space = None      # -m
        self.stdout_file = None        # -o
        self.stderr_file = None        # -r
        self.timeout = None            # -t
        self.verbosity = 0             # -v
        self.wallclock_timeout = None  # -w
        self.extra_timeout = None      # -x

        # Set common environment variables.
        # Specifically needed by Python, that searches the home for
        # packages.
        self.set_env["HOME"] = "./"

        # Needed on Ubuntu by PHP (and more, ) that
        # have in /usr/bin only a symlink to one out of many
        # alternatives.
        if os.path.isdir("/etc/alternatives"):
            self.add_mapped_directories(["/etc/alternatives"])

        # On Arch Linux, JDK needs the following directory.
        if os.path.isdir("/etc/java-8-openjdk"):
            self.add_mapped_directories(["/etc/java-8-openjdk"])

        # Tell isolate to get the sandbox ready. We do our best to
        # cleanup after ourselves, but we might have missed something
        # if the worker was interrupted in the middle of an execution.
        self.cleanup()
        self.initialize_isolate()

    def add_mapped_directories(self, dirs):
        """Add dirs to the external dirs visible to the sandboxed command.

        dirs ([string]): list of dirs to make visible.

        """
        for directory in dirs:
            self.dirs.append((directory, None, "rw"))

    def allow_writing_all(self):
        """Set permissions in such a way that any operation is allowed.

        """
        os.chmod(self.path, 0o777)
        for filename in os.listdir(self.path):
            os.chmod(os.path.join(self.path, filename), 0o777)

    def allow_writing_none(self):
        """Set permissions in such a way that the user cannot write anything.

        """
        os.chmod(self.path, 0o755)
        for filename in os.listdir(self.path):
            os.chmod(os.path.join(self.path, filename), 0o755)

    def allow_writing_only(self, paths):
        """Set permissions in so that the user can write only some paths.

        paths ([string]): the only paths that the user is allowed to
            write.

        """
        # If one of the specified file do not exists, we touch it to
        # assign the correct permissions.
        for path in (os.path.join(self.path, path) for path in paths):
            if not os.path.exists(path):
                io.open(path, "wb").close()

        # Close everything, then open only the specified.
        self.allow_writing_none()
        for path in (os.path.join(self.path, path) for path in paths):
            os.chmod(path, 0o766)

    def get_root_path(self):
        """Return the toplevel path of the sandbox.

        return (string): the root path.

        """
        return self.path

    def detect_box_executable(self):
        """Try to find an isolate executable. It first looks in
        ./isolate/, then the local directory, then in a relative path
        from the file that contains the Sandbox module, then in the
        system paths.

        return (string): the path to a valid (hopefully) isolate.

        """
        paths = [os.path.join('.', 'isolate', self.exec_name),
                 os.path.join('.', self.exec_name)]
        if '__file__' in globals():
            paths += [os.path.abspath(os.path.join(
                      os.path.dirname(__file__),
                      '..', '..', 'isolate', self.exec_name))]
        paths += [self.exec_name]
        for path in paths:
            # Consider only non-directory, executable files with SUID flag on.
            if os.path.exists(path) \
                    and not os.path.isdir(path) \
                    and os.access(path, os.X_OK):
                st = os.stat(path)
                if st.st_mode & stat.S_ISUID != 0:
                    return path

        # As default, return self.exec_name alone, that means that
        # system path is used.
        return paths[-1]

    def build_box_options(self):
        """Translate the options defined in the instance to a string
        that can be postponed to mo-box as an arguments list.

        return ([string]): the arguments list as strings.

        """
        res = list()
        if self.box_id is not None:
            res += ["--box-id=%d" % self.box_id]
        if self.cgroup:
            res += ["--cg", "--cg-timing"]
        if self.chdir is not None:
            res += ["--chdir=%s" % self.chdir]
        for in_name, out_name, options in self.dirs:
            s = in_name
            if out_name is not None:
                s += "=" + out_name
            if options is not None:
                s += ":" + options
            res += ["--dir=%s" % s]
        if self.preserve_env:
            res += ["--full-env"]
        for var in self.inherit_env:
            res += ["--env=%s" % var]
        for var, value in iteritems(self.set_env):
            res += ["--env=%s=%s" % (var, value)]
        if self.fsize is not None:
            res += ["--fsize=%d" % self.fsize]
        if self.stdin_file is not None:
            res += ["--stdin=%s" % self.inner_absolute_path(self.stdin_file)]
        if self.stack_space is not None:
            res += ["--stack=%d" % self.stack_space]
        if self.address_space is not None:
            if self.cgroup:
                res += ["--cg-mem=%d" % self.address_space]
            else:
                res += ["--mem=%d" % self.address_space]
        if self.stdout_file is not None:
            res += ["--stdout=%s" % self.inner_absolute_path(self.stdout_file)]
        if self.max_processes is not None:
            res += ["--processes=%d" % self.max_processes]
        else:
            res += ["--processes"]
        if self.stderr_file is not None:
            res += ["--stderr=%s" % self.inner_absolute_path(self.stderr_file)]
        if self.timeout is not None:
            res += ["--time=%g" % self.timeout]
        res += ["--verbose"] * self.verbosity
        if self.wallclock_timeout is not None:
            res += ["--wall-time=%g" % self.wallclock_timeout]
        if self.extra_timeout is not None:
            res += ["--extra-time=%g" % self.extra_timeout]
        res += ["--meta=%s" % self.relative_path("%s.%d" % (self.info_basename,
                                                            self.exec_num))]
        res += ["--run"]
        return res

    def get_log(self):
        """Read the content of the log file of the sandbox (usually
        run.log.N for some integer N), and set self.log as a dict
        containing the info in the log file (time, memory, status,
        ...).

        """
        # self.log is a dictionary of lists (usually lists of length
        # one).
        self.log = {}
        info_file = "%s.%d" % (self.info_basename, self.exec_num)
        try:
            with self.get_file(info_file) as log_file:
                for line in log_file:
                    key, value = line.decode('utf-8').strip().split(":", 1)
                    if key in self.log:
                        self.log[key].append(value)
                    else:
                        self.log[key] = [value]
        except IOError as error:
            raise IOError("Error while reading execution log file %s. %r" %
                          (info_file, error))

    @with_log
    def get_execution_time(self):
        """Return the time spent in the sandbox, reading the logs if
        necessary.

        return (float): time spent in the sandbox.

        """
        if 'time' in self.log:
            return float(self.log['time'][0])
        return None

    @with_log
    def get_execution_wall_clock_time(self):
        """Return the total time from the start of the sandbox to the
        conclusion of the task, reading the logs if necessary.

        return (float): total time the sandbox was alive.

        """
        if 'time-wall' in self.log:
            return float(self.log['time-wall'][0])
        return None

    @with_log
    def get_memory_used(self):
        """Return the memory used by the sandbox, reading the logs if
        necessary.

        return (int): memory used by the sandbox (in bytes).

        """
        if 'cg-mem' in self.log:
            return int(self.log['cg-mem'][0]) * 1024
        return None

    @with_log
    def get_killing_signal(self):
        """Return the signal that killed the sandboxed process,
        reading the logs if necessary.

        return (int): offending signal, or 0.

        """
        if 'exitsig' in self.log:
            return int(self.log['exitsig'][0])
        return 0

    @with_log
    def get_exit_code(self):
        """Return the exit code of the sandboxed process, reading the
        logs if necessary.

        return (int): exitcode, or 0.

        """
        if 'exitcode' in self.log:
            return int(self.log['exitcode'][0])
        return 0

    @with_log
    def get_status_list(self):
        """Reads the sandbox log file, and set and return the status
        of the sandbox.

        return (list): list of statuses of the sandbox.

        """
        if 'status' in self.log:
            return self.log['status']
        return []

    def get_exit_status(self):
        """Get the list of statuses of the sandbox and return the most
        important one.

        return (string): the main reason why the sandbox terminated.

        """
        status_list = self.get_status_list()
        if 'XX' in status_list:
            return self.EXIT_SANDBOX_ERROR
        elif 'TO' in status_list:
            if 'message' in self.log and 'wall' in self.log['message'][0]:
                return self.EXIT_TIMEOUT_WALL
            else:
                return self.EXIT_TIMEOUT
        elif 'SG' in status_list:
            return self.EXIT_SIGNAL
        elif 'RE' in status_list:
            return self.EXIT_NONZERO_RETURN
        # OK status is not reported in the log file, it's implicit.
        return self.EXIT_OK

    def get_human_exit_description(self):
        """Get the status of the sandbox and return a human-readable
        string describing it.

        return (string): human-readable explaination of why the
                         sandbox terminated.

        """
        status = self.get_exit_status()
        if status == self.EXIT_OK:
            return "Execution successfully finished (with exit code %d)" % \
                self.get_exit_code()
        elif status == self.EXIT_SANDBOX_ERROR:
            return "Execution failed because of sandbox error"
        elif status == self.EXIT_TIMEOUT:
            return "Execution timed out"
        elif status == self.EXIT_TIMEOUT_WALL:
            return "Execution timed out (wall clock limit exceeded)"
        elif status == self.EXIT_SIGNAL:
            return "Execution killed with signal %s" % \
                self.get_killing_signal()
        elif status == self.EXIT_NONZERO_RETURN:
            return "Execution failed because the return code was nonzero"

    def inner_absolute_path(self, path):
        """Translate from a relative path inside the sandbox to an
        absolute path inside the sandbox.

        path (string): relative path of the file inside the sandbox.

        return (string): the absolute path of the file inside the sandbox.

        """
        return os.path.join(self.inner_temp_dir, path)

    def _popen(self, command,
               stdin=None, stdout=None, stderr=None,
               close_fds=True):
        """Execute the given command in the sandbox using
        subprocess.Popen, assigning the corresponding standard file
        descriptors.

        command ([string]): executable filename and arguments of the
            command.
        stdin (int|None): a file descriptor.
        stdout (int|None): a file descriptor.
        stderr (int|None): a file descriptor.
        close_fds (bool): close all file descriptor before executing.

        return (Popen): popen object.

        """
        self.log = None
        self.exec_num += 1

        # We run a selection of commands without isolate, as they need
        # to create new files. This is safe because these commands do
        # not depend on the user input.
        if command[0] in IsolateSandbox.SECURE_COMMANDS:
            logger.debug("Executing non-securely: %s at %s",
                         pretty_print_cmdline(command), self.path)
            try:
                prev_permissions = stat.S_IMODE(os.stat(self.path).st_mode)
                os.chmod(self.path, 0o700)
                with io.open(self.relative_path(self.cmd_file), 'at') as cmds:
                    cmds.write("%s\n" % (pretty_print_cmdline(command)))
                p = subprocess.Popen(command, cwd=self.path,
                                     stdin=stdin, stdout=stdout, stderr=stderr,
                                     close_fds=close_fds)
                os.chmod(self.path, prev_permissions)
                # For secure commands, we clear the output so that it
                # is not forwarded to the contestants. Secure commands
                # are "setup" commands, which should not fail or
                # provide information for the contestants.
                io.open(
                    os.path.join(self.path, self.stdout_file), "wb").close()
                io.open(
                    os.path.join(self.path, self.stderr_file), "wb").close()
                self._write_empty_run_log(self.exec_num)
            except OSError:
                logger.critical(
                    "Failed to execute program in sandbox with command: %s",
                    pretty_print_cmdline(command), exc_info=True)
                raise
            return p

        args = [self.box_exec] + self.build_box_options() + ["--"] + command
        logger.debug("Executing program in sandbox with command: `%s'.",
                     pretty_print_cmdline(args))
        # Temporarily allow writing new files.
        prev_permissions = stat.S_IMODE(os.stat(self.path).st_mode)
        os.chmod(self.path, 0o770)
        with io.open(self.relative_path(self.cmd_file), 'at') as commands:
            commands.write("%s\n" % (pretty_print_cmdline(args)))
        os.chmod(self.path, prev_permissions)
        try:
            p = subprocess.Popen(args,
                                 stdin=stdin, stdout=stdout, stderr=stderr,
                                 close_fds=close_fds)
        except OSError:
            logger.critical("Failed to execute program in sandbox "
                            "with command: %s", pretty_print_cmdline(args),
                            exc_info=True)
            raise

        return p

    def _write_empty_run_log(self, index):
        """Write a fake run.log file with no information."""
        with io.open(os.path.join(self.path, "run.log.%s" % index),
                     "wt", encoding="utf-8") as f:
            f.write("time:0.000\n")
            f.write("time-wall:0.000\n")
            f.write("max-rss:0\n")
            f.write("cg-mem:0\n")

    def execute_without_std(self, command, wait=False):
        """Execute the given command in the sandbox using
        subprocess.Popen and discarding standard input, output and
        error. More specifically, the standard input gets closed just
        after the execution has started; standard output and error are
        read until the end, in a way that prevents the execution from
        being blocked because of insufficient buffering.

        command ([string]): executable filename and arguments of the
            command.
        wait (bool): True if this call is blocking, False otherwise

        return (bool|Popen): if the call is blocking, then return True
            if the sandbox didn't report errors (caused by the sandbox
            itself), False otherwise; if the call is not blocking,
            return the Popen object from subprocess.

        """
        popen = self._popen(command, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            close_fds=True)

        # If the caller wants us to wait for completion, we also avoid
        # std*** to interfere with command. Otherwise we let the
        # caller handle these issues.
        if wait:
            return self.translate_box_exitcode(wait_without_std([popen])[0])
        else:
            return popen

    def translate_box_exitcode(self, exitcode):
        """Translate the sandbox exit code to a boolean sandbox success.

        Isolate emits the following exit codes:
        * 0 -> both sandbox and internal process finished successfully (meta
            file will contain "status:OK" -> return True;
        * 1 -> sandbox finished successfully, but internal process was
            terminated, e.g., due to timeout (meta file will contain
            status:x" with x in (TO, SG, RE)) -> return True;
        * 2 -> sandbox terminated with an error (meta file will contain
            "status:XX") -> return False.

        """
        if exitcode == 0 or exitcode == 1:
            return True
        elif exitcode == 2:
            return False
        else:
            raise SandboxInterfaceException("Sandbox exit status (%d) unknown"
                                            % exitcode)

    def initialize_isolate(self):
        """Initialize isolate's box."""
        init_cmd = (
            [self.box_exec]
            + (["--cg"] if self.cgroup else [])
            + ["--box-id=%d" % self.box_id, "--init"])
        ret = subprocess.call(init_cmd)
        if ret != 0:
            raise SandboxInterfaceException(
                "Failed to initialize sandbox with command: %s "
                "(error %d)" % (pretty_print_cmdline(init_cmd), ret))

    def cleanup(self):
        """Cleanup the sandbox.

        To be called at the end of the execution, regardless of
        whether the sandbox should be deleted or not.

        """
        # Tell isolate to cleanup the sandbox.
        subprocess.call(
            [self.box_exec]
            + (["--cg"] if self.cgroup else [])
            + ["--box-id=%d" % self.box_id]
            + ["--cleanup"],
            # Use subprocess.DEVNULL when dropping Python 2.
            stdout=io.open(os.devnull, "r+b"),
            stderr=subprocess.STDOUT)

    def delete(self):
        """Delete the directory where the sandbox operated.

        """
        logger.debug("Deleting sandbox in %s.", self.path)

        # Delete the working directory.
        rmtree(self.outer_temp_dir)


Sandbox = {
    'stupid': StupidSandbox,
    'isolate': IsolateSandbox,
    }[config.sandbox_implementation]
