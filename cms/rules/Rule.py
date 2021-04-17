#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013-2016 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2018-2021 Tobias Lenz <t_lenz94@web.de>
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

import hashlib
import imp
import io
import json
import os
import stat
import subprocess
import time
import shlex

from cms import config
from cmscontrib.gerpythonformat.LaTeXSandbox import LaTeXSandbox
from cms.db.filecacher import FileCacher
from cmscontrib.gerpythonformat import copyifnecessary, copyrecursivelyifnecessary
from cmscontrib.gerpythonformat.LocationStack import chdir

from six import iteritems
from copy import copy

from cms import config

def compute_file_hash(filename):
    """Return the sha256 sum of the given file.
    """
    with io.open(filename, 'rb') as f:
        hasher = hashlib.sha256()
        while True:
            data = f.read(2**14)
            if not data:
                break
            hasher.update(data)
        return hasher.hexdigest()


def readfile(filename, encoding="utf-8"):
    """Return the contents of the given file.
    """
    with io.open(filename, 'r', encoding=encoding) as f:
        return f.read()


def deletefile(filename):
    """Remove the given file if it exists.
    """
    if os.path.exists(filename):
        os.remove(filename)


class Rule(object):
    """Base class for make-like rules.
    """

    def __init__(self, rulesdir):
        """Initializes a rule.

        rulesdir (string): directory used for persistent data

        """
        self.rulesdir = rulesdir
        self.result = None
        if not os.path.isdir(rulesdir):
            os.mkdir(rulesdir)

    def mission(self):
        """Return a dictionary specifying what to do.
        """
        raise NotImplementedError

    def missionhashfile(self):
        """Return the name of the file to which the results are saved.
        """
        hasher = hashlib.sha256()
        hasher.update(json.dumps(self.mission(),
                                 sort_keys=True).encode('utf-8'))
        return os.path.join(self.rulesdir, hasher.hexdigest())

    def run(self):
        """Run the rule (do what you have to do).

        This function should add dependencies, outputs and other results
        to self.result.

        Warning: Modifying a dependency inside run() may lead to
                 unexpected behaviour.

        Warning: Rules do not properly support recursion.
                 Do not run another rule from this function!

        """
        raise NotImplementedError

    def load(self):
        """Gets called if the rule is not run this time.
        """
        pass

    def finish(self):
        """Gets called after running/loading.
        """
        pass

    def uptodate(self):
        """Returns whether the rule results are up to date (meaning that the
        rule doesn't have to be run).
        """
        mhf = self.missionhashfile()
        if not os.path.exists(mhf):
            return False
        with io.open(mhf, 'r') as f:
            r = RuleResult.import_from_dict(self.rulesdir,
                                            json.load(f)['result'])
            return r.uptodate()

    def ensure(self, force=False):
        """Runs the rule if necessary, otherwise loads and returns the results.
        If the rule is not run, then load() is called after loading the
        results.
        Finally, finish() is called.

        force (bool): Whether the rule should be run even if that doesn't seem
                      necessary.

        """
        self.result = None
        mhf = self.missionhashfile()
        if not force:
            if os.path.exists(mhf):
                with io.open(mhf, 'rb') as f:
                    result = \
                        RuleResult.import_from_dict(self.rulesdir,
                                                    json.load(f)['result'])
                    if result.uptodate():
                        self.result = result
        if self.result is None:
            self.result = RuleResult(self.rulesdir)
            self.run()
            # Don't save the result if something really bad happened (e.g. the
            # dependencies could not be determined)
            if not self.result.badfail:
                with io.open(mhf, 'w') as f:
                    # Save the result.
                    # The mission is saved for debugging purposes.
                    json.dump({'mission': self.mission(),
                               'result': self.result.export_to_dict()}, f)
        else:
            self.load()
        self.finish()
        return self.result


class RuleResult(object):
    def __init__(self, rulesdir, dependencies={}, outputs={}, log={}):
        """Initialise the result of a rule execution.

        dependencies (dict): dictionary mapping each dependency file name to
                             its expected hash

        outputs (dict): dictionary mapping each output file name to its
                        expected hash

        The dependencies and outputs dictionaries currently behave in exactly
        the same way.

        log (dict): dictionary consisting of results (e.g. exit codes, stdout)
                    which should be persistent

        badfail (bool): if True, then the result will not be saved

        """
        self.rulesdir = rulesdir
        self.dependencies = dict(dependencies)
        self.outputs = dict(outputs)
        self.log = dict(log)
        self.badfail = False

    def hash_of_file(self, filename):
        """Return the hash of the given file.
        """
        filename = os.path.abspath(filename)

        try:
            sta = os.lstat(filename)
        except FileNotFoundError:
            # Not a file
            return None

        if stat.S_ISLNK(sta.st_mode):
            # Symbolic link
            target = os.readlink(filename)
            abstarget = os.path.join(os.path.dirname(filename), target)
            return ["link", target, self.hash_of_file(abstarget)]

        assert stat.S_ISREG(sta.st_mode)

        if config.always_recompute_hash:
            return compute_file_hash(filename)

        # TODO Check that the following works reliably on all systems.
        # For example, getctime sometimes only has a precision of 1 second.

        hasher = hashlib.sha256()
        hasher.update(json.dumps({'type': 'filehash',
                                  'file': filename},
                                 sort_keys=True).encode('utf-8'))
        hashfile = os.path.join(self.rulesdir, hasher.hexdigest())
        if os.path.exists(hashfile):
            with io.open(hashfile, "r") as f:
                stahash = os.fstat(f.fileno())
                res = json.load(f)
                # Check that the ctime is the same as when we last computed
                # the hash.
                # Also check that the ctime is more than 3 seconds before
                # the hashfile's ctime.
                if res['type'] == 'filehash' and \
                        res['file'] == filename and \
                        res['ctime'] == sta.st_ctime_ns and \
                        sta.st_ctime_ns + 3000000000 < stahash.st_ctime_ns:
                    return res['hash']

        ## Only remember this hash if the file's ctime is at least 10 seconds ago.
        ## Thus, if the file changes after hashing, its ctime has to change, too.
        ## (Even if ctime has only low resolution!)
        ## See also https://mirrors.edge.kernel.org/pub/software/scm/git/docs/technical/racy-git.html.
        time_before_hash = time.time()
        #print("Reading {} to compute hash".format(filename))
        hash_ = compute_file_hash(filename)
        if os.path.getctime(filename)+10 < time_before_hash:
            with io.open(hashfile, 'w', encoding='utf-8') as f:
                json.dump({'type': 'filehash', 'file': filename, 'ctime': sta.st_ctime_ns, 'hash': hash_}, f)

        return hash_

    def add_dependency(self, filename):
        """Add a file using its current hash value.
        """
        self.dependencies[filename] = self.hash_of_file(filename)

    def add_output(self, filename):
        """Add a file using its current hash value.
        """
        self.outputs[filename] = self.hash_of_file(filename)

    def uptodate(self):
        """Whether the saved hash values all agree with the current files.
        """
        for di in (self.dependencies, self.outputs):
            for filename, oldhash in iteritems(di):
                newhash = self.hash_of_file(filename)
                if oldhash != newhash:
                    #print("Out of date: {}, old hash {}, new hash {}".format(filename, oldhash, newhash))
                    return False
        return True

    def export_to_dict(self):
        return {'dependencies': self.dependencies,
                'outputs': self.outputs,
                'log': self.log}

    @classmethod
    def import_from_dict(cls, rulesdir, data):
        return cls(rulesdir=rulesdir, **data)


class CommandRule(Rule):
    def __init__(self, rulesdir, command, dependencies=[], outputs=[],
                 stdin=None, stdinstring=None,
                 stdout=None, stderr=None, dependonexe=True,
                 read_stdout=True, read_stderr=True):
        """A rule running the given command.
        The exit code is saved to result.code.

        rulesdir (string): directory used for persistent data

        command (list): array specifying the command and its arguments

        stdin (string): if specified, redirect input from this file

        stdinstring (string): if specified, pipe the contents of this string
                              to stdin

        stdout (string): if specified, redirect output to this file;
                         if not specified, the output is redirected to
                         .out and saved to result.out

        stderr (string): if specified, redirect error output to this file;
                         if not specified, the error output is redirected to
                         .err and saved to result.err

        dependencies (list): additional dependencies (apart from stdin
                             and the executable)

        outputs (list): additional outputs (apart from stdout and stderr)

        dependonexe (bool): whether the executable should be considered a
                            dependency

        read_stdout (bool): whether stdout should be saved automatically

        read_stderr (bool): whether stderr should be saved automatically

        """
        super(CommandRule, self).__init__(rulesdir)
        self.command = [x for x in map(str, command)]
        self.dependencies = dependencies
        self.outputs = outputs
        self.stdin = stdin
        self.stdinstring = stdinstring
        self.stdout = stdout
        self.stderr = stderr
        self.read_stdout = read_stdout
        self.read_stderr = read_stderr
        self.dependonexe = dependonexe
        if self.stdin is not None and self.stdinstring is not None:
            raise Exception("You can't redirect stdin from a file and a "
                            "string at the same time")

    def mission(self):
        return {'cwd': os.getcwd(),
                'type': 'command',
                'command': self.command,
                'dependencies': self.dependencies,
                'outputs': self.outputs,
                'stdin': self.stdin,
                'stdinstring': self.stdinstring,
                'stdout': self.stdout,
                'stderr': self.stderr,
                'read_stdout': self.read_stdout,
                'read_stderr': self.read_stderr,
                'dependonexe': self.dependonexe}

    def pre_run(self):
        """Called immediately before running the command.
        """
        pass

    def post_run(self):
        """Called immediately after running the command.
        """
        pass

    def run(self):
        self.pre_run()
        stdin = self.stdin
        if self.stdinstring:
            stdin = ".in"
            with io.open(stdin, "w", encoding="utf-8") as f:
                f.write(self.stdinstring)
        of = ".out" if self.stdout is None else self.stdout
        ef = ".err" if self.stderr is None else self.stderr
        with io.open(of, 'w', encoding="utf-8") as fout:
            with io.open(ef, 'w', encoding="utf-8") as ferr:
                fin = None
                if stdin is not None:
                    fin = io.open(stdin, 'r', encoding="utf-8")
                self.result.log['code'] = subprocess.call(self.command,
                                                          stdin=fin,
                                                          stdout=fout,
                                                          stderr=ferr)
                if stdin is not None:
                    fin.close()
        if self.stdout is None and self.read_stdout:
            self.result.log['out'] = readfile(".out")
        if self.stderr is None and self.read_stderr:
            self.result.log['err'] = readfile(".err")
        self.post_run()
        for f in self.dependencies:
            self.result.add_dependency(f)
        if self.dependonexe:
            self.result.add_dependency(self.command[0])
        if self.stdin is not None:
            self.result.add_dependency(self.stdin)
        for f in self.outputs:
            self.result.add_output(f)
        if self.stdout is not None:
            self.result.add_output(self.stdout)
        if self.stderr is not None:
            self.result.add_output(self.stderr)

    def finish(self):
        self.result.code = self.result.log['code']
        if self.stdout is None:
            self.result.out = self.result.log['out']
        if self.stderr is None:
            self.result.err = self.result.log['err']


def readmakefile(filename, result, readoutput):
    """Load dependencies and outputs from a makefile.

    filename (string): the name of the makefile

    result (RuleResult): the object to save the dependencies and outputs to

    readoutput (bool): whether to load outputs (not only dependencies)

    """
    if not os.path.exists(filename):  # We cannot find out the dependencies
        result.badfail = True
        return
    with io.open(filename, 'r', encoding="utf-8") as f:
        # FIXME The makefile parsing is far from perfect...
        aftercolon = False
        for line in f:
            if line[-1] == "\n":
                line = line[:-1]
            if line[-1] == "\\":
                line = line[:-1]

            token = ""
            escape = False
            dollarescape = False

            def finishtoken():
                if token == "":
                    pass
                elif not aftercolon:
                    if readoutput and token != filename:
                        result.add_output(token)
                else:
                    result.add_dependency(token)

            for i, c in enumerate(line):
                newescape = False
                newdollarescape = False
                if c == '$':
                    if dollarescape:
                        token += "$"
                    else:
                        newdollarescape = True
                else:
                    if dollarescape:
                        raise Exception("Unescaped dollar in Makefile rule")
                    elif c == '#' and not escape:
                        break
                    elif c == '\\' and not escape:
                        newescape = True
                    elif c == ' ' and not escape:
                        finishtoken()
                        token = ""
                    elif c == ':' and not escape:
                        finishtoken()
                        token = ""
                        aftercolon = True
                    else:
                        token += c
                escape = newescape
                dollarescape = newdollarescape
            finishtoken()
            token = ""


class GCCRule(CommandRule):
    def __init__(self, rulesdir, sources, output, libdirs=[]):
        """Compiles sources using g++ -O2 -std=gnu++17 -Wall.
        The dependencies are automatically detected.

        rulesdir (string): directory used for persistent data

        sources (list): source file names

        output (string): executable file name

        libdirs (list): additional directories to be searched for header files

        """
        gcc_command = ["g++", "-O2", "-std=gnu++17", "-Wall", "-o", output,
                       "-MMD", "-MF", ".deps", "-static",
                       "-fdiagnostics-color=always"]
        for l in libdirs:
            gcc_command += ["-I", l]
        gcc_command += sources

        super(GCCRule, self).__init__(rulesdir, gcc_command, dependonexe=False)
        self.sources = sources
        self.output = output
        self.libdirs = libdirs

    def mission(self):
        return {'cwd': os.getcwd(),
                'type': 'gcc',
                'sources': self.sources,
                'output': self.output,
                'libdirs': self.libdirs}

    def pre_run(self):
        # Delete the dependencies file before running g++ to ensure
        # that we don't read a left-over dependencies file in the end
        # (if g++ fails to write the dependencies file).
        deletefile(".deps")

    def post_run(self):
        for s in self.sources:
            self.result.add_dependency(s)  # Should not be necessary
        self.result.add_output(self.output)
        readmakefile(".deps", self.result, False)


class LaTeXRule(CommandRule):
    def __init__(self, rulesdir, source,
                 extra=["-pdflatex=pdflatex -interaction=nonstopmode %O %S"]):
        """Compiles a source using latexmk -pdf.
        The dependencies are automatically detected.

        rulesdir (string): directory used for persistent data

        source (string): the TeX file to compile

        extra (string): additional command line arguments passed to latexmk

        """
        command = ["latexmk", "-g", "-pdflua",
                   "-latexoption=-interaction=nonstopmode",
                   "-deps", "-deps-out=.deps"] + extra + [source]
        super(LaTeXRule, self).__init__(rulesdir, command, dependonexe=False,
                                        read_stdout=False, read_stderr=False)
        self.source = source
        self.extra = extra

    def mission(self):
        return {'cwd': os.getcwd(),
                'type': 'latex',
                'source': self.source,
                'extra': self.extra}

    def pre_run(self):
        # Delete the dependencies file before running latex to ensure
        # that we don't read a left-over dependencies file in the end
        # (if latex fails to write the dependencies file).
        deletefile(".deps")

    def post_run(self):
        # Don't save the result if LaTeX failed.
        # (We don't reliably detect when a previously missing file was added,
        # for example when a missing package was installed.)
        if self.result.log['code']:
            self.result.badfail = True
        self.result.add_dependency(self.source)  # Should not be necessary
        readmakefile(".deps", self.result, True)
        # Latexmk seems to output latin_1 instead of utf8.
        self.result.log['out'] = readfile(".out", "latin_1")
        self.result.log['err'] = readfile(".err", "latin_1")


class SafeLaTeXRule(Rule):
    def __init__(self, rulesdir, source, output, wdir,
                 extra=["-lualatex=lualatex --interaction=nonstopmode "
                        "--shell-restricted --nosocket %O %S"],
                 ignore=set(), ignore_ext=set(), do_copy=set()):
        super(SafeLaTeXRule, self).__init__(rulesdir)

        self.source = source
        self.output = output
        self.wdir = wdir
        self.file_cacher = FileCacher()
        self.extra = extra
        self.command = ["/usr/bin/latexmk", "-g", "-pdflua", "-deps",
                        "-deps-out=.deps"] + self.extra + [source]
        self.ignore = copy(ignore)
        self.ignore_ext = copy(ignore_ext)
        self.do_copy = copy(do_copy)

    def mission(self):
        return {'cwd': os.getcwd(),
                'type': 'safe-latex',
                'source': self.source,
                'extra': self.extra}

    def run(self):
        sandbox = LaTeXSandbox(self.file_cacher, name="LaTeX")
        copyrecursivelyifnecessary(self.wdir, sandbox.get_home_path(),
                                   self.ignore, self.ignore_ext, self.do_copy,
                                   mode=0o777)

        sandbox.allow_writing_all()

        relpath = os.path.relpath(os.getcwd(), self.wdir)
        sandbox.chdir = os.path.join(sandbox.chdir, relpath)

        depsfile = os.path.join(sandbox.get_home_path(), relpath, ".deps")

        # Delete the dependencies file before running latex to ensure
        # that we don't read a left-over dependencies file in the end
        # (if latex fails to write the dependencies file).
        deletefile(depsfile)

        success = sandbox.execute_without_std(self.command, wait=True)

        # Don't save the result if the sandbox or LaTeX failed.
        # (We don't reliably detect when a previously missing file was added,
        # for example when a missing package was installed.)
        if not success or sandbox.failed():
            self.result.badfail = True

        self.result.log['code'] = sandbox.failed()
        self.result.log['out'] = sandbox.get_stdout()
        self.result.log['err'] = sandbox.get_stderr()

        self.result.add_dependency(self.source)

        if self.result.log['code']:
            self.result.log['err'] += "\n\n" + ("#" * 40) + "\n" + \
                "SANDBOX: " + sandbox.get_root_path() + "\n" + \
                "MESSAGE: " + sandbox.get_human_exit_description() + "\n" + \
                "LOG FILE:\n" + sandbox.get_log_file_contents()
        else:
            copyifnecessary(os.path.join(sandbox.get_home_path(),
                                         relpath, self.output),
                            os.path.join(self.wdir, relpath, self.output))
            self.result.add_output(self.output)

            # Change to the same working directory that lualatex used (which is
            # inside the sandbox).
            with chdir(os.path.join(sandbox.get_home_path(), relpath)):
                readmakefile(".deps", self.result, True)

            def convert(path):
                if path.startswith(os.path.join(config.latex_distro, "")):
                    return os.path.join(os.path.expanduser("~"), path)
                else:
                    return path

            self.result.dependencies = \
               {convert(path): hash
                for path, hash in self.result.dependencies.items()}

            sandbox.cleanup(not config.keep_sandbox)

    def finish(self):
        self.result.code = self.result.log['code']
        self.result.out = self.result.log['out']
        self.result.err = self.result.log['err']

class JobRule(Rule):
    def __init__(self, rulesdir, job, file_cacher):
        """Executes a job (CompilationJob / EvaluationJob).
        The Job containing the results is saved to result.job.

        rulesdir (string): directory used for persistent data

        job (Job): the job to execute; the job is cloned before execution

        file_cacher (FileCacher): FileCacher for retrieving and storing files
                                  (e.g. sources, executables, outputs)

        The files written to the file cacher are not specified as outputs.
        It is assumed that no files are ever removed from the file cacher.

        """
        super(JobRule, self).__init__(rulesdir)
        self.job = job
        self.file_cacher = file_cacher

    def mission(self):
        return {'type': 'job',
                'job': self.job.export_to_dict()}

    def run(self):
        from cms.grading.Job import Job
        from cms.grading.tasktypes import get_task_type
        task_type = get_task_type(self.job.task_type,
                                  self.job.task_type_parameters)
        # Crazy workaround to clone the job
        jobresult = Job.import_from_dict_with_type(self.job.export_to_dict())
        task_type.execute_job(jobresult, self.file_cacher)
        # Don't save the result if the sandbox failed.
        if not jobresult.success:
            self.result.badfail = True
        self.result.log['job'] = jobresult.export_to_dict()

    def finish(self):
        from cms.grading.Job import Job
        self.result.job = \
            Job.import_from_dict_with_type(self.result.log['job'])


class ZipRule(Rule):
    def __init__(self, rulesdir, zipname, contents):
        """Makes a zip file.

        rulesdir (string): directory used for persistent data

        zipname (string): file name of the zip file to create

        contents (dict): dictionary mapping the names of the file to create
                         in the archive to the corresponding file name on
                         the file system.

        """
        super(ZipRule, self).__init__(rulesdir)
        self.zipname = zipname
        self.contents = contents

    def mission(self):
        return {'cwd': os.getcwd(),
                'type': 'zip', 'zipname': self.zipname,
                'contents': self.contents}

    def run(self):
        import zipfile
        with zipfile.ZipFile(self.zipname, 'w', zipfile.ZIP_DEFLATED) as zf:
            for an, fn in iteritems(self.contents):
                zf.write(fn, arcname=an)
                self.result.add_dependency(fn)
        self.result.add_output(self.zipname)


class PythonFunctionRule(Rule):
    def __init__(self, rulesdir, source, name, function, args, kwargs,
                 stdout, dependencies=[], outputs=[]):
        """A rule running the given function from the given python source file.
        The return value is saved to result.return_value.

        rulesdir (string): directory used for persistent data

        source (string): the file name of the python source file

        name (string): the name to assign to the loaded module

        function (string): name of the python function to call

        args (list): list of arguments to pass to the function

        kwargs (dict): keyword arguments to pass to the function

        stdout (string): if specified, open this file and pass the file
                         descriptor it as an argument called stdout

        dependencies (list): additional dependencies (apart from the python
                             source file)

        outputs (list): additional outputs (apart from stdout)

        """
        super(PythonFunctionRule, self).__init__(rulesdir)
        self.source = source
        self.name = name
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.stdout = stdout
        self.dependencies = dependencies
        self.outputs = outputs

    def mission(self):
        return {'cwd': os.getcwd(),
                'type': 'python_function',
                'source': self.source,
                'name': self.name,
                'function': self.function,
                'args': self.args,
                'kwargs': self.kwargs,
                'stdout': self.stdout,
                'dependencies': self.dependencies,
                'outputs': self.outputs}

    def run(self):
        module = imp.load_source(self.name, self.source)

        kwargs = dict(self.kwargs)

        if self.stdout is not None:
            stdout = io.open(self.stdout, "w", encoding="utf-8")
            kwargs["stdout"] = stdout

        self.result.log['return_value'] = module.gen(*self.args, **kwargs)

        if self.stdout is not None:
            stdout.close()

        for f in self.dependencies:
            self.result.add_dependency(f)
        self.result.add_dependency(self.source)
        for f in self.outputs:
            self.result.add_output(f)
        if self.stdout is not None:
            self.result.add_output(self.stdout)
