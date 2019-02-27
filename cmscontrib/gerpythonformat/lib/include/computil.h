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

#ifndef __computil_h
#define __computil_h

#include <bigintegers.h>
#include <filereading.h>
#include <tokenizing.h>
#include <stringreading.h>

/* "Top level" comparators */
inline bool strictly_equal(const string &s, const string &t) {
    return s == t;
}

class token_equal {
public:
    token_equal() {
        my_map = whitespace_omitting();
    }
    token_equal(const type_map &map) {
        my_map = map;
    }

    bool operator()(const string &s, const string &t) {
        return tokenize(s, my_map) == tokenize(t, my_map);
    }

private:
    type_map my_map;
};

#endif
