# Copyright (c) 2016 Noviflow
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
Utilities for Simple Switch 2.0 (SS2)
"""

import logging
import time

class _HostCacheEntry(object):
    "Basic class to hold data on a cached host"

    def __init__(self, dpid, port, mac):
        self.dpid = dpid
        self.port = port
        self.mac = mac
        self.timestamp = time.time()
        self.counter = 0

class HostCache(object):
    "Keeps track of recently learned hosts to prevent duplicate flowmods"

    def __init__(self, timeout):
        self.cache = {}
        self.logger = logging.getLogger("SS2HostCache")
        self.timeout = timeout

    def is_new_host(self, dpid, port, mac):
        "Check if the host/port combination is new and add the host entry"

        self.clean_entries()
        entry = self.cache.get((dpid, port, mac), None)
        if entry != None:
            entry.counter += 1
            return False

        entry = _HostCacheEntry(dpid, port, mac)
        self.cache[(dpid, port, mac)] = entry
        self.logger.debug("Learned %s, %s, %s", dpid, port, mac)
        return True

    def clean_entries(self):
        "Clean entries older than self.timeout"

        curtime = time.time()
        _cleaned_cache = {}
        for host in self.cache.values():
            if host.timestamp + self.timeout >= curtime:
                _cleaned_cache[(host.dpid, host.port, host.mac)] = host
            else:
                self.logger.debug("Unlearned %s, %s, %s after %s hits",
                                  host.dpid, host.port, host.mac, host.counter)

        self.cache = _cleaned_cache
