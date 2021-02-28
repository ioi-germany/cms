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

/* Function to print the typename of a given variable
 * In case there isn't support for ABI functions, a fallback is provided
 */
#pragma once

#include <typeinfo>
#include <string>
using namespace std;

#ifdef __GNUG__
#include<cxxabi.h>
template<typename T> string get_type(T t) {
    int status;
    return (string)(abi::__cxa_demangle(typeid(t).name(), NULL, NULL, &status));
}
#else
template<typename T> string get_type(T t) {
    return string(typeid(t).name());
}
#endif
