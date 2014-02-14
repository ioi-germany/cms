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
template<typename T> void put_constraint(const string &name, T min, T max) {
    cerr << "you have to write a specialization of put_constraing yourself!" << endl;
    exit(42);
}
template<> void put_constraint(const string &name, long long min, long long max) {
    constraints_ll[name] = make_pair(min, max);
}
template<> void put_constraint(const string &name, int min, int max) {
    put_constraint(name, (long long) min, (long long) max);
}

/* Read constraints from a command line array, interpreting them as integers
 * TODO: use templates and specialization?
 */
void read_some_constraints(char **argv, int count, int start = 0) {
    for (int i = 0; i < count; ++i) {
        string name = argv[start + 3 * i], min = argv[start + 3 * i + 1], max = argv[start + 3 * i + 2];
        put_constraint<long long> (name, from_string_or_fail<long long> (min), from_string_or_fail<long long> (max));
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
    token_stream(FILE *fin, type_map &t = whitespace_including()) : cursor(0) {
        data = tokenize(peek_whole(fin), t);
    }
    token_stream(vector<string> _data) : data(_data), cursor(0) {}
    string next_or_fail() {
        if (finished()) {
            cerr << "Missing token" << endl;
            exit(1);
        }
        return data.at(cursor++);
    }
    bool finished() {
        return cursor >= (int)data.size();
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

    void print() {
        for (int i = 0; i < (int) data.size(); ++i)
            cout << "[" << nice_whitespace(data[i]) << "] ";
        cout << endl;
    }

private:
    vector<string> data;
    int cursor;
};

#endif
