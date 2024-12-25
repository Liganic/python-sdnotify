# SPDX-License-Identifier: CC-BY-NC-SA-4.0
#
# Copyright (C) 2024 TriMoon <https://gitlab.com/TriMoon>
#
# Inspired/Adapted from a combination of:
#   - The Python version as published at:
#       https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html
#   - systemd Service Notification:
#       https://github.com/bb4242/sdnotify
#       https://github.com/Liganic/python-sdnotify
#
# Implement the systemd notify protocol without external dependencies.
# Supports both readiness notification on startup and on reloading,
# according to the protocol defined at:
# https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html
# This protocol is guaranteed to be stable as per:
# https://systemd.io/PORTABILITY_AND_STABILITY/

import os
import errno
import socket
import time

# import signal
# import sys

__version__ = "0.4.0-rc"

class SystemdNotifier:
    """This class holds a connection to the systemd notification socket and can be used to send messages to systemd using its notify method."""

    def __init__(self, debug: bool=False) -> None:
        """Instantiate a new notifier object. This will initiate a connection to the systemd notification socket.

        Normally this method silently ignores exceptions (for example, if the systemd notification socket is not available) to allow applications to function on non-systemd based systems.
        However, setting debug=True will cause this method to raise any exceptions generated to the caller, to aid in debugging."""
        self.debug = debug
        self.sock = None
        self.socket_path = os.environ.get("NOTIFY_SOCKET")
        self.version = __version__

        if self.socket_path:
            if self.socket_path[0] not in ("/", "@"):
                raise OSError(errno.EAFNOSUPPORT, "Unsupported socket type")

            # Handle abstract socket.
            if self.socket_path[0] == "@":
                self.socket_path = "\0" + self.socket_path[1:]

            # Open the connection to the socket, only once.
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC)
            if self.sock:
                try:
                    self.sock.connect(self.socket_path)
                except Exception:
                    self.socket = None
                    if self.debug:
                        raise

    def notify(self, message: str) -> None:
        """Send a notification to systemd. state is a string; see the man page of sd_notify (http://www.freedesktop.org/software/systemd/man/sd_notify.html) for a description of the allowable values.

        Normally this method silently ignores exceptions (for example, if the systemd notification socket is not available) to allow applications to function on non-systemd based systems.
        However, setting debug=True will cause this method to raise any exceptions generated to the caller, to aid in debugging."""
        if not message:
            raise ValueError("notify() requires a message")

        if not self.sock:
            return
        else:
            try:
                self.sock.sendall(message)
            except Exception:
                if self.debug:
                    raise

    def ready(self) -> None:
        """https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html#READY=1

        Tells the service manager that service startup is finished, or the service finished re-loading its configuration.
        This is only used by systemd if the service definition file has Type=notify or Type=notify-reload set.
        Since there is little value in signaling non-readiness, the only value services should send is "READY=1" (i.e. "READY=0" is not defined)."""
        self.notify(b"READY=1")

    def reloading(self) -> None:
        """https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html#RELOADING=1

        Tells the service manager that the service is beginning to reload its configuration.
        This is useful to allow the service manager to track the service's internal state, and present it to the user.
        Note that a service that sends this notification must also send a "READY=1" notification when it completed reloading its configuration.
        Reloads the service manager is notified about with this mechanisms are propagated in the same way as they are when originally initiated through the service manager.
        This message is particularly relevant for Type=notify-reload services, to inform the service manager that the request to reload the service has been received and is now being processed.

        Added in version 217."""
        microsecs = time.clock_gettime_ns(time.CLOCK_MONOTONIC) // 1000
        self.notify(f"RELOADING=1\nMONOTONIC_USEC={microsecs}".encode())

    def stopping(self) -> None:
        """https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html#STOPPING=1

        Tells the service manager that the service is beginning its shutdown.
        This is useful to allow the service manager to track the service's internal state, and present it to the user.

        Added in version 217."""
        self.notify(b"STOPPING=1")

    def status(self, message: str) -> None:
        """https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html#STATUS=%E2%80%A6

        Passes a single-line UTF-8 status string back to the service manager that describes the service state.
        This is free-form and can be used for various purposes: general state feedback, fsck-like programs could pass completion percentages and failing programs could pass a human-readable error message.
        Example: "STATUS=Completed 66% of file system check…"

        Added in version 233."""
        self.notify(f"STATUS={message}".encode())

    def errno(self, errno: int) -> None:
        """https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html#ERRNO=%E2%80%A6

        If a service fails, the errno-style error code, formatted as string. Example: "ERRNO=2" for ENOENT.

        Added in version 233."""
        self.notify(f"ERRNO={errno}".encode())

    def exit_status(self, exit_code: int) -> None:
        """https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html#EXIT_STATUS=%E2%80%A6

        The exit status of a service or the manager itself.
        Note that systemd currently does not consume this value when sent by services, so this assignment is only informational.
        The manager will send this notification to its notification socket, which may be used to collect an exit status from the system (a container or VM) as it shuts  down.
        For example, mkosi(1) makes use of this.
        The value to return may be set via the systemctl(1) exit verb.

        Added in version 254."""
        self.notify(f"EXIT_STATUS={exit_code}".encode())

    def mainpid(self, pid: int) -> None:
        """https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html#MAINPID=%E2%80%A6

        The main process ID (PID) of the service, in case the service manager did not fork off the process itself.
        Example: "MAINPID=4711".

        Added in version 233."""
        self.notify(f"MAINPID={pid}".encode())

    def wd_ping(self) -> None:
        """https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html#WATCHDOG=1

        Tells the service manager to update the watchdog timestamp.
        This is the keep-alive ping that services need to issue in regular intervals if WatchdogSec= is enabled for it.
        See systemd.service(5) for information how to enable this functionality and sd_watchdog_enabled(3) for the details of how the service can check whether the watchdog is enabled."""
        self.notify(b"WATCHDOG=1")

    def wd_trigger(self) -> None:
        """https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html#WATCHDOG=trigger

        Tells the service manager that the service detected an internal error that should be handled by the configured watchdog options.
        This will trigger the same behaviour as if WatchdogSec= is enabled and the service did not send "WATCHDOG=1" in time.
        Note that WatchdogSec= does not need to be enabled for "WATCHDOG=trigger" to trigger the watchdog action.
        See systemd.service(5) for information about the watchdog behavior.

        Added in version 243."""
        self.notify(b"WATCHDOG=trigger")

    def wd_usec(self, usec: int) -> None:
        """https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html#WATCHDOG_USEC=%E2%80%A6

        Reset watchdog_usec value during runtime.
        Notice that this is not available when using sd_event_set_watchdog() or sd_watchdog_enabled().
        Example : "WATCHDOG_USEC=20000000"

        Added in version 236."""
        self.notify(f"WATCHDOG_USEC={usec}".encode())

    def extend_timeout(self, usec: int) -> None:
        """https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html#EXTEND_TIMEOUT_USEC=%E2%80%A6

        Tells the service manager to extend the startup, runtime or shutdown service timeout corresponding the current state.
        The value specified is a time in microseconds during which the service must send a new message.
        A service timeout will occur if the message isn't received, but only if the runtime of the current state is beyond the original maximum times of TimeoutStartSec=, RuntimeMaxSec=, and TimeoutStopSec=.
        See systemd.service(5) for effects on the service timeouts.

        Added in version 236."""
        self.notify(f"EXTEND_TIMEOUT_USEC={usec}".encode())

sd_notify = SystemdNotifier()
