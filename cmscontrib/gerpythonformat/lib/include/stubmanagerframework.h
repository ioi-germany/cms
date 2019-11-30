/*
 * Programming contest management system
 * Copyright © 2013-2019 Tobias Lenz <t_lenz94@web.de>
 * Copyright © 2013 Fabian Gundlach <320pointsguy@gmail.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

/* Framework for simple managers for communication tasks for which the user
 * only submits a stub
 * Include this file and write your check function yourself
 */

#include <cstdio>
#include <cassert>
#include <cstdarg>
#include <cstdlib>
#include <iostream>
#include <signal.h>
#include <computil.h>

FILE *fin; // The input file
FILE *fok; // Reference output file

FILE *fcommout; // Pipe for sending messages to the submission
FILE *fcommin; // Pipe for receiving messages from the submission

FILE *fout; // Output file (the manager can write some stuff to it for debugging purposes)

bool message_on_shutdown = false; // Whether we should send the message -1 to the user program
                                  // when result is called

void __attribute__((noreturn)) __attribute__((format(printf, 2, 3)))
result(float points, const char *msg, ...) {
    // Write the verdict text to stderr.
    va_list args;
    va_start(args, msg);
    vfprintf(stderr, msg, args);
    fprintf(stderr, "\n");
    va_end(args);
    // Write the score to stdout.
    fprintf(stdout, "%f", points);
    
    // Tell the user program it should quit
    if(message_on_shutdown)
    {
        fprintf(fcommout, "-1\n");
        fflush(fcommout);
    }

    exit(0);
}

void check(); // You have to write this function yourself!

int main(int argc, char **argv) {
    // If the solution closes its stdin and we then write, SIGPIPE is thrown.
    // We ignore the signal and keep running.
    signal(SIGPIPE, SIG_IGN);

    std::ios_base::sync_with_stdio();
    
    fin = fopen("input.txt", "r");
    fok = fopen("ok.txt", "r");

    // We need to open the pipes in the same order as the solution program (in isolate) to avoid deadlocks.
    fcommout = fopen(argv[2], "w");
    fcommin = fopen(argv[1], "r");

    fout = fopen("output.txt", "w");

    check();
    return 0;
}
