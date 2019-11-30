/*
 * Programming contest management system
 * Copyright © 2019 Tobias Lenz <t_lenz94@web.de>
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

/* A very simple implementation of an optional; this will become obsolete as 
 * soon as we switch to C++17
 */

#ifndef __MY_OPTIONAL_H
#define __MY_OPTIONAL_H

#include<string>

using namespace std;

// We assume for simplicity that T is default constructible
template<typename T> class my_optional
{
 public:
    my_optional() : _has_value(false) {}
    my_optional(T t) : data(t), _has_value(true) {}
    
    bool has_value() const { return _has_value; }

    T& operator*() {
        if(not has_value()) {
            cerr << "trying to dereference an empty my_optional" << endl;
            throw "trying to dereference an empty my_optioanl";
        }
       
        return data;
    }
    
    const T& operator*() const {
        if(not has_value()) {
            cerr << "trying to dereference an empty my_optional" << endl;
            throw "trying to dereference an empty my_optioanl";
        }

        return data;
    }

 private:
    T data;
    bool _has_value;
};

my_optional<string> none;

template<typename F> class make_optional_wrapper {
 public:
 
    F f;
    make_optional_wrapper(F _f) : f(_f) {}
 
    template<typename P> auto operator()(my_optional<P> param) -> my_optional<decltype(f(*param))> {
        if(not param.has_value())
            return my_optional<decltype(f(*param))>();
        
        else
            return my_optional<decltype(f(*param))>(f(*param));
    }
};

template<typename F> make_optional_wrapper<F> make_optional(F f) {
    return make_optional_wrapper<F>(f);
}

#endif
