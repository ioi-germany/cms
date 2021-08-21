/*
 * Programming contest management system
 * Copyright © 2013-2021 Tobias Lenz <t_lenz94@web.de>
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

/* Basic framework for checkers
 * just include this file and provide a check-function
 */
#pragma once

#include <checkutil.h>
#include <iostream>
#include <cstdarg>
#include <cassert>

using namespace std;

void __attribute__((noreturn)) __attribute__((format(printf, 1, 2)))
die(const char *msg, ...) {
    va_list args;
    va_start(args, msg);
    vfprintf(stderr, msg, args);
    fprintf(stderr, "\n");
    va_end(args);
    exit(1);
}

FILE *fin;
FILE *fout;
token_stream t;

void check(int argc, char **argv); // you have to write this function yourself!

int main(int argc, char **argv) {
    std::ios_base::sync_with_stdio();

    constexpr int num_std_params = 2;
    assert(argc >= num_std_params);
    fin = stdin;
    fout = fopen(argv[1], "rb");
    //FILE *flog = fopen(argv[2], "w");

#ifdef CONSTRAINTS_INCLUDED
    load_constraints();
    cerr << "Constraints loaded." << endl;

    if(not _special_cases.empty())
    {
        cerr << "This case should satisfy the following additional condition(s):";
        for(string s : _special_cases) cerr << " " << s;
        cerr << endl;
    }
#endif

    t = token_stream(fin);
    check(argc - num_std_params, argv + num_std_params);

#ifdef CONSTRAINTS_INCLUDED
    log_soft(stdout);
#endif

    return 0; // everything OK
}
