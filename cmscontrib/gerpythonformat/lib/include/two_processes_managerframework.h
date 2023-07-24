/*
 * Programming contest management system
 * Copyright © 2013-2023 Tobias Lenz <t_lenz94@web.de>
 * Copyright © 2013 Fabian Gundlach <320pointsguy@gmail.com>
 * Copyright © 2019 Florian Jüngermann <florianjuengermann@gmai.com>
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

/* Framework for simple managers for two step style communication tasks.
 * Use it when you need two independet instances of the submissions running
 * at the same time.
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

FILE *fcommoutA; // Pipe for sending messages to the submission     - instance A
FILE *fcomminA; // Pipe for receiving messages from the submission  - instance A

FILE *fcommoutB; // Pipe for sending messages to the submissions    - instance B
FILE *fcomminB; // Pipe for receiving messages from the submission  - instance B

FILE *fout; // Output file (the manager can write some stuff to it for debugging purposes)

FILE *fquitter; // Tell the cms to kill the submission
FILE *fquittingresponse; // Waiting for the response

void __attribute__((noreturn)) __attribute__((format(printf, 2, 3)))
result(float points, const char *msg, ...) {
    // Ask cms to kill the submission.
    if(fquitter != 0) {
        fprintf(fquitter, "<3");
        fclose(fquitter);
    }

    // Write the verdict text to stderr.
    va_list args;
    va_start(args, msg);
    vfprintf(stderr, msg, args);
    fprintf(stderr, "\n");
    va_end(args);
    // Write the score to stdout.
    fprintf(stdout, "%f", points);

    // Wait for cms to confirm the solution has terminated (by closing fquittingresponse).
    if (fquittingresponse != 0) {
        char x;
        size_t read = fread(&x, 1, 1, fquittingresponse); (void) read;// mark unsed
    }

    exit(0);
}

void __attribute__((noreturn))
result(vector<float> points, vector<string> msgs) {
    // Ask cms to kill the submission.
    if(fquitter != 0) {
        fprintf(fquitter, "<3");
        fclose(fquitter);
    }

    // Write verdict to stderr
    fprintf(stderr, "%c", (char) 3);
    fprintf(stderr, "{\"outcome\": [");
    for(size_t i = 0; i < points.size(); ++i) {
        if(i) fprintf(stderr, ",");
        fprintf(stderr, "%f", points[i]);
    }
    fprintf(stderr, "], \"text\": [");

    auto escape = [](char c) -> string {
        if(c == '\\')      return "\\\\";
        else if(c == '\n') return "\\n";
        else if(c == '"')  return "\"";
        else if(c == 0)    return "\\u0000";
        else if(c == 3)    return "\\u0003";
        string s = " "; s[0] = c;
        return s;
    };

    for(size_t i = 0; i < msgs.size(); ++i) {
        if(i) fprintf(stderr, ",");
        string s;
        for(char c : msgs[i]) s += escape(c);
        fprintf(stderr, "\"%s\"", s.c_str());
    }
    fprintf(stderr, "]}");
    fprintf(stdout, "-1");

    // Wait for cms to confirm the solution has terminated (by closing fquittingresponse).
    if (fquittingresponse != 0) {
        char x;
        size_t read = fread(&x, 1, 1, fquittingresponse); (void) read;// mark unused
    }

    exit(0);
}

void check(); // You have to write this function yourself!

int main(int argc, char **argv) {
    // If the solution closes its stdin and we then write, SIGPIPE is thrown.
    // We ignore the signal and keep running.
    signal(SIGPIPE, SIG_IGN);

    std::ios_base::sync_with_stdio();
    assert(argc == 5 || argc == 7);
    // arguments:             1: fcomminA, 2: fcommoutA,
    //                        3: fcomminB, 4: fcommoutB,
    // (if stub is NOT used)  5: fquitter, 6: fquittingresponse

    fin = fopen("input.txt", "r");
    fok = fopen("ok.txt", "r");
    if(argc == 7) {
        fquitter = fopen(argv[5], "w");
        fquittingresponse = fopen(argv[6], "r");
    } else {
        fquitter = fquittingresponse = 0;
    }

    // We need to open the pipes in the same order as the solution program (in isolate) to avoid deadlocks.
    fcommoutB = fopen(argv[4], "w");
    fcomminB = fopen(argv[3], "r");
    fcommoutA = fopen(argv[2], "w");
    fcomminA = fopen(argv[1], "r");

    fout = fopen("output.txt", "w");

    check();
    return 1;
}
