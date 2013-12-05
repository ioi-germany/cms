External contest formats
************************

There are two different sets of needs that external contest formats strive to satisfy.

- The first is that of contest admins, that for several reasons (storage of old contests, backup, distribution of data) want to export the contest original data (tasks, contestants, ...) together with all data generated during the contest (from the contestants, submissions, user tests, ... and from the system, evaluations, scores, ...). Once a contest has been exported in this format, CMS must be able to reimport it in such a way that the new instance is indistinguishable from the original.

- The second is that of contest creators, that want an environment that helps them design tasks, testcases, and insert the contest data (contestant names and so on). The format needs to be easy to write, understand and modify, and should provide tools to help developing and testing the tasks (automatic generation of testcases, testing of solutions, ...). CMS must be able to import it as a new contest, but also to import it over an already created contest (after updating some data).

CMS provides an exporter :file:`cmsContestExporter` and an importer :file:`cmsContestImporter` working with a format suitable for the first set of needs. This format comprises a dump of all serializable data regarding the contest in a JSON file, together with the files needed by the contest (testcases, statements, submissions, user tests, ...). The exporter and importer understand also compressed versions of this format (i.e., in a zip or tar file). For more information run

.. sourcecode:: bash

    cmsContestExporter -h
    cmsContestImporter -h

As for the second set of needs, the philosophy is that CMS should not force upon contest creators a particular environment to write contests and tasks. Therefore, CMS provides two general-purpose commands, :file:`cmsImporter` (for importing a totally new contest) and :file:`cmsReimporter` (for merging an already existing contest with the one being imported). These two programs have no knowledge of any specific on-disk format, so they must are complemented with a set of "loaders", which actually interpret your files and directories. You can tell the importer or the reimported wich loader to use with the ``-L`` flag, or just rely and their autodetection capabilities. Running with ``-h`` flag will list the available loaders.

At the moment, the only loader distributed with CMS understand the format used within Italian Olympiad. It is not particularly suited for general use (see below for some details more), so we encourage you to write a loader for your favorite format and then get in touch with CMS authors to have it accepted in CMS. See files :gh_blob:`cmscontrib/BaseLoader.py` and :gh_blob:`cmscontrib/YamlLoader.py` for some hints.


Italian import format
=====================

You can follow this description looking at `this example <https://github.com/cms-dev/con_test>`_. A contest is represented in one directory, containing:

- a YAML file named :file:`contest.yaml`, that describes the general contest properties;

- for each task :samp:`{task_name}`, a YAML file :file:`{task_name}.yaml` that describes the task and a directory :file:`{task_name}` that contains all the files needed to build the statement of the problem, the input and output cases, the reference solution and (when used) the solution checker.

The exact structure of these files and directories is detailed below. Note that providing confusing input to ``cmsYamlImporter`` can, unexpectedly, confuse it and create inconsistent tasks and/or strange errors. For confusing input we mean parameters and/or files from which it can infer no or multiple task types or score types.

As the name suggest, this format was born among the Italian trainers group, thus many of the keywords detailed below used to be in Italian. Now they have been translated to English, but Italian keys are still recognized for backward compatibility and are detailed below. Please note that, although so far this is the only format natively supported by CMS, it is far from ideal: in particular, it has grown in a rather untidy manner in the last few years (CMS authors are planning to develop a new, more general and more organic, format, but unfortunately it doesn't exist yet). Thus, instead of converting your tasks to the Italian format for importing into CMS, it is suggested to write a loader for the format you already have. Please get in touch with CMS authors to have support.


General contest description
---------------------------

The :file:`contest.yaml` file is a plain YAML file, with at least the following keys.

- ``name`` (string; also accepted: ``nome_breve``): the contest's short name, used for internal reference (and exposed in the URLs); it has to match the name of the directory that serves as contest root.

- ``description`` (string; also accepted: ``nome``): the contest's name (description), shown to contestants in the web interface.

- ``tasks`` (list of strings; also accepted: ``problemi``): a list of the tasks belonging to this contest; for each of these strings, say :samp:`{task_name}`, there must be a file named :file:`{task_name}.yaml` in the contest directory and a directory called :file:`{task_name}`, used to extract information about that task; the order in this list will be the order of the tasks in the web interface.

- ``users`` (list of associative arrays; also accepted: ``utenti``): each of the elements of the list describes one user of the contest; the exact structure of the record is described :ref:`below <externalcontestformats_user-description>`.

The following are optional keys.

- ``start`` (integer; also accepted: ``inizio``): the UNIX timestamp of the beginning of the contest (copied in the ``start`` field); defaults to zero, meaning that contest times haven't yet been decided.

- ``stop`` (integer; also accepted: ``fine``): the UNIX timestamp of the end of the contest (copied in the ``stop`` field); defaults to zero, meaning that contest times haven't yet been decided.

- ``token_*``: token parameters for the contest, see :ref:`configuringacontest_tokens` (the names of the parameters are the same as the internal names described there); by default tokens are disabled.

- ``max_*_number`` and ``min_*_interval`` (integers): limitations for the whole contest, see :ref:`configuringacontest_limitations` (the names of the parameters are the same as the internal names described there); by default they're all unset.


.. _externalcontestformats_user-description:

User description
----------------

Each contest user (contestant) is described in one element of the ``utenti`` key in the :file:`contest.yaml` file. Each record has to contains the following keys.

- ``username`` (string): obviously, the username.

- ``password`` (string): obviusly as before, the user's password.

The following are optional keys.

- ``first_name`` (string; also accepted: ``nome``): the user real first name; defaults to the empty string.

- ``last_name`` (string; also accepted: ``cognome``): the user real last name; defaults to the value of ``username``.

- ``ip`` (string): the IP address from which incoming connections for this user are accepted, see :ref:`configuringacontest_login`.

- ``hidden`` (string; also accepted: ``fake``): when set to ``True`` (case-sensitive _string_) set the ``hidden`` flag in the user, see :ref:`configuringacontest_login`; defaults to ``False``.


Task description
----------------

The task YAML files requires the following keys.

- ``name`` (string; also accepted: ``nome_breve``): the name used to reference internally to this task; it is exposed in the URLs.

- ``title`` (string; also accepted: ``nome``): the long name (title) used in the web interface.

- ``n_input`` (integer): number of test cases to be evaluated for this task; the actual test cases are retrieved from the :ref:`task directory <externalcontestformats_task-directory>`.

The following are optional keys.

- ``time_limit`` (float; also accepted: ``timeout``): the timeout limit for this task in seconds; defaults to no limitations.

- ``memory_limit`` (integer; also accepted: ``memlimit``): the memory limit for this task in megabytes; defaults to no limitations.

- ``public_testcases`` (string; also accepted: ``risultati``): a comma-separated list of test cases (identified by their numbers, starting from 0) that are marked as public, hence their results are available to contestants even without using tokens.

- ``token_*``: token parameters for the task, see :ref:`configuringacontest_tokens` (the names of the parameters are the same as the internal names described there); by default tokens are disabled.

- ``max_*_number`` and ``min_*_interval`` (integers): limitations for the task, see :ref:`configuringacontest_limitations` (the names of the parameters are the same as the internal names described there); by default they're all unset.

- ``outputonly`` (boolean): if set to True, the task is created with the :ref:`tasktypes_outputonly` type; defaults to False.

The following are optional keys that must be present for some task type or score type.

- ``total_value`` (float): for tasks using the :ref:`scoretypes_sum` score type, this is the maximum score for the task and defaults to 100.0; for other score types, the maximum score is computed from the :ref:`task directory <externalcontestformats_task-directory>`.

- ``infile`` and ``outfile`` (strings): for :ref:`tasktypes_batch` tasks, these are the file names for the input and output files; default to :file:`input.txt` and :file:`output.txt`.

- ``primary_language`` (string): the statement will be imported with this language code; defaults to ``it`` (Italian), in order to ensure backward compatibility.


.. _externalcontestformats_task-directory:

Task directory
--------------

The content of the task directory is used both to retrieve the task data and to infer the type of the task.

These are the required files.

- :file:`statement/statement.pdf` (also accepted: :file:`testo/testo.pdf`): the main statement of the problem. It is not yet possible to import several statement associated to different languages: this (only) statement will be imported according to the language specified under the key ``primary_language``.

- :file:`input/input{%d}.txt` and :file:`output/output{%d}.txt` for all integers :samp:`{%d}` between 0 (included) and ``n_input`` (excluded): these are of course the input and (one of) the correct output files.

The following are optional files, that must be present for certain task types or score types.

- :file:`gen/GEN`: in the Italian environment, this file describes the parameters for the input generator: each line not composed entirely by white spaces or comments (comments start with ``#`` and end with the end of the line) represents an input file. Here, it is used, in case it contains specially formatted comments, to signal that the score type is :ref:`scoretypes_groupmin`. If a line contains only a comment of the form :samp:`# ST: {score}` then it marks the beginning of a new group assigning at most :samp:`{score}` points, containing all subsequent testcases until the next special comment. If the file does not exists, or does not contain any special comments, the task is given the :ref:`scoretypes_sum` score type.

- :file:`sol/grader.{%l}` (where :samp:`{%l}` here and after means a supported language extension): for tasks of type :ref:`tasktypes_batch`, it is the piece of code that gets compiled together with the submitted solution, and usually takes care of reading the input and writing the output. If one grader is present, the graders for all supported languages must be provided.

- :file:`sol/*.h` and :file:`sol/*lib.pas`: if a grader is present, all other files in the :file:`sol` directory that end with ``.h`` or ``lib.pas`` are treated as auxiliary files needed by the compilation of the grader with the submitted solution.

- :file:`check/checker` (also accepted: :file:`cor/correttore`): for tasks of types :ref:`tasktypes_batch` or :ref:`tasktypes_outputonly`, if this file is present, it must be the executable that examines the input and both the correct and the contestant's output files and assigns the outcome. It must be a statically linked executable (for example, if compiled from a C or C++ source, the :samp:`-static` option must be used) because otherwise the sandbox will prevent it from accessing its dependencies. If instead the file is not present, a simple diff is used to compare the correct and the contestant's output files.

- :file:`check/manager`: (also accepted: :file:`cor/manager`) for tasks of type :ref:`tasktypes_communication`, this executable is the program that reads the input and communicates with the user solution.

- :file:`sol/stub.%l`: for tasks of type :ref:`tasktypes_communication`, this is the piece of code that is compiled together with the user submitted code, and is usually used to manage the communication with :file:`manager`. Again, all supported languages must be present.

- :file:`att/*`: each file in this folder is added as an attachment to the task, named as the file's filename.


German import format
=====================

An example contest can be found here: `<https://github.com/ioi-germany/testcontest>`_

You can test a contest locally using the :file:`cmsGerMake` command. It will create a :file:`build` directory inside the given contest directory, copy all files from the contest directory to the build directory and then build the contest (read the configuration files, generate test cases, ...).

Similarly, use :file:`cmsImporter` or :file:`cmsReimporter` as usual. **Warning:** :file:`cmsReimporter` currently ignores test submissions.

Contests and tasks are specified using python scripts :file:`contest-config.py` and :file:`taskname/config.py`.

Each time a contest or task is built, the respective python configuration files are executed. The configuration files contain static information like a list of all users, task names and time limits but are also responsible for e.g. compiling test case generators, generating test cases, validating test cases and compiling task statements.

The python scripts are provided with some variables and functions (both global and local): The methods of a :ref:`ContestConfig` or :ref:`TaskConfig` (and their superclass :ref:`CommonConfig`) object that are marked as :samp:`@exported_function` as well as other contents of the :samp:`exported` dictionary.

Lazy rebuilding
---------------

We use a mechanism to ensure that most operations are only performed if necessary, for example:

* Compiling
* Executing a command
* Making a zip file
* Testing a test submission

E.g., a command usually has to be executed only if the executable, the command line arguments, any input file or any output file has changed.

Although this is relatively stable, it may happen that a necessary operation is not executed (for example, if you forgot to install a LaTeX package before the previous run and now you installed it). In such cases, you can remove the :file:`build` directory (or change one of the output or input files).

Below, we describe the internals of this mechanism (for details, see :file:`cms/rules/Rule.py`):

A :samp:`Rule` object is created whenever an operation is requested. We call the details of such a request the rule's *mission*. A rule's mission could for example be "compile source.cpp to binary using g++" or "run binary using input.txt for stdin and output.txt for stdout; beware, the binary could also read extradata.txt!".

Subsequently (in :samp:`Rule.ensure()`), we check if the last result (:samp:`RuleResult`) of this mission can be found on the disk (we look for a file whose name is essentially the hash sum of the mission). If no, then we run the rule (compile, execute the binary, ...). If yes, then we retrieve the set of dependency/output file names along with their expected hash sums (the ones after the last time the rule was run) from the result file. If one of the saved hash sums is different from the current one, we run the rule, otherwise we don't. In the end (if nothing terrible happened), we find out the dependencies/outputs (e.g., g++ usually returns them with the -MMD flag) and save these results (so that they can be retrieved using the mission the next time this rule is supposed to be run). The results can comprise other information than dependency/output file names, e.g. compiler output, some representation of the result of the evaluation of a test submission, etc.

Supplements
-----------

A supplement is a header file that is automatically generated immediately before a compilation (e.g. of a LaTeX statement) is performed. Its job is to provide information that can easily be extracted from the configuration file to the compiler, for example the task name, the time and memory limits and sample test cases.

Constraints
-----------

You can specify simple constraints (e.g., 5 <= N <= 100) in the configuration file which are then automatically provided to both the task statement and test case checkers.

Test submissions (a.k.a. unit tests)
------------------------------------

You can add test submissions which are automatically evaluated by :file:`cmsGerMake` and submitted by :file:`cmsImporter` (**Warning:** :file:`cmsReimporter` currently ignores test submissions).

For each test submission, you have to specify the expected results, which :file:`cmsGerMake` automatically compares to the actual results. You could say "this submission should get 50 points for private and 150 points for public test cases; it should succeed for all test cases except the last one, where it should exceed the time limit".

Test submissions will **in a future version** be evaluated with increased (weak) time and memory limits. In the end, the used time (or memory) is compared to the weak and (lower) strong limits. The purpose of this is to ensure some "safety margin" (e.g.: the correct test submissions should take only need the allowed time; the slow test submissions should need at least twice the allowed time).

Referencing test cases
----------------------

For test submission result specifications, you need some way to reference test cases. Doing so by code name (a number) can be cumbersome, in particular if you decide add test cases later. For this reason, you can give subtasks, groups and test cases internal (short) names. If you have a subtask called "small" containing a group called "nastycases", then you can reference the second test case in this group by :samp:`task.small.nastycases.t1` (notice the 0-based indexing!). The fact that we add attributes of the given names to task/subtask/group objects, unfortunately makes this a bit fragile, so you have to choose reasonable names that aren't attributes, yet. This name-based referencing can also be found in the :file:`subtasks` output directory (you can find the test cases both in :file:`subtasks` and :file:`cases`).

Detailed (partial) feedback
---------------------------

We can give partial feedback by creating a (public) detailed feedback subtask containing a subset of the official test cases. These detailed feedback subtasks can be automatically created using :py:meth:`cmscontrib.gerpythonformat.TaskConfig.generate_feedback` after you have marked the wanted test cases by handing :samp:`feedback=True` to :py:meth:`cmscontrib.gerpythonformat.TaskConfig.MyGroup.add_testcase` (or :py:meth:`cmscontrib.gerpythonformat.TaskConfig.MyGroup.testcase`).

Compiling
---------

You can compile c++, latex and asymptote files using the commands :samp:`compilecpp`, :samp:`compilelatex`, :samp:`compileasy`. Call them with the base name of the file you want to compile (e.g. :samp:`gen` if you want to compile :samp:`gen.cpp` or :samp:`statement` if you want to compile :samp:`statement.tex`). For convenience, you can use the :samp:`compile` function which automatically figures out the corresponding extension.

Executables
-----------

Compiling a c++ file returns an executable object.



Test cases and scoring
----------------------

Only the :ref:`scoretypes_subtaskgroup` score type is supported.

The usual way to specify subtasks, groups and test cases is the following::

    output_generator(compile("solution"))  # Compiles :file:`solution.cpp` and
    gen = compile("gen")  # Compiles :file:`gen.cpp`
    # Create the public subtask
    with subtask("Public", "public", public=True):
        with group(100):  # Group with 100 points
            testcase(explicit.p("1.in"))
    # Create the first subtask
    with subtask("Subtask 1", "small"):
        with group(20):  # Group with 20 points
            testcase(gen.p(1, 5), feedback=True)
            testcase(gen.p(2, 7))
        with group(20):  # Group with 20 points
            testcase(gen.p(3, 9))
            testcase(gen.p(4, 11))
    generate_feedback()


Calling :samp:`testcase(gen.p(1, 5))` generates a test case and adds it to

.. _CommonConfig:

CommonConfig
------------

.. autoclass:: cmscontrib.gerpythonformat.CommonConfig.CommonConfig

.. _ContestConfig:

ContestConfig
-------------

.. autoclass:: cmscontrib.gerpythonformat.ContestConfig.ContestConfig
    :show-inheritance:

.. _TaskConfig:

TaskConfig
----------

.. autoclass:: cmscontrib.gerpythonformat.TaskConfig.TaskConfig
    :show-inheritance:

Scope
^^^^^

.. autoclass:: cmscontrib.gerpythonformat.TaskConfig.Scope
    :show-inheritance:

MySubtask
^^^^^^^^^

.. autoclass:: cmscontrib.gerpythonformat.TaskConfig.MySubtask
    :show-inheritance:

MyGroup
^^^^^^^

.. autoclass:: cmscontrib.gerpythonformat.TaskConfig.MyGroup
    :show-inheritance:

MyCase
^^^^^^

.. autoclass:: cmscontrib.gerpythonformat.TaskConfig.MyCase
    :show-inheritance:
