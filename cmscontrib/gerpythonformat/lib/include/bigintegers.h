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

#ifndef __bigintegers_h
#define __bigintegers_h

#include <iostream>
#include <cctype>
#include <stringreading.h>
 
#ifdef __GNUG__

// g++ provides an 128bit-integer type, but no stream reading/writing for it
ostream & operator<<(ostream &out, __int128 y) {
    unsigned __int128 x = static_cast<unsigned __int128>(y);

    if(y < 0) {
        out << "-";
        
        --x; x = ~x;
    }
    
    string s;
    
    do {
        s.push_back((x % 10) + '0');
        x /= 10;
    }
    while(x);
    
    reverse(s.begin(), s.end());
    out << s;

    return out;
}

istream & operator>>(istream &in, __int128 &x) {
    in >> ws;
    x = 0;
    
    bool negative = false;
    
    if(in.peek() == '-') {
        negative = true;
        (void) in.get();
    }
    
    bool read = false;
    
    while(not in.eof() and '0' <= in.peek() and in.peek() <= '9') {
        char c; in >> c;
        x = 10 * x + (negative ? -1 : 1) * (c - '0');
        read = true;
    }
    
    if((not in.eof() and not isspace(in.peek())) or not read)
        in.setstate(ios_base::failbit);
    
    // Checking whether the digit string actually fits into an __int128 happens
    // in from_string by calling string_representation_ok
    
    return in;
}

#endif


class big_int {
 public:
    big_int() : data("0")
    {}
 
    template<typename T> big_int(const T &t) :
        data(from_string_or_fail<big_int>(to_string(t)).data)
    {}
    
    bool operator<(const big_int &rhs) const {
        if(data[0] == '-' and rhs.data[0] != '-') return true;
        if(data[0] != '-' and rhs.data[0] == '-') return false;
        
        if(data[0] == '-' and rhs.data[0] == '-')
            return unsigned_compare_string_representations(rhs.data, data);
        else
            return unsigned_compare_string_representations(data, rhs.data);
    }
    
    bool operator>(const big_int &rhs)  const { return rhs < *this; }
    bool operator<=(const big_int &rhs) const { return not (rhs > *this); }
    bool operator>=(const big_int &rhs) const { return not (rhs < *this); }
    
    string to_string() const { return data; }
    
    /* T should be an integral type for this to be meaningful */
    template<typename T> void try_downcast() const
    {
        (void) from_string_or_fail<T>(data);
    }
    
 private:
    static bool unsigned_compare_string_representations(const string& lhs, const string& rhs) {
        if(lhs.size() < rhs.size()) return true;
        if(lhs.size() > rhs.size()) return false;
        
        return lhs < rhs;
    }
 
    string data;
    
    friend istream & operator>>(istream &, big_int &);
};

ostream & operator<<(ostream &out, const big_int &x) {
    out << x.to_string();
    return out;
}

istream & operator>>(istream &in, big_int &x) {
    string data;
    in >> ws;
    
    if(in.peek() == '-') {
        data = "-";
        (void) in.get();
    }
    
    bool read = false;
    
    while(not in.eof() and '0' <= in.peek() and in.peek() <= '9') {
        char c; in >> c;
        data.push_back(c);
        read = true;
    }
    
    if((not in.eof() and not isspace(in.peek())) or not read)
        in.setstate(ios_base::failbit);
    else
        x.data = data;

    return in;
}

#endif
