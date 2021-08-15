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

/* Standard functions for checkers
 */

#pragma once

#include <computil.h>
#include <optionaladapter.h>
#include <map>
#include <set>
#include <string>
#include <cstdio>
#include <iostream>
#include <sstream>
#include <type_traits>
using namespace std;

/* Check whether the header "constraints.h" has been included BEFORE this file
 * The templating is necessary to exploit C++'s SFINAE
 */
 template<typename... Ts> constexpr bool constraints_loaded() {
     #ifdef CONSTRAINTS_INCLUDED
         return true;
     #else
         return false;
     #endif
 }

 #define CONSTRAINT_ERROR_MSG "You have to include the constraints header before including checkutil.h or checkframework.h if you want to use the constraints system"

/* We save constraints as strings, thereby allowing for numbers that do not fit
 * one of the usual integer types
 */
typedef pair<optional<string>, optional<string>> constraint;
map<string, constraint> _integral_constraints;
map<string, vector<constraint>> _integral_soft_constraints;

/* Queries for automatic constraints */
template<typename T> pair<optional<T>, optional<T>> cast_constraint(constraint c) {
    return make_pair(optional_adapter(from_string_or_fail<T>)(c.first),
                     optional_adapter(from_string_or_fail<T>)(c.second));
}

template<typename T> pair<optional<T>, optional<T>> get_constraint(const string &name) {
    static_assert(constraints_loaded<T>(), CONSTRAINT_ERROR_MSG);

    auto iter = _integral_constraints.find(name);

    if(iter != _integral_constraints.end()) {
        return cast_constraint<T>(iter->second);
    }

    else {
        cerr << "auto-check failed: name '" + name + "' not found" << endl;
        exit(42);
    }
}

template<typename T> T get_constraint_lower(const string &name) {
    return *get_constraint<T>(name).first;
}

template<typename T> T get_constraint_upper(const string &name) {
    return *get_constraint<T>(name).second;
}

template<typename T> pair<T, T> GET_CONSTRAINT(const string &name) {
    return {get_constraint_lower<T>(name), get_constraint_upper<T>(name)};
}

template<typename T> T get_constraint_value(const string &name) {
    pair<T, T> constraint = GET_CONSTRAINT<T>(name);

    if(constraint.first != constraint.second) {
        cerr << "asking for constraint value although lower != upper -- why?" << endl;
        exit(42);
    }

    return constraint.first;
}

/* Register an automatic constraint */
void put_integral_constraint(const string &name, const optional<string> &min, const optional<string> &max) {
    _integral_constraints[name] = make_pair(min, max);
}

/* Register a soft automatic constraint -- we will check whether such a
   constraint is satisfied, but we just output the result in the end and we will
   certainly not die if it is violated...
 */
void put_integral_soft_constraint(const string &name, const optional<string> &min, const optional<string> &max) {
    if(_integral_soft_constraints.find(name) == _integral_soft_constraints.end())
        _integral_soft_constraints[name] = {};
    _integral_soft_constraints[name].emplace_back(min, max);
}

map<string, vector<char>> _integral_soft_constraints_satisfied;

void log_soft_constraints(FILE *flog)
{
    fprintf(flog, "{\n");

    bool first_line = true;

    for(const auto &[var, C] : _integral_soft_constraints) {
        if(not C.empty() and _integral_soft_constraints_satisfied[var].empty()) {
            cerr << "soft constraint \"" << var << "\" (and maybe also others?) "
                 << "hasn't been checked -- dying...";
            exit(1);
        }
    }

    for(const auto &[var, L] : _integral_soft_constraints_satisfied) {
        if(L.empty()) continue;

        if(not first_line) fprintf(flog, ",\n");
        first_line = false;

        fprintf(flog, "\t\"%s\": [", var.c_str());
        bool first_entry = true;

        for(bool b : L) {
            if(not first_entry) fprintf(flog, ", ");
            first_entry = false;
            fprintf(flog, "%s", b ? "true" : "false");
        }

        fprintf(flog, "]");
    }

    fprintf(flog, "\n}\n");
}

/* Facilities for special cases */
set<string> _special_cases;

void add_special_case(string s) {
    _special_cases.insert(s);
}

#define SPECIAL_CASE_TYPE_ERROR_MSG "You may only call is_special_case or ought_to_be with parameters convertible to strings"

template<typename T> bool is_special_case(const T &s) {
    static_assert(constraints_loaded<T>(), CONSTRAINT_ERROR_MSG);
    static_assert(is_convertible<T, string>(), SPECIAL_CASE_TYPE_ERROR_MSG);

    return _special_cases.find(s) != _special_cases.end();
}

template<typename T> bool ought_to_be(const T &t) {
    return is_special_case(t);
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

template<typename T> void check_bounds(const string &name, T t, optional<T> min, optional<T> max) {
        if (min.has_value() and t < *min) {
            cerr << name << " = " << t << " < " << *min << endl;
            exit(1);
        }
        if (max.has_value() and t > *max) {
            cerr << name << " = " << t << " > " << *max << endl;
            exit(1);
        }
}

template<typename T> bool satisfies_bounds(const string &name, T t, optional<T> min, optional<T> max) {
    if(min.has_value() and t < *min) return false;
    if(max.has_value() and t > *max) return false;
    else                             return true;
}

template<typename T> void auto_check_bounds(const string &name, T t) {
    auto constraint = get_constraint<T>(name);
    check_bounds(name, t, constraint.first, constraint.second);

    vector<char> r;
    for(auto c: _integral_soft_constraints[name]) {
        const auto &[min, max] = cast_constraint<T>(c);
        r.push_back(satisfies_bounds<T>(name, t, min, max));
    }

    vector<char> &v = _integral_soft_constraints_satisfied[name];

    if(not v.empty() and r != v) {
        cerr << "Checking soft constraints for \"" << name << "\" after they've "
             << "already been checked before -- and the results are different "
             << "this time! Dying..." << endl;
        exit(1);
    }

    v = r;
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

    template<typename T> T parse_and_check(const string &name, optional<T> min, optional<T> max, const string &expected_whitespace = "") {
        T t = parse_and_check<T> (expected_whitespace);

        check_bounds(name, t, min, max);

        return t;
    }

    template<typename T> T parse_and_auto_check(const string &name, const string &expected_whitespace = "") {
        T t = parse_and_check<T>(expected_whitespace);
        auto_check_bounds<T>(name, t);
        return t;
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
