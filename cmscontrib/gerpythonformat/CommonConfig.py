#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2017 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2013-2015 Fabian Gundlach <320pointsguy@gmail.com>
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

from cmscontrib.gerpythonformat.Messenger import print_msg, print_block, header
from cmscontrib.gerpythonformat.Executable import CPPProgram, InternalPython, ExternalScript, \
    ExternalPython, asy_keyword_list
from cms.rules.Rule import LaTeXRule, CommandRule, ZipRule
from cmscontrib.gerpythonformat.Supplement import easycall, def_latex, escape_latex, def_asy, escape_asy
import inspect
import io
import os
from collections import defaultdict
import copy
from datetime import timedelta
import shutil
import logging

logger = logging.getLogger(__name__)


def exported_function(f):
    """
    Decorator for making a method available to the configuration script
    """
    f.exported_function = True
    if f.__doc__ is None:
        f.__doc__ = ""
    f.__doc__ = "@exported_function\n\n" + f.__doc__
    return f


class Supplement(object):
    def __init__(self):
        self.files = set()
        self.parts = []

    def add_file(self, f):
        self.files.add(f)

    def add_part(self, f):
        self.parts.append(f)


class CommonConfig(object):
    """
    Base class for reading configuration files of contest or tasks,
    exporting some common methods.

    The methods marked with the @exported_function decorator are made
    available to the configuration file. Provides basic functions for the
    querying system.
    """

    def __init__(self, rules, ignore_latex=False):
        self.upstream = None
        self.rules = rules
        self.ignore_latex = ignore_latex

        # how to exchange data with upstream
        self.inheriting = False
        self.bequeathing = False

        self.supplements = defaultdict(Supplement)
        self.supplement_ext_to_key = defaultdict(list)
        # These extensions can also be used as keys:
        for ext in ["cpp", "latex", "asy"]:
            self.supplement_ext_to_key[ext].append(ext)

        # The dictionary containing the variables that will be made accessible
        # to the configuration file
        self.exported = {}

        # Export all methods declared with the @exported_function decorator
        for n, f in inspect.getmembers(self):
            if inspect.ismethod(f):
                try:
                    inc = f.exported_function
                except AttributeError:
                    inc = False
                if inc:
                    self.exported[n] = f

        self.exported["timedelta"] = timedelta

    # Run the configuration file

    def _readconfig(self, filename):
        """
        Read (and run) the configuration from the given file.
        The entries of self.exported are made accessible to the configuration
        script (as local and global variables).

        filename (string): file name of the configuration script

        """
        with open(os.path.abspath(filename), "rb") as f:
            code = compile(f.read(), os.path.abspath(filename), 'exec')
            exec(code, self.exported)

    # Supplements

    @exported_function
    def simple_query(self, what):
        """
        Return a function f returning self.what (at the time when f is
        called).

        what (string): name of the attribute to access

        """
        def f():
            return getattr(self, what)
        return f

    @exported_function
    def supplement_file(self, key, filename):
        """
        Set the storage file for supplements registered with the given
        file type.

        key (string): a string specifying for which purpose to use the
                      supplement

        filename (string): name of the file to save the supplements to

        """
        print_msg("Supplement file for {} set to {}".format(key, filename),
                  headerdepth=10)
        self.supplements[key].add_file(filename)

    @exported_function
    def supply(self, key, f):
        """
        Register the given supplement.

        key (string): a string specifying for which purpose to use the
                      supplement

        f: a function returning the string to supply or a constant string

        """
        self.supplements[key].add_part(f)

    @exported_function
    def supply_latex(self, name, f):
        self.supply("latex", def_latex(name, escape_latex(f)))

    @exported_function
    def supply_asy(self, name, f):
        self.supply("asy", def_asy(name, escape_asy(f)))

    @exported_function
    def register_supplement(self, key, extension):
        """
        Register a key to be used for compiling files with a specific
        extension.

        key (string): a string specifying a purpose to use the supplements for

        extension (string): the extension to use the supplements registered
                            under the given key for

        """
        self.supplement_ext_to_key[extension].append(key)

    def _build_supplements(self, ext):
        """
        Build the supplements for the given extension (i.e. overwrite all
        the files registered for a key referenced by this extension).

        ext (string): the extension

        """
        for key in self.supplement_ext_to_key[ext]:
            self._build_supplements_for_key(key)

    def _build_supplements_for_key(self, key):
        """
        Build the supplements for the given key (i.e. overwrite all
        the files registered for this key).

        key (string): a string specifying a purpose to use the supplements for

        """
        files = self.supplements[key].files
        parts = self.supplements[key].parts

        out = ""
        for s in parts:
            out += easycall(s)
        for fname in files:
            with io.open(fname, 'w', encoding="utf-8") as f:
                f.write(out)

    def _get_supplement_extension_files(self, ext):
        """
        Get all supplements registered with a given extension.

        ext (string): the extension

        return (list): list of Supplement objects for this extension

        """
        L = []
        for key in self.supplement_ext_to_key[ext]:
            L += copy.deepcopy(self.supplements[key].files)
        return L

    def _inherit_supplements(self, t):
        """
        Add all supplement information from t
        Since supplements are not named, there will be no overriding
        """
        self.supplements = copy.deepcopy(t.supplements)
        self.supplement_ext_to_key = copy.deepcopy(t.supplement_ext_to_key)

    def _inherit(self):
        """
        Get all information from upstream
        """
        if self.upstream is None:
            return
        self._inherit_supplements(self.upstream)

    def _bequeath(self):
        """
        Give all information to upstream
        """
        if self.upstream is None:
            return
        self.upstream.inherit_supplements(self)

    def __enter__(self):
        if self.inheriting:
            self._inherit()
        return self

    def __exit__(self, a, b, c):
        if self.bequeathing:
            self._bequeath()

    def _get_inc_dir(self):
        return os.path.join(os.path.dirname(__file__), "lib", "include")

    def _get_ready_dir(self):
        return os.path.join(os.path.dirname(__file__), "lib", "ready")

    # Compilation

    @exported_function
    def compilecpp(self, *args, **kwargs):
        """
        See CPPProgram.
        """
        return CPPProgram(self.rules, self, *args, **kwargs)

    @exported_function
    def compilelatex(self, basename):
        """
        Use latexmk to compile basename.tex to basename.pdf .

        This command also creates a directory basename.kit containing all the
        files necessary to compile the tex source. This can be useful for
        translation sessions.

        basename (string): base of the tex and pdf file names

        return (string): file name of the generated pdf file

        """
        source = basename + ".tex"
        output = basename + ".pdf"

        if self.ignore_latex:
            return output

        with header("Compile {} to {} using LaTeX"
                    .format(self.short_path(source), self.short_path(output)),
                    depth=10):
            self._build_supplements("latex")

            r = LaTeXRule(self.rules, source).ensure()
            print_block(r.out)
            print_block(r.err)
            if r.code != 0:
                raise Exception("Compilation failed")

            # Create "translation kit" containing all important dependencies
            kit_directory = basename + ".kit"
            if os.path.exists(kit_directory):
                shutil.rmtree(kit_directory)
            for dep in r.dependencies:
                depabs = os.path.abspath(dep)
                wdirpath = os.path.abspath(self.wdir) + '/'
                # We don't want to include global latex style files, etc.
                if depabs.startswith(wdirpath):
                    basefile = depabs[len(wdirpath):]
                    basefiledir = os.path.join(kit_directory,
                                               os.path.dirname(basefile))
                    if not os.path.exists(basefiledir):
                        os.makedirs(basefiledir)
                    shutil.copy(depabs, os.path.join(kit_directory, basefile))

        return output

    @exported_function
    def compileasy(self, basename, stdin=None, output=None, pdf=True,
                   **kwargs):
        """
        Compile and run an asymptote file to generate a pdf file.

        basename (string): base of the asymptote file name: basename.asy

        stdin (string): file to redirect stdin from (if not None)

        output (string): file name of the picture to generate (by default
                         basename.eps or basename.pdf, cf. next parameter)

        pdf (boolean): whether we should generate a pdf file (True by default)

        The remaining keyword arguments are passed to asy as command line
        arguments.

        """
        source = basename + ".asy"
        if output is None:
            output = basename + (".pdf" if pdf else ".eps")

        with header("Compile {} to {} using Asymptote"
                    .format(self.short_path(source), self.short_path(output)),
                    depth=10):
            self._build_supplements("asy")

            # Asymptote does not tell us the dependencies, so we have to guess
            dep = [source] + self._get_supplement_extension_files("asy")

            r = CommandRule(self.rules,
                            ["asy"] + (["-f", "pdf"] if pdf else []) +
                            ["-o", output] + asy_keyword_list(kwargs) +
                            [source], stdin=stdin, dependencies=dep,
                            outputs=[output], dependonexe=False).ensure()
            print_block(r.out)
            print_block(r.err)
            if r.code != 0:
                raise Exception("Compilation failed")
        return output

    @exported_function
    def compile(self, filename, **kwargs):
        """
        Compile, automatically guessing appropriate extensions and
        compilation methods. See compilecpp, compilelatex, compileasy.

        filename (string): name of the file to compile or its
                           basename (without extension)

        The remaining arguments are passed to compilecpp, etc.

        """
        extmap = {".cpp": self.compilecpp,
                  ".tex": self.compilelatex,
                  ".asy": self.compileasy}

        basename, extension = os.path.splitext(filename)
        if extension == "":
            ok = [e for e in extmap if os.path.isfile(filename + e)]
            if len(ok) == 0:
                raise Exception("Could not find a suitable extension for {}"
                                .format(filename))
            elif len(ok) > 1:
                raise Exception("Found multiple suitable extensions for {}: "
                                "{}".format(filename, ', '.join(ok)))
            else:
                extension = ok[0]
        try:
            f = extmap[extension]
        except KeyError:
            raise Exception("Extension {} not known".format(extension))
        x = f(basename, **kwargs)
        return x

    # Zip file

    @exported_function
    def make_zip(self, zipname, contents):
        zipfile = os.path.abspath(zipname)
        with header("Creating zip file {}"
                    .format(self.short_path(zipfile)),
                    depth=10):

            r = ZipRule(self.rules, zipfile, contents).ensure()
        return zipfile

    # Executables

    @exported_function
    def encapsulate(self, *args, **kwargs):
        """
        See InternalPython.
        """
        return InternalPython(*args, **kwargs)

    @exported_function
    def ext_script(self, *args, **kwargs):
        """
        See ExternalScript.
        """
        return ExternalScript(self.rules, *args, **kwargs)

    @exported_function
    def ext_python(self, *args, **kwargs):
        """
        See ExternalPython
        """
        return ExternalPython(self.rules, *args, **kwargs)

    # Tokens

    @exported_function
    def no_tokens(self):
        """
        Specify that there are no tokens available.
        """
        self.token_mode = "disabled"

    @exported_function
    def infinite_tokens(self):
        """
        Specify that there are infinitely many tokens available.
        """
        self.token_mode = "infinite"

    @exported_function
    def tokens(self, gen_initial, gen_number, gen_interval, gen_max,
               min_interval, max_number):
        """
        Specify the number of tokens available.

        initial (int): number of tokens at the beginning of the contest

        gen_number (int): number of tokens to generate each time

        gen_time (timedelta): how often new tokens are generated

        max (int): limit for the number of tokens at any time

        min_interval (timedelta): time the user has to wait after using a
                                  token before he can use another token

        total (int): maximum number of tokens the user can use in total

        """
        self.token_mode = "finite"
        self.token_max_number = max_number
        self.token_min_interval = min_interval
        self.token_gen_initial = gen_initial
        self.token_gen_number = gen_number
        self.token_gen_interval = gen_interval
        self.token_gen_max = gen_max

    def _set_tokens(self, obj):
        """Applies the token settings to the given db object (Contest or Task).

        obj (Contest or Task): the database object

        """
        obj.token_mode = self.token_mode
        if self.token_mode == "finite":
            obj.token_max_number = self.token_max_number
            obj.token_min_interval = self.token_min_interval
            obj.token_gen_initial = self.token_gen_initial
            obj.token_gen_number = self.token_gen_number
            obj.token_gen_interval = self.token_gen_interval
            obj.token_gen_max = self.token_gen_max

    # Submission and user test limits

    @exported_function
    def submission_limits(self, max_number, min_interval):
        """
        Set limits on the frequency of submissions.

        max_number (int): maximum number of submissions

        min_interval (timedelta): time the user has to wait after submitting
                                  before he can submit again

        """
        self.max_submission_number = max_number
        self.min_submission_interval = min_interval

    @exported_function
    def user_test_limits(self, max_number, min_interval):
        """
        Set limits on the frequency of user tests.

        max_number (int): maximum number of user tests

        min_interval (timedelta): time the user has to wait after submitting
                                  a user test before he can submit a user test
                                  again

        """
        self.max_user_test_number = max_number
        self.min_user_test_interval = min_interval
