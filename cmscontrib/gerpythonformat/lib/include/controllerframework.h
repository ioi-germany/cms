/*
 * Programming contest management system
 * Copyright © 2026 Julian Dörfler <qwasyx3000@gmail.com>
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

/* Framework for simple controllers for interactive tasks
 * Include this file and write your controller function yourself
 */

#include <cassert>
#include <computil.h>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <optional>
#include <signal.h>

#ifndef PROTOCOL_VIOLATION
#define PROTOCOL_VIOLATION "Protocol violation"
#endif

__attribute__((noreturn)) __attribute__((format(printf, 3, 4))) void result(double score, const char *msg, const char *admin_msg, ...) {
    va_list args;
    va_start(args, admin_msg);

    fprintf(stderr, "SCORE: %f\n", score);
    fprintf(stderr, "USER_MESSAGE: %s\n", msg);
    fprintf(stderr, "ADMIN_MESSAGE: ");
    vfprintf(stderr, admin_msg, args);
    fprintf(stderr, "\n");

    va_end(args);
    exit(0);
}

__attribute__((noreturn)) void result(double score, const char *msg) {
    fprintf(stderr, "SCORE: %f\n", score);
    fprintf(stderr, "USER_MESSAGE: %s\n", msg);
    exit(0);
}

class SubmissionProcess {
  public:
    FILE *fsend = nullptr; // Pipe for sending messages to the submission
    FILE *frecv = nullptr; // Pipe for receiving messages from the submission

    SubmissionProcess &start() {
        assert(fsend == nullptr && frecv == nullptr);

        printf("START_SOLUTION\n");
        fflush(stdout);
        int fdsend, fdrecv;
        scanf("%d%d", &fdsend, &fdrecv);
        fsend = fdopen(fdsend, "w");
        frecv = fdopen(fdrecv, "r");
        assert(fsend);
        assert(frecv);
        return *this;
    }

    ~SubmissionProcess() {
        if (fsend)
            fclose(fsend);
        if (frecv)
            fclose(frecv);
    }

    // send a message to the submission, printf-style, already includes flushing.
    // You should include a newline or space at the end of the message
    __attribute__((format(printf, 2, 3))) void send(const char *msg, ...) {
        va_list args;
        va_start(args, msg);
        vfprintf(fsend, msg, args);
        va_end(args);

        fflush(fsend);
    }

    // send a message to the submission using a callback for more control
    void send(function<void(FILE *)> sendfn) {
        sendfn(fsend);
        fflush(fsend);
    }

    // receive a message from the submission, scanf-style
    __attribute__((format(scanf, 2, 3))) int recv(const char *msg, ...) {
        va_list args;
        va_start(args, msg);
        int ret = vfscanf(frecv, msg, args);
        va_end(args);

        return ret;
    }

    // receive a message from the submission using a callback for more control
    void recv(function<void(FILE *)> recvfn) { recvfn(frecv); }

    // receive a message from the submission, scanf-style.
    // Ends with a protocol violation if the secret is not received
    __attribute__((format(scanf, 3, 4))) int recv_with_secret(int requiredSecret, const char *msg, ...) {
        int secret;
        if (fscanf(frecv, "%d", &secret) != 1) {
            result(0, PROTOCOL_VIOLATION, "Failed to read secret");
        }
        if (secret != requiredSecret) {
            result(0, PROTOCOL_VIOLATION, "Submission sent wrong secret");
        }

        va_list args;
        va_start(args, msg);
        int ret = vfscanf(frecv, msg, args);
        va_end(args);

        return ret;
    }

    // receive a message from the submission using a callback for more control.
    // Ends with a protocol violation if the secret is not received
    void recv_with_secret(int requiredSecret, function<void(FILE *)> recvfn) {
        int secret;
        if (fscanf(frecv, "%d", &secret) != 1) {
            result(0, PROTOCOL_VIOLATION, "Failed to read secret");
        }
        if (secret != requiredSecret) {
            result(0, PROTOCOL_VIOLATION, "Submission sent wrong secret");
        }
        recvfn(frecv);
    }
};

FILE *fin; // The input file
FILE *fok; // Reference output file

void controller(); // You have to write this function yourself!

int main(int argc, char **argv) {
    // If the solution closes its stdin and we then write, SIGPIPE is thrown.
    // We ignore the signal and keep running.
    signal(SIGPIPE, SIG_IGN);
    std::ios_base::sync_with_stdio();

    fin = fopen("input.txt", "r");
    fok = fopen("ok.txt", "r");

    controller();

    return 1;
}
