/*
 * Programming contest management system
 * Copyright © 2013 Tobias Lenz <t_lenz94@web.de>
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

/* Framework for simple comparators
 * Include this file and write your check function yourself
 */

#include <cstdio>
#include <cassert>
#include <cstdarg>
#include <cstdlib>
#include <iostream>
#include <computil.h>

float STD_FAILURE_SCORE = 0.0; // Score if the comparator fails for unknown reasons

void __attribute__((noreturn)) __attribute__((format(printf, 2, 3)))
result(float points, const char *msg, ...) {
    va_list args;
    va_start(args, msg);
    vfprintf(stderr, msg, args);
    fprintf(stderr, "\n");
    va_end(args);
    fprintf(stdout, "%f", points);
    exit(0);
}

FILE *fin; // The input file
FILE *fcommout; // The file to send messages to the submission through
FILE *fcommin; // The file to receive messages from the submission through
FILE *fout; // Contestant output file (the manager should write some stuff to it)
FILE *fok; // Reference output file

void check(); // You have to write this function yourself!

int main(int argc, char **argv) {
    std::ios_base::sync_with_stdio();
    assert(argc == 3);
    fin = fopen("input.txt", "r");
    fout = fopen("output.txt", "w");
    fcommout = fopen(argv[1], "w");
    fcommin = fopen(argv[2], "r");
    fok = fopen("res.txt", "r");
    check();
    return 1;
}
