# -*- coding: utf-8 -*-
#
#    Authors:
#        Pavel Březina <pbrezina@redhat.com>
#
#    Copyright (C) 2019 Red Hat
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import signal
import re

from functools import wraps


class TimeoutError(Exception):
    def __init__(self, timeout, message):
        super().__init__(message)
        self.timeout = timeout


# Based on timeout-decorator
# https://github.com/pnpnpn/timeout-decorator/blob/master/timeout_decorator/timeout_decorator.py
class timeout(object):
    def __init__(self, timeout=None, message=None):
        self.timeout = timeout
        self.message = message
        self.seconds = self._timeout_to_seconds(timeout)

    def _timeout_to_seconds(self, timeout):
        if timeout is None:
            return None

        matches = re.findall(
          r'(([\d\.]+)\W*(hours?|minutes?|seconds?)?)',
          str(timeout)
        )

        if not matches:
            raise ValueError('Unknown timeout value: {}'.format(timeout))

        seconds = 0
        for m in matches:
            (_, time, unit) = m
            if unit.startswith('h'):
                seconds += int(float(time) * 60 * 60)
            elif unit.startswith('m'):
                seconds += int(float(time) * 60)
            else:
                seconds += int(time)

        return seconds

    def _signal_handler(self, signum, frame):
        message = self.message
        if message is None:
            message = 'Operation timed out.'
        raise TimeoutError(self.seconds, message)

    def __call__(self, function):
        if not self.seconds:
            return function

        @wraps(function)
        def decorated(*args, **kwargs):
            old_handler = signal.signal(signal.SIGALRM, self._signal_handler)
            old_timer = signal.setitimer(signal.ITIMER_REAL, self.seconds)
            try:
                return function(*args, **kwargs)
            finally:
                signal.setitimer(signal.ITIMER_REAL, *old_timer)
                signal.signal(signal.SIGALRM, old_handler)

        return decorated
