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

/* Standard functions for checkers
 */

#ifndef __checkutil_h
#define __checkutil_h

#include <computil.h>
#include <map>
#include <set>
#include <string>
#include <cstdio>
#include <iostream>
#include <sstream>
using namespace std;

/* We save constraints as strings, thereby allowing for numbers that do not fit
 * one of the usual integer types
 */
map<string, pair<string, string>> _integral_constraints;

/* Queries for automatic constraints */
template<typename T> pair<T, T> get_constraint(const string &name) {
    auto iter = _integral_constraints.find(name);

    if(iter != _integral_constraints.end()) {
        pair<string, string> result = iter->second;

        return make_pair(from_string_or_fail<T>(result.first),
                         from_string_or_fail<T>(result.second));
    }
    
    else {
        cerr << "auto-check failed: name '" + name + "' not found" << endl;
        exit(42);
    }
}

/* Register an automatic constraint */
void put_integral_constraint(const string &name, const string &min, const string &max) {
    _integral_constraints[name] = make_pair(min, max);
}

/* Facilities for special cases */
set<string> _special_cases;

void add_special_case(string s) {
    _special_cases.insert(s);
}

bool is_special_case(string s) {
    return _special_cases.find(s) != _special_cases.end();
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
        return parse_and_check<T>(name, constraint.first, constraint.second, expected_whitespace);
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
