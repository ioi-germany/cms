/*
 * Programming contest management system
 * Copyright © 2022 Lukas Michel <lukas-michel@gmx.de>
 * Copyright © 2013-2022 Tobias Lenz <t_lenz94@web.de>
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

/* Framework for manager controlled communication tasks in which the manager decides
 * whether the user submission should be run again
 * TODO: extend this to work with num_processes > 1
 */

#include <cstdio>
#include <cassert>
#include <cstdarg>
#include <cstdlib>
#include <iostream>
#include <signal.h>
#include <computil.h>
#include <cstdio>
#include <string>

bool message_on_shutdown = false;

FILE *fin; // The input file
FILE *fok; // Reference output file

constexpr int MAX_NUM_INSTANCES = 42;
int num_instances;
FILE* fcommout[MAX_NUM_INSTANCES]; // Pipes for sending messages to the submission
FILE* fcommin[MAX_NUM_INSTANCES];  // Pipes for receiving messages from the submission

FILE *fcmsout; // Tell the cms to kill/restart the submission
FILE *fcmsin;  // Pipe for the response

FILE *fout; // Output file (for debugging purposes)

// add #define DEBUG_ to your manager for detailed logs of all communication

template<typename... Ts> void _write_helper(FILE* f, string s, int line, Ts... params) {
  fprintf(f, params...);
  fflush(f);

    #ifdef DEBUG_
      fprintf(stderr, "[line %d, >>%s] ", line, s.c_str());
      fprintf(stderr, params...);
    #endif
}

#define _write(f, ...) _write_helper(f, #f, __LINE__, __VA_ARGS__)

void __attribute__((noreturn)) __attribute__((format(printf, 2, 3)))
result_helper(float points, const char *msg, ...) {
    // Tell CMS we are done
    _write(fcmsout, "Q");

    // the submission might also be interested in this
    if(message_on_shutdown)
      for(int i = 0; i < num_instances; ++i)
        _write(fcommout[i], "-1\n-1\n"), fclose(fcommout[i]);

    // Write the verdict text to stderr.
    va_list args;
    va_start(args, msg);
    vfprintf(stderr, msg, args);
    fprintf(stderr, "\n");
    va_end(args);
    // Write the score to stdout.
    fprintf(stdout, "%f", points);

    #ifdef DEBUG_
      fprintf(stderr, "waiting for answer from cms");
    #endif

    // Wait for cms to confirm the solution has terminated to avoid breaking pipes
    char c = fgetc(fcmsin);

    #ifdef DEBUG_
      fprintf(stderr, "received answer [%c]", c);
    #else
      (void) c;
    #endif

    exit(0);
}

template<typename... Ts> void __attribute__((noreturn)) result_wrapper(int line, string parameters, Ts... params)
{
  #ifdef DEBUG_
    fprintf(stderr, "calling result in line %d with parameters (%s)\n", line, parameters.c_str());
  #endif
  result_helper(params...);
}

#define result(...) result_wrapper(__LINE__, #__VA_ARGS__, __VA_ARGS__)

void check(); // You have to write this function yourself!

string argv1[MAX_NUM_INSTANCES], argv2[MAX_NUM_INSTANCES];

string string_from_cms() {
  char *buffer = NULL;
  size_t _ = 0;
  getline(&buffer, &_, fcmsin);
  string r(buffer); free(buffer);
  r.pop_back();
  return r;
}

void tell_cms(int n, int T) {
  assert(0 < n and n <= MAX_NUM_INSTANCES);
  num_instances = n;

  char r = fgetc(fcmsin); assert(r == 'S'); // welcome message from CMS
  _write(fcmsout, "%dB%dB", num_instances, T);

  for(int i = 0; i < num_instances; ++i) {
    argv1[i] = string_from_cms();
    argv2[i] = string_from_cms();
    // fprintf(stderr, "[%s|%s]", argv1[i].c_str(), argv2[i].c_str());
  }
}

void open_pipes() {
  for(int i = 0; i < num_instances; ++i) {
    fcommout[i] = fopen(argv2[i].c_str(), "w");
    fcommin[i] = fopen(argv1[i].c_str(), "r");
  }
}

void restart_submission() {
  for(int i = 0; i < num_instances; ++i)
    fclose(fcommout[i]);     // closing the pipes will become relevant in a second
  _write(fcmsout, "C");      // tell CMS we do not want to quit just yet
  char r = fgetc(fcmsin);    // after this the previous user programs have terminated
  for(int i = 0; i < num_instances; ++i)
    fclose(fcommin[i]);      // ... but their successors cannot yet have opened their
                             // pipe for writing as isolate first opens pipes for
                             // reading which blocks as we closed fcommout---in
                             // effect we closed all pipes now in a safe manner
  if(r == 'X') exit(0);      // terminate if the user program did not run successfully
  open_pipes();              // after this we can be sure to be on the same page again
}

int main(int argc, char **argv) {
    // If the solution closes its stdin and we then write, SIGPIPE is thrown.
    // We ignore the signal and keep running.
    signal(SIGPIPE, SIG_IGN);

    std::ios_base::sync_with_stdio();

    fin = fopen("input.txt", "r");
    fok = fopen("ok.txt", "r");

    fcmsout = fopen(argv[1], "w");
    fcmsin = fopen(argv[2], "r");

    fout = fopen("output.txt", "w");

    check();
    result(0.0, "error in manager");
    return 0;
}
