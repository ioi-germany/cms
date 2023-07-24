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
#include <string>
#include <computil.h>

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

void __attribute__((noreturn))
result(vector<float> points, vector<string> msgs) {
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
    exit(0);
}

FILE *fin; // The input file
FILE *fout; // The contestant output file
FILE *fok; // The sample output file

/* Compare the string versions of fout and fok by means
 * of the specified comparator (any callable object, that
 * takes two strings, throws strings on invalid formats
 * and returns a boolean
 */
template<typename T> void stdcomp(T comparator) {
    string s, t;
    s = peek_whole(fout);
    t = peek_whole(fok);

    bool correct;
    correct = comparator(s, t);

    if (correct)
        result(1.0, "Correct.");
    else
        result(0.0, "Not correct.");
}

/* Compare the string versions of fout and fok seperately for
 * each line by means of the specified comparator
 */
template<typename T> void linewise_comp(T comparator) {
    vector<string> s, t;
    s = tokenize(peek_whole(fout), linebreak_omitting());   // WARNING: current version ignores empty lines (but not lines consisting of mere whitespace)!
    t = tokenize(peek_whole(fok), linebreak_omitting());

    if (s.size() < t.size()) result(0.0, "Not correct: too few (non-empty) lines");
    if (s.size() > t.size()) result(0.0, "Not correct: too many (non-empty) lines");

    for (int i = 0; i < s.size(); ++i) {
        bool correct;
        correct = comparator(s[i], t[i]);

        if (not correct) result(0.0, "Not correct");
    }

    result(1.0, "Correct.");
}

void check(); // You have to write this function yourself!

int main(int argc, char **argv) {
    std::ios_base::sync_with_stdio();
    assert(argc >= 4);
    fin = fopen(argv[1], "rb");
    fok = fopen(argv[2], "rb");
    fout = fopen(argv[3], "rb");
    check();
    return 1;
}
