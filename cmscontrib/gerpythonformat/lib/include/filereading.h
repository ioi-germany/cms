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

/* Various useful method for file reading
 *
 */
#pragma once

#include <string>
#include <cstdio>
#include <memory.h>
#include <vector>
#include <tokenizing.h>
#include <typenaming.h>

const int SAFETY_OFFSET = 10;

using namespace std;

/* Get number of chars in given file (which must be readable)
 * After successful execution the cursor will be at its original position
 */
size_t get_file_size(FILE *f) {
    // Save position to restore it later
    fpos_t old_pos;
    fgetpos(f, &old_pos);
    rewind(f);

    fseek(f, 0, SEEK_END);
    size_t length = ftell(f);

    fsetpos(f, &old_pos);

    return length;
}

/* Get *remaining* number of chars in given file (which must be readable)
 * After successful execution the cursor will be at its original position
 */
size_t get_remaining_file_size(FILE *f) {
    return get_file_size(f) - ftell(f);
}

/* General method for getting a string from a readable file */
string generic_read(FILE *f, bool rewind_me, bool restore_cursor) {
    fpos_t old_pos;
    fgetpos(f, &old_pos);

    if (rewind_me) rewind(f);

    size_t eof = get_remaining_file_size(f);
    size_t buffer_size = eof + SAFETY_OFFSET;
    char *buffer = new char[buffer_size + SAFETY_OFFSET];
    size_t read = fread(buffer, 1, buffer_size, f); (void) read; // mark unused
    buffer[eof] = '\0';

    if (restore_cursor) fsetpos(f, &old_pos);

    string s(buffer);
    delete[] buffer;
    return s;
}

/* "Top level" versions of generic_read */
inline string peek_rest(FILE *f) {
    return generic_read(f, false, true);
}
inline string peek_whole(FILE *f) {
    return generic_read(f, true, true);
}
inline string read_rest(FILE *f) {
    return generic_read(f, false, false);
}
inline string read_whole(FILE *f) {
    return generic_read(f, true, false);
}

/* Standard exception thrown when read fails */
#define READ_FAIL_THROW throw "couldn't read input token of type " + get_type(t)

/* Read a specific element from the given file (which should be
 * readable) or throw an exception if it isn't there
 */
template<typename T> T base_read_or_fail(FILE *f, const char *const spec) {
    T t;
    if (fscanf(f, spec, &t) != 1)    READ_FAIL_THROW;
    return t;
}

/* Converters for basic data types */
template<typename T> T read_or_fail(FILE *f) {
    throw "No converter specified";    // this function should not be called
}
template<> int read_or_fail(FILE *f) {
    return base_read_or_fail<int>(f, "%d");
}
template<> long long read_or_fail(FILE *f) {
    return base_read_or_fail<long long>(f, "%lld");
}
template<> double read_or_fail(FILE *f) {
    return base_read_or_fail<double>(f, "%lf");
}

bool rest_empty(FILE *f) {
    return tokenize(peek_rest(f), whitespace_omitting()).empty();
}
