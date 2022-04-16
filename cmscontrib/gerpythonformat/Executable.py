#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2017 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2014 Fabian Gundlach <320pointsguy@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from collections import abc
import hashlib
import json
import os.path
from cmscontrib.gerpythonformat.Messenger import print_block, header
from cms.rules.Rule import CommandRule, GCCRule, PythonFunctionRule
from six import iteritems

class Executable(object):
    """Abstract base class for executables suitable for e.g. solutions and
    generators. Examples are CPPProgram and InternalPython (see below).

    Overload run() in subclasses.

    Executables can be called with function-like syntax: a(5, 7, p="x")

    """

    def __init__(self):
        pass

    def p(self, *args, **kwargs):
        """Returns a new Executable which, when called, appends the given
        additional arguments.
        This cannot be used to specify stdin, stdout, stderr or dependencies.
        For keyword arguments, later calls supersede earlier ones and the
        arguments handed to __call__ supersede those given to this function.
        For example, a.p(p="x", q="y").p(p="y")(q="y") would
        use the keyword arguments p="y" and q="y".

        args (list): list of additional arguments

        kwargs (dict): dictionary of additional keyword arguments

        """
        return ParamsExecutable(self, args=args, kwargs=kwargs)

    def i(self, *args):
        """
        Returns an executable which, when called, writes the specified
        arguments (with "\n" after each argument) to a temporary file and
        redirects stdin from this file.
        """
        string = "".join("{}\n".format(a) for a in args)
        return ParamsExecutable(self, stdinstring=string)

    def ifi(self, filename):
        """
        Returns an executable which, when called, redirects stdin from the
        specified file.
        """
        return ParamsExecutable(self, stdin=filename)

    def _exerule(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        """Should return a rule object that is run when the executable is, if
        the executable is implemented using the rules system. Otherwise, it's
        left unimplemented.

        args (list): list of arguments that should be passed to the executable

        kwargs (dict): dictionary of keyword arguments that should be passed
                       to the executable

        stdin (string): name of the file to redirect input from

        stdinstring (string): string to pipe into stdin

        stdout (string): name of the file to redirect output to

        stderr (string): name of the file to redirect error output to

        dependencies (string): additional dependencies

        """
        raise NotImplementedError

    def _missionhash(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        """Should return the missionhash of a hypothetical run of the executable.
        This standard implementation assumes implementation using the rules
        system, with the rule to be run accessible through _exerule.

        args (list): list of arguments that should be passed to the executable

        kwargs (dict): dictionary of keyword arguments that should be passed
                       to the executable

        stdin (string): name of the file to redirect input from

        stdinstring (string): string to pipe into stdin

        stdout (string): name of the file to redirect output to

        stderr (string): name of the file to redirect error output to

        dependencies (string): additional dependencies

        """
        mission = self._exerule(args, kwargs, stdin, stdinstring, stdout,
                       stderr, dependencies).mission()
        hasher = hashlib.sha256()
        hasher.update(json.dumps(mission,
                                 sort_keys=True).encode('utf-8'))
        return hasher.hexdigest()

    def run(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        """Should run the executable.

        args (list): list of arguments that should be passed to the executable

        kwargs (dict): dictionary of keyword arguments that should be passed
                       to the executable

        stdin (string): name of the file to redirect input from

        stdinstring (string): string to pipe into stdin

        stdout (string): name of the file to redirect output to

        stderr (string): name of the file to redirect error output to

        dependencies (string): additional dependencies

        """
        raise NotImplementedError

    def missionhash(self, *args, **kwargs):
        """Provide convenient access to the missionhash.
        In many cases it should suffice to override the _missionhash method
        (or leave it, if the executable is implemented using the rules system).

        args (list): list of arguments that should be passed to the executable

        kwargs(dict): dictionary of keyword arguments that should be passed
                      to the executable;
                      If stdin, stdout, stderr or dependencies is specified,
                      the corresponding value will be discarded from the
                      keyword arguments and instead be passed to run().

        """
        stdin = kwargs.pop("stdin", None)
        stdinstring = kwargs.pop("stdinstring", None)
        stdout = kwargs.pop("stdout", None)
        stderr = kwargs.pop("stderr", None)
        dependencies = kwargs.pop("dependencies", [])

        return self._missionhash(args, kwargs, stdin=stdin, stdinstring=stdinstring,
                 stdout=stdout, stderr=stderr,
                 dependencies=dependencies)

    def __call__(self, *args, **kwargs):
        """Provide convenient access by making Executables callable.
        In many cases it should suffice to override the run method.

        args (list): list of arguments that should be passed to the executable

        kwargs(dict): dictionary of keyword arguments that should be passed
                      to the executable;
                      If stdin, stdout, stderr or dependencies is specified,
                      the corresponding value will be discarded from the
                      keyword arguments and instead be passed to run().

        """
        stdin = kwargs.pop("stdin", None)
        stdinstring = kwargs.pop("stdinstring", None)
        stdout = kwargs.pop("stdout", None)
        stderr = kwargs.pop("stderr", None)
        dependencies = kwargs.pop("dependencies", [])

        return self.run(args, kwargs, stdin=stdin, stdinstring=stdinstring,
                        stdout=stdout, stderr=stderr,
                        dependencies=dependencies)


class ParamsExecutable(Executable):
    """Helper class for specifying additional command line arguments.
    """

    def __init__(self, parent, args=tuple(), kwargs={},
                 stdin=None, stdinstring=None):
        """Initialize.

        parent (Executable): the Executable to be called

        args (list): the additional arguments

        kwargs (dict): the additional keyword arguments

        stdin (string): from where to redirect stdin

        stdinstring (string): string to pipe into stdin

        """
        self.parent = parent
        self.args = args
        self.kwargs = kwargs
        self.stdin = stdin
        self.stdinstring = stdinstring

    def _missionhash(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        k = kwargs.copy()
        k.update(self.kwargs)
        if stdin is None:
            stdin = self.stdin
        if stdinstring is None:
            stdinstring = self.stdinstring
        return self.parent._missionhash(args + self.args, k, stdin=stdin,
                        stdinstring=stdinstring, stdout=stdout,
                        stderr=stderr, dependencies=dependencies)

    def run(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        k = kwargs.copy()
        k.update(self.kwargs)
        if stdin is None:
            stdin = self.stdin
        if stdinstring is None:
            stdinstring = self.stdinstring
        return self.parent.run(args + self.args, k, stdin=stdin,
                               stdinstring=stdinstring, stdout=stdout,
                               stderr=stderr, dependencies=dependencies)

    def __str__(self):
        return "{} with additional arguments {}" \
            .format(self.parent.__str__(),
                    ", ".join([x for x in map(str, self.args)] +
                              [str(a) + "=" + str(b)
                               for a, b in iteritems(self.kwargs)]))


class ExitCodeException(Exception):
    pass


def keyword_list(kwords):
    """ Convert a keyword dictionary to something readable on
    the command line. Override this function, if neccessary.
    """
    L = []
    for elem in kwords:
        L += ["-" + str(elem), str(kwords[elem])]
    return L


def asy_keyword_list(kwords):
    """ Convert a keyword dictionary to something readable by
    asymptote on the command line
    """
    def encode(key, val):
        return ("-" if val else "-no") + str(key)

    return [encode(key, val) for key, val in kwords.items()]


class CPPProgram(Executable):
    """An Executable which is the binary resulting from compiling some c++
    source files.

    The source files are compiled whenever the Executable is run. The
    supplements are all build before each compilation.

    The rule system is used to compile/run the executable only if necessary.

    Arguments are handed over to the executable in the format
    "ARG1 ... ARGN -KEYWORD0 VALUE0 ... -KEYWORDM VALUEM".

    If the compiler or the executable returns with non-zero exit code, then
    an exception is thrown.

    """

    def __init__(self, rulesdir, conf, executable, sources=None):
        """Initialize.

        rulesdir (string): directory used for persistent data (for Rule)

        conf (CommonConfig): the "current" configuration object (used for
                             building supplements)

        executable (string): the base of the file name of the executable file;
                             the actual file name is basename.versionN where
                             N is a number that gets incremented each time the
                             sources are compiled (and that starts at 0 for
                             each instance of this class)
                             TODO improve this

        sources (list): the file names of the source files; if None, then it
                        is assumed that the only source file is executable.cpp.

        """
        self.rulesdir = rulesdir
        self.conf = conf
        self.executable = os.path.abspath(executable)
        if sources is None:
            sources = [executable + ".cpp"]
        self.sources = [os.path.abspath(s) for s in sources]
        self.nr = 0

    def wanted_path(self):
        """Return the file name of the executable file (including the version
        number).
        """
        return self.executable + ".version" + str(self.nr)

    def compilerule(self):
        """Return a rule for compiling the sources.
        """
        inc = [self.conf._get_inc_dir()]
        return GCCRule(self.rulesdir, self.sources, self.wanted_path(),
                       libdirs=inc)

    def compilenow(self):
        """Compiles the given sources using g++ if necessary (after building
        the cpp supplements).
        """
        self.conf._build_supplements("cpp")
        if not self.compilerule().uptodate():  # Compilation necessary
            self.nr += 1
            with header("Compile {} to {} using g++"
                        .format(",".join(self.conf.short_path(s)
                                         for s in self.sources),
                                self.conf.short_path(self.wanted_path())),
                        depth=10):
                r = self.compilerule().ensure()
                print_block(r.out)
                print_block(r.err)
                if r.code != 0:
                    raise Exception("Compilation failed")

    def _exerule(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        self.compilenow()
        return CommandRule(self.rulesdir,
                        [self.wanted_path()] +
                        list(args) +
                        keyword_list(kwargs),
                        stdin=stdin, stdinstring=stdinstring, stdout=stdout,
                        stderr=stderr, dependencies=dependencies)

    def run(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        self.compilenow()
        r = self._exerule(args, kwargs, stdin, stdinstring, stdout,
                    stderr, dependencies).ensure()
        if stderr is None:
            print_block(r.err)
        if r.code != 0:
            raise ExitCodeException(
                "Error executing program {} with parameters {}"
                .format(self.conf.short_path(self.wanted_path()),
                        str(list(args) + keyword_list(kwargs))))
        return r

    def __str__(self):
        return self.conf.short_path(self.executable)

    def get_path(self):
        """Return the path of the executable, compiling if necessary.
        """
        self.compilenow()
        return self.wanted_path()


class InternalPython(Executable):
    """An Executable which is actually a python function.

    File descriptors for stdin, stdout and stderr are passed to the function.
    """

    def __init__(self, f=None, additional_params=None):
        self.f = f
        self.path = str(f)
        self.fname = f.__qualname__
        # These are parameters that are "built into" f and therefore wouldn't
        # be visible in the mission dict if we didn't add them explicitly.
        # Specifically, the filename passed to explicit or the parameters
        # passed to verbatim (that get formed to an stdinstring).
        # TODO Couldn't we just make them parameters of the respective
        # function f in the definition of explicit and verbatim?
        self.additional_params = additional_params


    def mission(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        """
        A mission dict in analogy to a rule mission dict, only used to create a
        hash identifying the executable
        """
        return {'cwd': os.getcwd(),
                'type': 'internalpython',
                'name': self.fname,
                'additional_params': self.additional_params,
                'args': args,
                'kwargs': kwargs,
                'stdin': stdin,
                'stdinstring': stdinstring,
                'stdout': stdout,
                'stderr': stderr,
                'dependencies': dependencies}

    def _missionhash(self, args, kwargs, stdin=None, stdinstring=None,
                     stdout=None, stderr=None, dependencies=[]):
        mission = self.mission(args, kwargs, stdin, stdinstring, stdout,
                               stderr, dependencies)
        hasher = hashlib.sha256()
        hasher.update(json.dumps(mission,
                                 sort_keys=True).encode('utf-8'))
        return hasher.hexdigest()

    def run(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        # TODO: treat dependencies specially?
        kwargs = kwargs.copy()
        if stdin is not None:
            stdin = open(stdin, "r")
            kwargs["stdin"] = stdin
        if stdinstring is not None:
            kwargs["stdinstring"] = stdinstring
        if stdout is not None:
            stdout = open(stdout, "w")
            kwargs["stdout"] = stdout
        if stderr is not None:
            stderr = open(stderr, "w")
            kwargs["stderr"] = stderr
        self.f(*args, **kwargs)
        if stdin is not None:
            stdin.close()
        if stdout is not None:
            stdout.close()

    def __str__(self):
        return "<internal>"


class ExternalPython(Executable):
    """ An executable which is actually a python script containing a
    specific function.
    On each call of run the module is loaded and gen is performed if necessary.
    Other imported python modules that might change MUST be specified in the
    dependencies array or the function will not be re-run when they change.
    """

    def __init__(self, rulesdir, source, function="gen"):
        """Initialize.

        rulesdir (string): directory used for persistent data (for Rule)

        source (string): file name of the python script (should be in the
                         current working directory)

        function (string): name of the function to call ("gen" by default)

        """
        self.rulesdir = rulesdir
        if not source.endswith(".py"):
            raise Exception(
                "Python source file name '{}' doesn't end with '.py'.")
        self.name = "ext-python-" + source[:-3]
        self.path = os.path.abspath(source)
        self.function = function

    def _exerule(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        if stdin is not None or stdinstring is not None or stderr is not None:
            raise ExitCodeException(
                "Stdin, stdinstring and stderr are not implemented "
                "for ext_script.")
        return PythonFunctionRule(self.rulesdir,
                           self.path,
                           self.name,
                           self.function,
                           args,
                           kwargs,
                           stdout=stdout,
                           dependencies=dependencies)

    def run(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        self._exerule(args, kwargs, stdin, stdinstring, stdout,
                       stderr, dependencies).ensure()

    def __str__(self):
        return "<external>"


interpreter_table = {".py": "python2", ".rb": "ruby", ".pl": "perl",
                     ".sh": "/bin/bash"}


class ExternalScript(Executable):
    """An Executable which is actually a script file. The interpreter is
    automatically guessed from the file name extension.

    The rule system is used to run the script only if necessary.

    Arguments are handed over to the executable in the format
    "ARG1 ... ARGN -KEYWORD0 VALUE0 ... -KEYWORDM VALUEM".

    If the compiler returns with non-zero exit code, then
    an exception is thrown.

    """

    def __init__(self, rules, path=None):
        """Initialize.

        rulesdir (string): directory used for persistent data (for Rule)

        path (string): the file name of the script

        """
        self.rules = rules
        self.path = os.path.abspath(path)

    def _exerule(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        interpreter = None

        try:
            extension = os.path.splitext(self.path)[1]
            interpreter = interpreter_table[extension]
        except:
            raise Exception(
                "No interpreter for the extension '{}' of file '{}'"
                .format(extension, self.path))
            return None

        return CommandRule(self.rules,
                        [interpreter, self.path] +
                        list(args) +
                        keyword_list(kwargs),
                        stdin=stdin, stdinstring=stdinstring,
                        stdout=stdout, stderr=stderr,
                        dependonexe=False, dependencies=dependencies)

    def run(self, args, kwargs, stdin=None, stdinstring=None, stdout=None,
            stderr=None, dependencies=[]):
        r = self._exerule(args, kwargs, stdin, stdinstring, stdout,
                       stderr, dependencies).ensure()
        if stderr is None:
            print_block(r.err)
        if r.code != 0:
            raise ExitCodeException(
                "Error executing script {} with parameters {}"
                .format(self.path, str(list(args) + keyword_list(kwargs))))

    def get_path(self):
        return self.path
