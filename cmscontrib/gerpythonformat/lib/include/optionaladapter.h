/*
 * Programming contest management system
 * Copyright © 2019-2021 Tobias Lenz <t_lenz94@web.de>
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

#include<string>

using namespace std;

optional<string> none;

template<typename F> class optional_adapter_wrapper {
 public:

    F f;
    optional_adapter_wrapper(F _f) : f(_f) {}

    template<typename P> auto operator()(optional<P> param) -> optional<decltype(f(*param))> {
        if(not param.has_value())
            return optional<decltype(f(*param))>();

        else
            return optional<decltype(f(*param))>(f(*param));
    }
};

template<typename F> optional_adapter_wrapper<F> optional_adapter(F f) {
    return optional_adapter_wrapper<F>(f);
}
