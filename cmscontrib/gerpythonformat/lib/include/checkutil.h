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

/* Standard functions for checkers
 */

#ifndef __checkutil_h
#define __checkutil_h

#include <computil.h>
#include <map>
#include <string>
#include <cstdio>
#include <iostream>
#include <sstream>
using namespace std;

map<string, pair<long long, long long> > constraints_ll;

/* Queries for automatic constraints */
template<typename T> pair<T, T> get_constraint(const string &name);

template<> pair<long long, long long> get_constraint(const string &name) {
    if (constraints_ll.find(name) != constraints_ll.end())
        return constraints_ll.find(name)->second;
    else {
        cerr << "auto-check failed: name '" + name + "' not found" << endl;
        exit(42);
    }
}

template<> pair<int, int> get_constraint(const string &name) {
    return (pair<int, int>)(get_constraint<long long> (name));
}

/* Register an automatic constraint */
void put_constraint(const string &name, long long min, long long max) {
    constraints_ll[name] = make_pair(min, max);
}

/* Read constraints from a command line array, interpreting them as integers
 * TODO: use templates and specialization?
 */
void read_some_constraints(char **argv, int count, int start = 0) {
    for (int i = 0; i < count; ++i) {
        string name = argv[start + 3 * i], min = argv[start + 3 * i + 1], max = argv[start + 3 * i + 2];
        put_constraint(name, from_string_or_fail<long long> (min), from_string_or_fail<long long> (max));
    }
}

void read_all_constraints(char **argv, int argc, int start = 0) {
    read_some_constraints(argv, (argc - start) / 3, start);
}

/* Replaces all whitespace escapes by their respective codes
 */
string nws(char c) {
    if (c == '\n')   return "\\n";
    if (c == '\r')   return "\\r";
    if (c == '\t')   return "\\t";

    string s = " ";
    s[0] = c;
    return s;
}

string nice_whitespace(const string &s) {
    string r = "";
    for (int i = 0; i < (int) s.size(); ++i)
        r += nws(s[i]);
    return r;
}

/* Provides the ability to simply scan a file token by token */
class token_stream {
public:
    token_stream() : cursor(0) {}
    token_stream(const string &_s, type_map &t = whitespace_including()) : cursor(0), s(_s), tm(t) {
    }
    token_stream(FILE *fin, type_map &t = whitespace_including()) : cursor(0), tm(t) {
        s = peek_whole(fin);
    }
    string next_or_fail() {
        string token = next_token();
        if (token.empty()) {
            cerr << "Missing token" << endl;
            exit(1);
        }
        return token;
    }
    bool finished() {
        int cursor_before = cursor;
        string token = next_token();
        cursor = cursor_before;
        return token.empty();
    }
    void rewind() {
        cursor = 0;
    }

    /* control next relevant token and next whitespace
     * if "" is provided as expected_whitespace, the next token is not accessed
     * nor is cursor moved one step farther (note that it is impossible for a token
     * to be empty by the definition of tokenize)
     */
    template<typename T> T parse_and_check(const string &expected_whitespace = "") {
        T t = from_string_or_fail<T> (next_or_fail());
        if (expected_whitespace == "")
            return t;
        string read_whitespace = next_or_fail();
        if (read_whitespace != expected_whitespace) {
            cerr << "Incorrect whitespace token. Expected '" << nice_whitespace(expected_whitespace) << "', but got '" << nice_whitespace(read_whitespace) << "'" << endl;
            exit(1);
        }
        return t;
    }

    template<typename T> T parse_and_check(const string &name, T min, T max, const string &expected_whitespace = "") {
        T t = parse_and_check<T> (expected_whitespace);
        if (t < min) {
            cerr << name << " = " << t << " < " << min << endl;
            exit(1);
        }
        if (t > max) {
            cerr << name << " = " << t << " > " << max << endl;
            exit(1);
        }
        return t;
    }

    template<typename T> T parse_and_auto_check(const string &name, const string &expected_whitespace = "") {
        pair<T, T> constraint = get_constraint<T> (name);
        return parse_and_check(name, constraint.first, constraint.second, expected_whitespace);
    }

private:
    int cursor;
    string s;
    type_map tm;

    string next_token() {
        string token;
        int token_type = 0;
        for (; cursor < (int)s.length(); cursor++) {
            char ch = s[cursor];
            int type = 0;
            if (tm.find(ch) != tm.end())
                type = tm.find(ch)->second;
            if (!token.empty() && token_type != type) {
                if (token_type >= 0)
                    return token;
                token.clear();
            }
            token.push_back(ch);
            token_type = type;
        }
        if (!token.empty() && token_type >= 0)
            return token;
        return "";
    }
};

#endif
