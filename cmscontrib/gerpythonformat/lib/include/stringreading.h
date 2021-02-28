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

/* Various useful method for converting string tokens to other objects
 *
 */
#pragma once

#include <cmath>
#include <string>
#include <sstream>
#include <iostream>
#include <cctype>
#include <algorithm>
#include <typenaming.h>
using namespace std;

// Helper function to print almost anything to a string
template<typename T> string to_string(const T &t) {
    ostringstream out;
    out << t;
    return out.str();
}

// Prints t to a string and compares it to s
template<typename T> bool string_representation_ok(const string &s, const T &t) {
    return to_string(t) == s;
}

// For double, we are less strict as there are many ways to represent a double.
// FIXME This is not completely secure: For example, " 1" would be accepted!
template<> bool string_representation_ok(const string &s, const double &t) {
    int b = fpclassify(t);
    return b == FP_ZERO || b == FP_NORMAL;
}

// Try to read a value of type T from the given string.
// Check if the string is correctly formatted.
// If not, print an error message and exit(1).
// Else, return the value.
template<typename T> bool from_string(const string &s, T &t) {
    istringstream in(s);
    in >> t;
    return !in.fail() && in.eof() && string_representation_ok(s, t);
}

template<> bool from_string(const string &s, char &t) {
    if (s.size() != 1)
        return false;
    t = s[0];
    return true;
}

template<typename T> T from_string_or_fail(const string &s) {
    T t;
    if (!from_string(s, t)) {
        cerr << "Can't convert token '" << s << "' to type " << get_type(t) << endl;
        exit(1);
    }
    return t;
}
