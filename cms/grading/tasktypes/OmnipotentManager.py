#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2016 Masaki Hara <ackie.h.gmai@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2022 Tobias Lenz <t_lenz94@web.de>
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
import os
import signal
import time
import tempfile
from functools import reduce

from cms import config, rmtree
from cms.db import Executable
from cms.grading.ParameterTypes import ParameterTypeChoice, ParameterTypeInt
from cms.grading.Sandbox import wait_without_std, Sandbox
from cms.grading.languagemanager import LANGUAGES, get_language
from cms.grading.steps import compilation_step, evaluation_step_before_run, \
    evaluation_step_after_run, extract_outcome_and_text, \
    human_evaluation_message, merge_execution_stats, trusted_step
from cms.grading.tasktypes import check_files_number
from cms.grading.tasktypes import TaskType, check_executables_number, \
    check_manager_present, create_sandbox, delete_sandbox
from cms.grading.tasktypes.Communication import Communication

logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message

# TODO: should we somehow treat the merging differently for num_processes > 1?
def my_merge_execution_stats(first_stats, second_stats):
    """Merge two execution statistics dictionary.

    The first input stats can be None, in which case the second stats is copied
    to the output (useful to treat the first merge of a sequence in the same
    way as the others).

    first_stats (dict|None): statistics about the first execution; contains
        execution_time, execution_wall_clock_time, execution_memory,
        exit_status, and possibly signal.
    second_stats (dict): same for the second execution.

    return (dict): the merged statistics, using the following algorithm:
        * execution times, memory usages, and wall clock times are max'd;
        * exit_status and related values (signal) are from the first non-OK,
            if present, or OK;
        * stdout and stderr, if present, are joined with a separator line.

    raise (ValueError): if second_stats is None.

    """
    if second_stats is None:
        raise ValueError("The second input stats cannot be None.")
    if first_stats is None:
        return second_stats.copy()

    ret = first_stats.copy()
    for s in ["execution_time", "execution_wall_clock_time", "execution_memory"]:
        ret[s] = max(ret[s], second_stats[s])

    if (first_stats["exit_status"] == Sandbox.EXIT_TIMEOUT_WALL and
        second_stats["exit_status"] != Sandbox.EXIT_OK) \
        or first_stats["exit_status"] == Sandbox.EXIT_OK:
        ret["exit_status"] = second_stats["exit_status"]
        if second_stats["exit_status"] == Sandbox.EXIT_SIGNAL:
            ret["signal"] = second_stats["signal"]

    for f in ["stdout", "stderr"]:
        if f in ret or f in second_stats:
            ret[f] = "\n===\n".join(d[f]
                                    for d in [ret, second_stats]
                                    if f in d)

    return ret


class OmnipotentManager(Communication):
    def __init__(self, parameters):
        super().__init__(parameters)

    def evaluate(self, job, file_cacher):
        if not check_executables_number(job, 1):
            return
        executable_filename = next(iter(job.executables.keys()))
        executable_digest = job.executables[executable_filename].digest

        # Make sure the required manager is among the job managers.
        if not check_manager_present(job, self.MANAGER_FILENAME):
            return
        manager_digest = job.managers[self.MANAGER_FILENAME].digest

        # Create FIFO dirs and first batch of FIFos
        fifo_dir_base = tempfile.mkdtemp(dir=config.temp_dir)

        def fifo_dir(i, j):
            p = os.path.join(fifo_dir_base, f"fifo{i}_{j}")
            if not os.path.exists(p):
                os.mkdir(p)
            return p

        abortion_control_fifo_dir = tempfile.mkdtemp(dir=config.temp_dir)
        fifo_solution_quitter = os.path.join(abortion_control_fifo_dir, "sq")
        fifo_manager_quitter = os.path.join(abortion_control_fifo_dir, "mq")
        os.mkfifo(fifo_solution_quitter)
        os.mkfifo(fifo_manager_quitter)
        os.chmod(abortion_control_fifo_dir, 0o755)
        os.chmod(fifo_solution_quitter, 0o666)
        os.chmod(fifo_manager_quitter, 0o666)

        sandbox_abortion_control_fifo_dir = "/abort"
        sandbox_fifo_solution_quitter = \
            os.path.join(sandbox_abortion_control_fifo_dir, "sq")
        sandbox_fifo_manager_quitter = \
            os.path.join(sandbox_abortion_control_fifo_dir, "mq")

        # Start the manager. Redirecting to stdin is unnecessary, but for
        # historical reasons the manager can choose to read from there
        # instead than from INPUT_FILENAME.
        manager_command = ["./%s" % self.MANAGER_FILENAME]
        manager_command += [sandbox_fifo_solution_quitter,
                            sandbox_fifo_manager_quitter]

        # Create the manager sandbox and copy manager and input and
        # reference output.
        sandbox_mgr = create_sandbox(file_cacher, name="manager_evaluate")
        job.sandboxes.append(sandbox_mgr.get_root_path())
        sandbox_mgr.create_file_from_storage(
            self.MANAGER_FILENAME, manager_digest, executable=True)
        sandbox_mgr.create_file_from_storage(
            self.INPUT_FILENAME, job.input)
        sandbox_mgr.create_file_from_storage(
            self.OK_FILENAME, job.output)

        # We could use trusted_step for the manager, since it's fully
        # admin-controlled. But trusted_step is only synchronous at the moment.
        # Thus we use evaluation_step, and we set a time limit generous enough
        # to prevent user programs from sending the manager in timeout.
        # This means that:
        # - the manager wall clock timeout must be greater than the sum of all
        #     wall clock timeouts of the user programs;
        # - with the assumption that the work the manager performs is not
        #     greater than the work performed by the user programs, the manager
        #     user timeout must be greater than the maximum allowed total time
        #     of the user programs; in theory, this is the task's time limit,
        #     but in practice is num_processes times that because the
        #     constraint on the total time can only be enforced after all user
        #     programs terminated.
        sandbox_fifo_dir_base = "/fifo"

        def sandbox_fifo_dir(i, j):
            return f"{sandbox_fifo_dir_base}/fifo{i}_{j}"

        manager_time_limit = max(self.num_processes * (job.time_limit + 1.0),
                                 config.trusted_sandbox_max_time_s)
        manager_dirs_map = {abortion_control_fifo_dir:
                                (sandbox_abortion_control_fifo_dir, "rw")}

        # TODO: can we avoid creating all these directories?
        MAX_NUM_INSTANCES = 42

        list_of_fifo_dirs = []

        for pr in range(0, self.num_processes):
            for i in range(0, MAX_NUM_INSTANCES):
                d = fifo_dir(i, pr)
                list_of_fifo_dirs.append(d)
                manager_dirs_map[d] = (sandbox_fifo_dir(i, pr), "rw")

        manager = evaluation_step_before_run(
            sandbox_mgr,
            manager_command,
            manager_time_limit,
            config.trusted_sandbox_max_memory_kib * 1024,
            dirs_map=manager_dirs_map,
            writable_files=[self.OUTPUT_FILENAME],
            stdin_redirect=self.INPUT_FILENAME,
            multiprocess=True)

        solution_quitter = open(fifo_solution_quitter, "r")
        manager_quitter = open(fifo_manager_quitter, "w")

        def finish_run():
            wait_without_std(processes)
            L = [finish_run_single(i) for i in indices]
            return all(L)

        def finish_run_single(i):
            nonlocal wall_clock_acc
            nonlocal num_runs

            user_results.append(evaluation_step_after_run(sandbox_user[i]))
            wall_clock_acc += user_results[-1][2]["execution_wall_clock_time"]
            num_runs += 1
            runtimes[i].append(user_results[-1][2]["execution_time"])

            # Convert tuple to list for write access to entries
            L = list(user_results[-1])
            L[2]["execution_time"] = runtimes[i][-1] / max_num_runs

            if(L[2]["execution_time"] >= job.time_limit):
                L[2]["exit_status"] = Sandbox.EXIT_TIMEOUT

            user_results[-1] = tuple(L)

            if not self._uses_stub():
                # It can happen that the submission runs out of memory and then
                # gets killed by the manager while it is being shut down, in
                # which case isolate does not report a signal as the exit
                # status. To catch this, we look for cg-oom-killed in the logs
                sandbox_user[i].get_log()
                if user_results[-1][1] and \
                   "cg-oom-killed" in sandbox_user[i].log:
                    # Convert tuple to list for write access to entries
                    r = list(user_results[-1])
                    r[1] = False
                    r[2]["status"] = ["SG"]
                    r[2]["exit_status"] = "signal"
                    r[2]["signal"] = -41 # sit by a lake
                    r[2]["message"] = ["out of memory"]
                    user_results[-1] = tuple(r)

            return user_results[-1][0] and user_results[-1][1]

        def respond(okay=True):
            manager_quitter.write("O" if okay else "X")
            manager_quitter.flush()

        def read_int_from_manager():
            L = []
            while True:
                c = solution_quitter.read(1)
                if c == 'B':
                    break
                else:
                    L.append(c)
            return int("".join(L))

        quit = False

        for pr in range(0, self.num_processes):
            if quit:
                break

            wall_clock_acc = 0
            num_runs = 0

            # Startup message to sync pipes
            manager_quitter.write('S')
            manager_quitter.flush()

            # Ask the manager for the number of processes
            num_instances = read_int_from_manager()
            indices = range(0, num_instances)
            max_num_runs = read_int_from_manager()

            # Create remaining FIFOs
            fifo_user_to_manager = [
                os.path.join(fifo_dir(i, pr), f"u{pr}_{i}_to_m")
                for i in indices]
            fifo_manager_to_user = [
                os.path.join(fifo_dir(i, pr), f"m_to_u{pr}_{i}")
                for i in indices]
            for i in indices:
                os.mkfifo(fifo_user_to_manager[i])
                os.mkfifo(fifo_manager_to_user[i])
                os.chmod(fifo_dir(i, pr), 0o755)
                os.chmod(fifo_user_to_manager[i], 0o666)
                os.chmod(fifo_manager_to_user[i], 0o666)

            # Names of the fifos after being mapped inside the sandboxes.
            sandbox_fifo_user_to_manager = \
                [os.path.join(sandbox_fifo_dir(i, pr),
                              f"u{pr}_{i}_to_m") for i in indices]
            sandbox_fifo_manager_to_user = \
                [os.path.join(sandbox_fifo_dir(i, pr),
                              f"m_to_u{pr}_{i}") for i in indices]

            for i in indices:
                print(sandbox_fifo_user_to_manager[i], file=manager_quitter,
                      flush=True)
                print(sandbox_fifo_manager_to_user[i], file=manager_quitter,
                      flush=True)

            # Create the user sandbox(es) and copy the executable.
            sandbox_user = [create_sandbox(file_cacher, name="user_evaluate")
                            for i in indices]
            job.sandboxes.extend(s.get_root_path() for s in sandbox_user)

            for i in indices:
                sandbox_user[i].create_file_from_storage(
                    executable_filename, executable_digest, executable=True)

                # Prepare the user submissions
                language = get_language(job.language)
                main = self.STUB_BASENAME if self._uses_stub() \
                    else os.path.splitext(executable_filename)[0]
                processes = [None for i in indices]
                user_results = []

                args = []
                stdin_redirect = None
                stdout_redirect = None
                if self._uses_fifos():
                    args.extend([sandbox_fifo_manager_to_user[i],
                                sandbox_fifo_user_to_manager[i]])
                if self.num_processes != 1:
                    args.append(str(i))
                if self._uses_stub():
                    main = self.STUB_BASENAME
                else:
                    main = executable_filename
                commands = language.get_evaluation_commands(
                    executable_filename,
                    main=main,
                    args=args)

                # Assumes that the actual execution of the user solution is the
                # last command in commands, and that the previous are "setup"
                # that don't need tight control.
                if len(commands) > 1:
                    trusted_step(sandbox_user[i], commands[:-1])

            processes = [None for _ in indices]
            runtimes = [[] for _ in indices]

            while True:
                for i in indices:
                    processes[i] = evaluation_step_before_run(
                        sandbox_user[i],
                        commands[-1],
                        job.time_limit * max_num_runs * num_instances,
                        job.memory_limit,
                        dirs_map={fifo_dir(i, pr): (sandbox_fifo_dir(i, pr),
                                                    "rw")},
                        stdin_redirect=sandbox_fifo_manager_to_user[i],
                        stdout_redirect=sandbox_fifo_user_to_manager[i],
                        multiprocess=job.multithreaded_sandbox)

                response = solution_quitter.read(1)

                if response == "C": # continue
                    if not finish_run():
                        # this run was not successful, time to call it quits
                        quit = True
                        respond(okay=False)
                        break
                    respond()
                elif response == "N": # next process
                    if not finish_run():
                        # this run was not successful, time to call it quits
                        quit = True
                        respond(okay=False)
                        break
                    respond()
                    break
                elif response == "Q":
                    if not self._uses_stub():
                        time.sleep(.01)
                        processes[i].send_signal(signal.SIGINT)
                    finish_run()
                    respond()
                    quit = True
                    break
                else:
                    raise RuntimeError("Received '{}' ".format(response) +
                                       "through solution_quitter.")

        # Wait for the manager to conclude, without blocking them on I/O.
        wait_without_std([manager])

        solution_quitter.close()
        manager_quitter.close()

        # Get the results of the manager sandbox.
        box_success_mgr, evaluation_success_mgr, unused_stats_mgr = \
            evaluation_step_after_run(sandbox_mgr)

        # Coalesce the results of the user sandboxes.
        box_success_user = all(r[0] for r in user_results)
        evaluation_success_user = all(r[1] for r in user_results)
        stats_user = reduce(my_merge_execution_stats,
                            [r[2] for r in user_results])
        # The actual running time is the sum of every user process, but each
        # sandbox can only check its own; if the sum is greater than the time
        # limit we adjust the result.
        if box_success_user and evaluation_success_user and \
                stats_user["execution_time"] >= job.time_limit:
            evaluation_success_user = False
            stats_user['exit_status'] = Sandbox.EXIT_TIMEOUT

        success = box_success_user \
            and box_success_mgr and evaluation_success_mgr
        outcome = None
        text = None

        # If at least one sandbox had problems, or the manager did not
        # terminate correctly, we report an error (and no need for user stats).
        if not success:
            stats_user = None

        # If just asked to execute, fill text and set dummy outcome.
        elif job.only_execution:
            outcome = 0.0
            text = [N_("Execution completed successfully")]

        # If the user sandbox detected some problem (timeout, ...),
        # the outcome is 0.0 and the text describes that problem.
        elif not evaluation_success_user:
            outcome = 0.0
            text = human_evaluation_message(stats_user)

        # Otherwise, we use the manager to obtain the outcome.
        else:
            outcome, text = extract_outcome_and_text(sandbox_mgr)

        # If asked so, save the output file with additional information,
        # provided that it exists.
        if job.get_output:
            if sandbox_mgr.file_exists(self.OUTPUT_FILENAME):
                job.user_output = sandbox_mgr.get_file_to_storage(
                    self.OUTPUT_FILENAME,
                    "Output file in job %s" % job.info,
                    trunc_len=100 * 1024)
            else:
                job.user_output = None

        # Fill in the job with the results.
        job.success = success
        job.outcome = "%s" % outcome if outcome is not None else None
        job.text = text
        job.plus = stats_user

        delete_sandbox(sandbox_mgr, job.success, job.keep_sandbox)
        for s in sandbox_user:
            delete_sandbox(s, job.success, job.keep_sandbox)
        if job.success and not config.keep_sandbox and not job.keep_sandbox:
            rmtree(fifo_dir_base)
            rmtree(abortion_control_fifo_dir)