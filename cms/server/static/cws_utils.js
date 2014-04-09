/**
 * Utility functions needed by CWS front-end.
 */

var CMS = CMS || {};

CMS.CWSUtils = function(timestamp,
                        current_phase_begin, current_phase_end, phase) {
    this.last_notification = timestamp;
    this.server_timestamp = timestamp;
    this.client_timestamp = $.now() / 1000;
    this.current_phase_begin = current_phase_begin;
    this.current_phase_end = current_phase_end;
    this.phase = phase;
    this.remaining_div = null;
    this.unread_count = 0;
};


CMS.CWSUtils.prototype.update_notifications = function() {
    var self = this;
    $.get(
        url_root + "/notifications",
        {"last_notification": this.last_notification},
        function(data) {
            var counter = 0;
            for (var i = 0; i < data.length; i += 1) {
                self.display_notification(
                    data[i].type,
                    data[i].timestamp,
                    data[i].subject,
                    data[i].text,
                    data[i].level);
                if (data[i].type != "notification") {
                    counter += 1;
                }
            }
            self.update_unread_counts(counter);
        }, "json");
};


CMS.CWSUtils.prototype.display_notification = function(
    type, timestamp, subject, text, level) {
    if (this.last_notification < timestamp) {
        this.last_notification = timestamp;
    }

    // TODO somehow display timestamp, subject and text

    var alert = $('<div class="alert alert-block notification">' +
                  '<a class="close" data-dismiss="alert" href="#">×</a>' +
                  '<h4 class="alert-heading"></h4>' +
                  '</div>');

    if (type == "message") {
        alert.children("h4").text($("#translation_new_message").text());
    } else if (type == "announcement") {
        alert.children("h4").text($("#translation_new_announcement").text());
    } else if (type == "question") {
        alert.children("h4").text($("#translation_new_answer").text());
    } else if (type == "notification") {
        alert.children("h4").text(subject);
        alert.append($("<span>" + text + "</span>"));
    }

    // The "warning" level is the default, so no check needed.
    if (level == "error") {
        alert.addClass("alert-error");
    } else if (level == "success") {
        alert.addClass("alert-success");
    }

    $("#notifications").prepend(alert);
};


CMS.CWSUtils.prototype.update_unread_counts = function(counter) {
    if (counter > 0) {
        this.unread_count += counter;
        $("#unread_count").text(
            $("#translation_unread").text().replace("%d", this.unread_count));
        $("#unread_count").removeClass("no_unread");
    }
};


/**
 * Return a string representation of the number with two digits.
 *
 * n (int): a number with one or two digits.
 * return (string): n as a string with two digits, maybe with a
 *     leading 0.
 */
CMS.CWSUtils.prototype.two_digits = function(n) {
    if (n < 10) {
        return "0" + n;
    } else {
        return "" + n;
    }
};


CMS.CWSUtils.prototype.format_iso_date = function(timestamp) {
    var date = new Date(timestamp * 1000);
    return date.getFullYear() + "-"
        + this.two_digits(date.getMonth() + 1) + "-"
        + this.two_digits(date.getDate());
};


CMS.CWSUtils.prototype.format_time = function(timestamp) {
    var date = new Date(timestamp * 1000);
    return this.two_digits(date.getHours()) + ":"
        + this.two_digits(date.getMinutes()) + ":"
        + this.two_digits(date.getSeconds());
};


CMS.CWSUtils.prototype.format_iso_datetime = function(timestamp) {
    /* The result value differs from Date.toISOString() because if uses
       " " as a date/time separator (instead of "T") and because it stops
       at the seconds (and not at milliseconds). */
    return this.format_iso_date(timestamp) + " " + this.format_time(timestamp);
};


CMS.CWSUtils.prototype.format_timedelta = function(timedelta) {
    // A negative time delta does not make sense, let's show zero to the user.
    if (timedelta < 0) {
        timedelta = 0;
    }

    var hours = Math.floor(timedelta / 3600);
    timedelta %= 3600;
    var minutes = Math.floor(timedelta / 60);
    timedelta %= 60;
    var seconds = Math.floor(timedelta);

    return this.two_digits(hours) + ":"
        + this.two_digits(minutes) + ":"
        + this.two_digits(seconds);
};


CMS.CWSUtils.prototype.update_time = function() {
    var now = $.now() / 1000;

    var server_time = now - this.client_timestamp + this.server_timestamp;
    $("#server_time").text(this.format_time(server_time));

    // TODO consider possible null values of this.current_phase_begin
    // and this.current_phase_end (they mean -inf and +inf
    // respectively)

    switch (this.phase) {
    case -2:
        // Contest hasn't started yet.
        if (server_time >= this.current_phase_end) {
            window.location.href = url_root + "/";
        }
        $("#countdown_label").text(
            $("#translation_until_contest_starts").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case -1:
        // Contest has already started but user hasn't started its
        // time yet.
        $("#countdown_label").text(
            $("#translation_until_contest_ends").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case 0:
        // Contest is currently running.
        if (server_time >= this.current_phase_end) {
            window.location.href = url_root + "/";
        }
        $("#countdown_label").text($("#translation_time_left").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case +1:
        // User has already finished its time but contest hasn't
        // finished yet.
        if (server_time >= this.current_phase_end) {
            window.location.href = url_root + "/";
        }
        $("#countdown_label").text(
            $("#translation_until_contest_ends").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case +2:
        // Contest has already finished.
        $("#countdown_box").addClass("hidden");
        break;
    }
};

