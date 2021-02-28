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

#pragma once

#include <vector>
#include <string>
#include <cstdio>
#include <map>
#include <iostream>

using namespace std;
typedef map<char, int> type_map;

const string STD_WHITESPACE = " \t\n\r";
const string STD_LINEBREAK = "\n\r";

type_map STD_WHITESPACE_OMITTING;
type_map &whitespace_omitting() {
    if (STD_WHITESPACE_OMITTING.empty())
        for (int i = 0; i < (int)STD_WHITESPACE.size(); ++i)
            STD_WHITESPACE_OMITTING[STD_WHITESPACE[i]] = -1;
    return STD_WHITESPACE_OMITTING;
}

type_map STD_WHITESPACE_INCLUDING;
type_map &whitespace_including() {
    if (STD_WHITESPACE_INCLUDING.empty())
        for (int i = 0; i < (int)STD_WHITESPACE.size(); ++i)
            STD_WHITESPACE_INCLUDING[STD_WHITESPACE[i]] = 1;
    return STD_WHITESPACE_INCLUDING;
}

type_map STD_LINEBREAK_OMITTING;
type_map &linebreak_omitting() {
    if (STD_LINEBREAK_OMITTING.empty())
        for (int i = 0; i < (int)STD_WHITESPACE.size(); ++i)
            STD_LINEBREAK_OMITTING[STD_WHITESPACE[i]] = -1;
    return STD_LINEBREAK_OMITTING;
}

/*
 * Let v be the vector of non-empty strings satisfying the following properties:
 *
 * 1) The concatenation of the strings is s.
 * 2) For each string t in v, all characters in t have the same type. We call this the type of t.
 * 3) Consecutive strings in v are of different types.
 *
 * This function returns a vector consisting of the strings in v except the ones consisting only of
 * characters of negative type.
 *
 * The type of a character is retrieved from the type map. It is assumed to be 0 for characters not
 * in the map.
 */
vector<string> tokenize(const string &s, const type_map &tm) {
    vector<string> r;
    string token;
    int token_type = 0;
    for (int i = 0; i < (int)s.length(); i++) {
        char ch = s[i];
        int type = 0;
        if (tm.find(ch) != tm.end())
            type = tm.find(ch)->second;
        if (!token.empty() && token_type != type) {
            if (token_type >= 0)
                r.push_back(token);
            token.clear();
        }
        token.push_back(ch);
        token_type = type;
    }
    if (!token.empty() && token_type >= 0)
        r.push_back(token);
    return r;
}
