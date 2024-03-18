External contest formats
************************

There are two different sets of needs that external contest formats strive to satisfy.

- The first is that of contest admins, that for several reasons (storage of old contests, backup, distribution of data) want to export the contest original data (tasks, contestants, ...) together with all data generated during the contest (from the contestants, submissions, user tests, ... and from the system, evaluations, scores, ...). Once a contest has been exported in this format, CMS must be able to reimport it in such a way that the new instance is indistinguishable from the original.

- The second is that of contest creators, that want an environment that helps them design tasks, testcases, and insert the contest data (contestant names and so on). The format needs to be easy to write, understand and modify, and should provide tools to help developing and testing the tasks (automatic generation of testcases, testing of solutions, ...). CMS must be able to import it as a new contest, but also to import it over an already created contest (after updating some data).

CMS provides an exporter :file:`cmsDumpExporter` and an importer :file:`cmsDumpImporter` working with a format suitable for the first set of needs. This format comprises a dump of all serializable data regarding the contest in a JSON file, together with the files needed by the contest (testcases, statements, submissions, user tests, ...). The exporter and importer understand also compressed versions of this format (i.e., in a zip or tar file). For more information run

.. sourcecode:: bash

    cmsDumpExporter -h
    cmsDumpImporter -h

As for the second set of needs, the philosophy is that CMS should not force upon contest creators a particular environment to write contests and tasks. Therefore, CMS provides general-purpose commands, :file:`cmsAddUser`, :file:`cmsAddTask` and :file:`cmsAddContest`. These programs have no knowledge of any specific on-disk format, so they must be complemented with a set of "loaders", which actually interpret your files and directories. You can tell the importer or the reimported wich loader to use with the ``-L`` flag, or just rely and their autodetection capabilities. Running with ``-h`` flag will list the available loaders.

At the moment, CMS comes with two loaders pre-installed:

* :file:`italy_yaml`, for tasks/users stored in the "Italian Olympiad" format.
* :file:`polygon_xml`, for tasks made with `Polygon <https://polygon.codeforces.com/>`_.

The first one is not particularly suited for general use (see below for more details), so, if you don't want to migrate to one of the aforementioned formats then we encourage you to **write a loader** for your favorite format and then get in touch with CMS authors to have it accepted in CMS. See the file :gh_blob:`cmscontrib/loaders/base_loader.py` for some hints.


Italian import format
=====================

You can follow this description looking at `this example <https://github.com/cms-dev/con_test>`_. A contest is represented in one directory, containing:

- a YAML file named :file:`contest.yaml`, that describes the general contest properties;

- for each task :samp:`{task_name}`, a directory :file:`{task_name}` that contains the description of the task and all the files needed to build the statement of the problem, the input and output cases, the reference solution and (when used) the solution checker.

The exact structure of these files and directories is detailed below. Note that this loader is not particularly reliable and providing confusing input to it may lead to create inconsistent or strange data on the database. For confusing input we mean parameters and/or files from which it can infer no or multiple task types or score types.

As the name suggest, this format was born among the Italian trainers group, thus many of the keywords detailed below used to be in Italian. Now they have been translated to English, but Italian keys are still recognized for backward compatibility and are detailed below. Please note that, although so far this is the only format natively supported by CMS, it is far from ideal: in particular, it has grown in a rather untidy manner in the last few years (CMS authors are planning to develop a new, more general and more organic, format, but unfortunately it doesn't exist yet).

For the reasons above, instead of converting your tasks to the Italian format for importing into CMS, it is suggested to write a loader for the format you already have. Please get in touch with CMS authors to have support.

.. warning::

   The authors offer no guarantee for future compatibility for this format. Again, if you use it, you do so at your own risk!


General contest description
---------------------------

The :file:`contest.yaml` file is a plain YAML file, with at least the following keys.

- ``name`` (string; also accepted: ``nome_breve``): the contest's short name, used for internal reference (and exposed in the URLs); it has to match the name of the directory that serves as contest root.

- ``description`` (string; also accepted: ``nome``): the contest's name (description), shown to contestants in the web interface.

- ``tasks`` (list of strings; also accepted: ``problemi``): a list of the tasks belonging to this contest; for each of these strings, say :samp:`{task_name}`, there must be a directory called :file:`{task_name}` in the contest directory, with content as described :ref:`below <externalcontestformats_task-directory>`; the order in this list will be the order of the tasks in the web interface.

- ``users`` (list of associative arrays; also accepted: ``utenti``): each of the elements of the list describes one user of the contest; the exact structure of the record is described :ref:`below <externalcontestformats_user-description>`.

- ``token_mode``: the token mode for the contest, as in :ref:`configuringacontest_tokens`; it can be ``disabled``, ``infinite`` or ``finite``; if this is not specified, the loader will try to infer it from the remaining token parameters (in order to retain compatibility with the past), but you are not advised to rely on this behavior.

The following are optional keys.

- ``start`` (integer; also accepted: ``inizio``): the UNIX timestamp of the beginning of the contest (copied in the ``start`` field); defaults to zero, meaning that contest times haven't yet been decided.

- ``stop`` (integer; also accepted: ``fine``): the UNIX timestamp of the end of the contest (copied in the ``stop`` field); defaults to zero, meaning that contest times haven't yet been decided.

- ``timezone`` (string): the timezone for the contest (e.g., "Europe/Rome").

- ``per_user_time`` (integer): if set, the contest will be USACO-like (as explained in :ref:`configuringacontest_usaco-like-contests`); if unset, the contest will be traditional (not USACO-like).

- ``token_*``: additional token parameters for the contest, see :ref:`configuringacontest_tokens` (the names of the parameters are the same as the internal names described there).

- ``max_*_number`` and ``min_*_interval`` (integers): limitations for the whole contest, see :ref:`configuringacontest_limitations` (the names of the parameters are the same as the internal names described there); by default they're all unset.


.. _externalcontestformats_user-description:

User description
----------------

Each contest user (contestant) is described in one element of the ``utenti`` key in the :file:`contest.yaml` file. Each record has to contains the following keys.

- ``username`` (string): obviously, the username.

- ``password`` (string): obviously as before, the user's password.

The following are optional keys.

- ``first_name`` (string; also accepted: ``nome``): the user real first name; defaults to the empty string.

- ``last_name`` (string; also accepted: ``cognome``): the user real last name; defaults to the value of ``username``.

- ``ip`` (string): the IP address or subnet from which incoming connections for this user are accepted, see :ref:`configuringacontest_login`.

- ``hidden`` (boolean; also accepted: ``fake``): when set to true set the ``hidden`` flag in the user, see :ref:`configuringacontest_login`; defaults to false (the case-sensitive *string* ``True`` is also accepted).


.. _externalcontestformats_task-directory:

Task directory
--------------

The content of the task directory is used both to retrieve the task data and to infer the type of the task.

These are the required files.

- :file:`task.yaml`: this file contains the name of the task and describes some of its properties; its content is detailed :ref:`below <externalcontestformats_task-description>`; in order to retain backward compatibility, this file can also be provided in the file :file:`{task_name.yaml}` in the root directory of the *contest*.

- :file:`statement/statement.pdf` (also accepted: :file:`testo/testo.pdf`): the main statement of the problem. It is not yet possible to import several statement associated to different languages: this (only) statement will be imported according to the language specified under the key ``primary_language``.

- :file:`input/input{%d}.txt` and :file:`output/output{%d}.txt` for all integers :samp:`{%d}` between 0 (included) and ``n_input`` (excluded): these are of course the input and reference output files.

The following are optional files, that must be present for certain task types or score types.

- :file:`gen/GEN`: in the Italian environment, this file describes the parameters for the input generator: each line not composed entirely by white spaces or comments (comments start with ``#`` and end with the end of the line) represents an input file. Here, it is used, in case it contains specially formatted comments, to signal that the score type is :ref:`scoretypes_groupmin`. If a line contains only a comment of the form :samp:`# ST: {score}` then it marks the beginning of a new group assigning at most :samp:`{score}` points, containing all subsequent testcases until the next special comment. If the file does not exists, or does not contain any special comments, the task is given the :ref:`scoretypes_sum` score type.

- :file:`sol/grader.{%l}` (where :samp:`{%l}` here and after means a supported language extension): for tasks of type :ref:`tasktypes_batch`, it is the piece of code that gets compiled together with the submitted solution, and usually takes care of reading the input and writing the output. If one grader is present, the graders for all supported languages must be provided.

- :file:`sol/*.h` and :file:`sol/*lib.pas`: if a grader is present, all other files in the :file:`sol` directory that end with ``.h`` or ``lib.pas`` are treated as auxiliary files needed by the compilation of the grader with the submitted solution.

- :file:`check/checker` (also accepted: :file:`cor/correttore`): for tasks of types :ref:`tasktypes_batch` or :ref:`tasktypes_outputonly`, if this file is present, it must be the executable that examines the input and both the correct and the contestant's output files and assigns the outcome. It must be a statically linked executable (for example, if compiled from a C or C++ source, the :samp:`-static` option must be used) because otherwise the sandbox will prevent it from accessing its dependencies. It is going to be executed on the workers, so it must be compiled for their architecture. If instead the file is not present, a simple diff is used to compare the correct and the contestant's output files.

- :file:`check/manager`: (also accepted: :file:`cor/manager`) for tasks of type :ref:`tasktypes_communication`, this executable is the program that reads the input and communicates with the user solution.

- :file:`sol/stub.%l`: for tasks of type :ref:`tasktypes_communication`, this is the piece of code that is compiled together with the user submitted code, and is usually used to manage the communication with :file:`manager`. Again, all supported languages must be present.

- :file:`att/*`: each file in this folder is added as an attachment to the task, named as the file's filename.


.. _externalcontestformats_task-description:

Task description
----------------

The task YAML files require the following keys.

- ``name`` (string; also accepted: ``nome_breve``): the name used to reference internally to this task; it is exposed in the URLs.

- ``title`` (string; also accepted: ``nome``): the long name (title) used in the web interface.

- ``n_input`` (integer): number of test cases to be evaluated for this task; the actual test cases are retrieved from the :ref:`task directory <externalcontestformats_task-directory>`.

- ``score_mode``: the score mode for the task, as in :ref:`configuringacontest_score`; it can be ``max_tokened_last``, ``max``, or ``max_subtask``.

- ``token_mode``: the token mode for the task, as in :ref:`configuringacontest_tokens`; it can be ``disabled``, ``infinite`` or ``finite``; if this is not specified, the loader will try to infer it from the remaining token parameters (in order to retain compatibility with the past), but you are not advised to relay on this behavior.

The following are optional keys.

- ``time_limit`` (float; also accepted: ``timeout``): the timeout limit for this task in seconds; defaults to no limitations.

- ``memory_limit`` (integer; also accepted: ``memlimit``): the memory limit for this task in mibibytes; defaults to no limitations.

- ``public_testcases`` (string; also accepted: ``risultati``): a comma-separated list of test cases (identified by their numbers, starting from 0) that are marked as public, hence their results are available to contestants even without using tokens. If the given string is equal to ``all``, then the importer will mark all testcases as public.

- ``token_*``: additional token parameters for the task, see :ref:`configuringacontest_tokens` (the names of the parameters are the same as the internal names described there).

- ``max_*_number`` and ``min_*_interval`` (integers): limitations for the task, see :ref:`configuringacontest_limitations` (the names of the parameters are the same as the internal names described there); by default they're all unset.

- ``output_only`` (boolean): if set to True, the task is created with the :ref:`tasktypes_outputonly` type; defaults to False.

The following are optional keys that must be present for some task type or score type.

- ``total_value`` (float): for tasks using the :ref:`scoretypes_sum` score type, this is the maximum score for the task and defaults to 100.0; for other score types, the maximum score is computed from the :ref:`task directory <externalcontestformats_task-directory>`.

- ``infile`` and ``outfile`` (strings): for :ref:`tasktypes_batch` tasks, these are the file names for the input and output files; default to :file:`input.txt` and :file:`output.txt`; if left empty, :file:`stdin` and :file:`stdout` are used.

- ``primary_language`` (string): the statement will be imported with this language code; defaults to ``it`` (Italian), in order to ensure backward compatibility.


Polygon format
==============

`Polygon <https://polygon.codeforces.com>`_ is a popular platform for the creation of tasks, and a task format, used among others by Codeforces.

Since Polygon doesn't support CMS directly, some task parameters cannot be set using the standard Polygon configuration. The importer reads from an optional file :file:`cms_conf.py` additional configuration specifics to CMS. Additionally, user can add file named contestants.txt to allow importing some set of users.

By default, all tasks are batch files, with custom checker and score type is Sum. Loaders assumes that checker is check.cpp and written with usage of testlib.h. It provides customized version of testlib.h which allows using Polygon checkers with CMS. Checkers will be compiled during importing the contest. This is important in case the architecture where the loading happens is different from the architecture of the workers.

Polygon (by now) doesn't allow custom contest-wide files, so general contest options should be hard-coded in the loader.


.. _GermanFormat:

German import format
=====================

An example contest can be found here: `<https://github.com/ioi-germany/testcontest>`_

You can test a contest locally using the :file:`cmsGerMake` command. It will create a :file:`build` directory inside the given contest directory, copy all files from the contest directory to the build directory and then build the contest (read the configuration files, generate test cases, ...).

Use :file:`cmsGerImport` instead of the generic command :file:`cmsImportContest`, which doesn't support this import format. **Warning:** Don't try to use :file:`cmsImportContest` or one of the abolished commands :file:`cmsImporter` or :file:`cmsReimporter` as that doesn't work.

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

Compiling
---------

You can compile c++ and latex files using the commands :py:meth:`.compilecpp` and :py:meth:`.compilelatex`. Call them with the base name of the file you want to compile (e.g. :samp:`gen` if you want to compile :samp:`gen.cpp` or :samp:`statement` if you want to compile :samp:`statement.tex`). For convenience, you can use the :py:meth:`.compile` function which automatically figures out the corresponding extension.

Supplements
^^^^^^^^^^^

A supplement is a header file that is automatically generated immediately before a compilation (e.g. of a LaTeX statement) is performed. Its job is to provide information that can easily be extracted from the configuration file to the compiler, for example the task name, the time and memory limits and sample test cases.

Executables
-----------

For details, see :file:`cmscontrib/gerpythonformat/Executable.py`

Compiling a c++ file returns an executable object. You can also create an executable object from a python function using :py:meth:`.encapsulate` or from a script file using :py:meth:`.ext_script`.

An executable object can be called like a python function, handing it (normal or keyword) parameters (which are translated to command line arguments executable files). You can also specify stdin, stdout or stderr redirections and additional dependency file names. For example, :samp:`gen(5,6,"afds",stdin="in.txt",stdout="out.txt",dependencies=["dep.txt"])` is roughly equivalent to :samp:`gen 5 6 afds < in.txt > out.txt` and understands that it depends on or outputs :file:`in.txt`, :file:`out.txt` and :file:`dep.txt`.

From an executable, you can construct another executable that

* appends certain command line arguments (e.g., :samp:`gen.p(1,2)(3)` would run :samp:`gen 3 1 2`),
* redirects stdin from a certain file by default (e.g., :samp:`gen.ifi("in.txt")()` would run :samp:`gen < in.txt`) or
* writes a certain string to a file and redirects stdin from it (e.g., :samp:`gen.i(1,2)()` would write :samp:`1\\n2\\n` to a file :file:`.in` and run :samp:`gen < .in`).

This can be particularly helpful for :ref:`creating test cases <gerformat_testcases>`.

.. _gerformat_testcases:

Generating test cases
---------------------

Before generating a test case, you have to specify an output generator using :py:meth:`.output_generator` (which accepts an executable).

You can generate a test case using the :py:meth:`.make_testcase` method which accepts an executable printing the test case input to stdout. The test case input is generated using this executable and then the output generator is provided the input file through stdin and shall print the sample output to stdout.

This method adds the test case to the task, but it does not add it to any subtasks or test case groups. Hence, the test case will be evaluated, but does not automatically count towards the score. See the next section on how to actually add the test case to a test case group.

To hand command line arguments or stdin content to the test case generator, you should create a new executable using the methods explained above. For example, you could use :samp:`make_testcase(gen.i(1,2))` to generate a test case using :samp:`1\\n2\\n` for stdin.

Explicit test cases
^^^^^^^^^^^^^^^^^^^

The utility function :py:meth:`.explicit` returns an executable that just retrieves the input file from the given file (useful for sample test cases).

Subtasks, groups and test cases
-------------------------------

Only the :ref:`scoretypes_subtaskgroup` score type is supported.

The usual way to specify subtasks, groups and test cases is the following::

    output_generator(compile("solution"))  # Compiles solution.cpp and makes it the output generator for this task
    gen = compile("gen")  # Compiles gen.cpp
    chk = compile("checker")  # Compile chk.cpp
    checker(chk.p(0))  # Add the command "checker 0" as a global test case checker
    # Create the public subtask
    with subtask("Public", "public", sample=True):  # Create a subtask with sample test cases
        with group(1):  # Group with 1 point
            testcase(explicit("1.in"), save=True)  # save=True saves the test case to a zip file attachment for the contestants and displays it in the task statement
        with group(1):  # Group with 1 point
            testcase(explicit("2.in"), save=True)  # save=True saves the test case to a zip file attachment for the contestants and displays it in the task statement
    # Create the first subtask
    with subtask("Subtask 1", "small"):  # "small" is the internal name of this subtask
        checker(chk.p(1))  # Add the command "checker 1" as a test case checker for this subtask
        with group(20):  # Group with 20 points
            testcase(gen.i(1, 5), feedback=True)  # feedback=True means that this test case will be used for partial feedback
            testcase(gen.i(2, 7))
        with group(20):  # Group with 20 points
            testcase(gen.i(3, 9))
            testcase(gen.i(4, 11), feedback=True)

The :py:meth:`.TaskConfig.testcase` method generates a test case (using :py:meth:`.make_testcase`) and adds it to the current group (w.r.t. the :samp:`with` statements). If you have already generated a test case using :py:meth:`.make_testcase`, you can use :py:meth:`.TaskConfig.add_testcase` to add it to the current group.

Feedback modes
--------------

The feedback mode (specified in the call to :py:meth:`.ContestConfig.task`) specifies how much information the contestants receive during the contest about their score and the outcomes of the test cases.

The contestants always get full information (including time and memory usage) about the sample subtask. For all other subtask, the amount of information depends on the feedback mode:

No feedback
^^^^^^^^^^^

No further information is shown.

Partial feedback
^^^^^^^^^^^^^^^^

Only the outcomes of the test cases added with :samp:`feedback=True` are shown to the contestants.

Time and memory usage are shown.

Full feedback
^^^^^^^^^^^^^

The contestants get full information about all the outcomes of all test cases.

Time and memory usage are shown.

Restricted feedback
^^^^^^^^^^^^^^^^^^^

In each group, only the first test case with the least score is shown.

Time and memory usage are hidden.

Test case checkers
------------------

To check if your test cases are all valid, you can specify test case checkers using :py:meth:`.checker`. You can add checkers to the task, to a subtask or to a group (the scope is again determined using the :samp:`with` statements). A test case checker is run whenever a test case is added to a group (not when it is created!). It receives the input file through stdin and the output file name is prepended to the list of command line arguments. The checker should return with an exit code different from 0 to indicate that the case is invalid.

In the above example, :samp:`checker OUTPUT 0 < INPUT` would be run for all test cases and :samp:`checker OUTPUT 1 < INPUT` would be run for the test cases belonging to subtask 1.

Checkers must be written in C++ and compiled with `compile(...)`. They mustn't write anything to stdout. On the other hand, stderr output is allowed and will be displayed to the user.

Constraints
^^^^^^^^^^^

You can add simple constraints (e.g., 5 <= N <= 100) to the task, a subtask or a group using :py:meth:`.constraint`. They are automatically provided to both the task statement and test case checkers.

Referencing test cases
----------------------

For test submission result specifications (see below), you need some way to reference test cases. Doing so by code name (a number) can be cumbersome, in particular if you decide to add test cases later. For this reason, you can give subtasks, groups and test cases internal (short) names. If you have a subtask called "small" containing a group called "nastycases", then you can reference the second test case in this group by :samp:`task.small.nastycases.t1` (notice the 0-based indexing!). The fact that we add attributes of the given names to task/subtask/group objects, unfortunately makes this a bit fragile, so you have to choose reasonable names that aren't attributes, yet. This name-based referencing can also be found in the :file:`subtasks` output directory (you can find the test cases both in :file:`subtasks` and :file:`cases`).

Test submissions (a.k.a. unit tests)
------------------------------------

Using :py:meth:`.test_submission`, you can add test submissions which are automatically evaluated by :file:`cmsGerMake` and submitted by :file:`cmsGerImport`.

For each test submission, you have to specify the expected results, which :file:`cmsGerMake` automatically compares to the actual results.

For example, to add a test submission that should

* get 50 private points,
* get 150 public points,
* exceeds its memory limit in the "nastycases" group,
* exceeds its time limit in all other test cases in the "small" or "medium" subtask and
* get 0 (relative) points for all other test cases, although it runs in time and doesn't crash,

you can use the following code::

    test_submission("veryclose.cpp", score=50, public_score=150,
                    expected={"0.0": [task], "time": [task.small, task.medium], "memory": [task.small.nastycases]})`

Test submissions are evaluated with increased (weak) time and memory limits. In the end, the used time (or memory) is compared to the weak and (lower) strong limits. The purpose of this is to ensure some "safety margin" (e.g.: the correct test submissions should take only need the allowed time; the slow test submissions should need at least twice the allowed time). If the time or memory is between the strong and the weak limits, the result (which can be used in the :samp:`expected` dictionary) is :samp:`time?` or :samp:`memory?`. If both the time and the memory limits are exceeded, the result is :samp:`resources`. There is also a keyword `arbitrary` for when you don't care what a test submission does on certain test cases. You can pass the weak and strong limits to :py:meth:`.test_submission` every time or use :py:meth:`.test_submission_limits` to specify them for the whole task (before calling :py:meth:`.test_submission`).

Ranking data directory
----------------------

:file:`cmsGerMake` generates a directory :file:`build/ranking_conf` containing files to copy to :file:`/var/local/lib/cms/ranking`. To make this useful, create a file :file:`logo.png` in the contest directory, for each user a file :file:`face-USERNAME.png` and for each team a file :file:`flag-TEAM.png` and call :samp:`team()` once per team and add a :samp:`team=` parameter when calling :samp:`user()`. For image files, you can also use the formats jpg, gif and bmp instead of png.

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
