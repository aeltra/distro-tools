# -*- encoding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2026 Tobias Koch <tobias.koch@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import logging
import os
import re

from aeltra.error import AeltraError

LOGGER = logging.getLogger(__name__)

class AuthFile:
    """
    Download credentials from a file in the format of apt's auth.conf, as
    aept reads it: netrc-style "machine", "login" and "password" tokens, in
    any layout across lines. For an Aeltra archive:

        machine archive.aeltra.eu login token password aeltra_api_...

    Only https URLs ever match an entry, by host and, where the machine
    names one, a path prefix that ends at a segment boundary. The first
    matching entry wins.

    Nothing read from the file is ever logged: a malformed entry is reported
    by file and line, never by content, since the token at fault may well
    be a password.
    """

    HTTPS_PREFIX = "https://"

    class Error(AeltraError):
        pass

    class Entry:

        def __init__(self, host, path, login, password):
            self.host     = host
            self.path     = path
            self.login    = login
            self.password = password
        #end function

        def __repr__(self):
            # Without the login and password, which would otherwise end up
            # in tracebacks and debug output.
            return "AuthFile.Entry(host={!r}, path={!r})"\
                .format(self.host, self.path)
        #end function

        def matches(self, host, path):
            if host != self.host:
                return False
            if not self.path:
                return True
            if not path.startswith(self.path):
                return False
            return path[len(self.path):][:1] in ("", "/", "?", "#")
        #end function

    #end class

    def __init__(self, entries=None):
        self._entries = list(entries or [])

    @classmethod
    def load(cls, filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                # Readable by a group is fine: a service's credentials are
                # typically root-owned and readable by its group only.
                if os.fstat(f.fileno()).st_mode & 0o007:
                    LOGGER.warning(
                        "auth file '{}' is accessible by other users"
                        .format(filename)
                    )
                #end if

                return cls.parse(f, filename=filename)
            #end with
        except (OSError, UnicodeDecodeError) as e:
            raise AuthFile.Error(
                "cannot read auth file '{}': {}".format(
                    filename,
                    e.strerror if isinstance(e, OSError) else
                        "not valid UTF-8"
                )
            )
        #end try
    #end function

    @classmethod
    def parse(cls, lines, filename="<auth file>"):
        entries = []
        pending = {}
        expect  = None
        lineno  = 0

        for lineno, line in enumerate(lines, start=1):
            for token in line.split():
                if expect:
                    pending[expect] = token
                    expect = None
                # A '#' starts a comment only at the start of a token and
                # only where no value is expected, since a password may
                # contain or even start with '#'.
                elif token.startswith("#"):
                    break
                elif token == "machine":
                    cls._finish(entries, pending, filename)
                    pending = {"line": lineno}
                    expect  = "machine"
                elif token in ("login", "password") and "machine" in pending:
                    expect = token
                else:
                    LOGGER.warning(
                        "auth file '{}' line {}: unexpected token, "
                        "ignoring it".format(filename, lineno)
                    )
                #end if
            #end for
        #end for

        if expect:
            LOGGER.warning(
                "auth file '{}' line {}: missing value at end of file"
                .format(filename, lineno)
            )
        #end if

        cls._finish(entries, pending, filename)
        return cls(entries)
    #end function

    def find(self, url):
        """
        The (login, password) pair for a URL, or None. A URL that carries
        credentials of its own gets none.
        """
        if url[:len(self.HTTPS_PREFIX)].lower() != self.HTTPS_PREFIX:
            return None

        authority, path = re.match(
            r"([^/?#]*)(.*)", url[len(self.HTTPS_PREFIX):], re.DOTALL
        ).groups()

        if "@" in authority:
            return None

        host = self._strip_default_port(authority).lower()

        for entry in self._entries:
            if entry.matches(host, path):
                return entry.login, entry.password
        #end for

        return None
    #end function

    # HELPERS

    @classmethod
    def _finish(cls, entries, pending, filename):
        if not pending.get("machine"):
            return

        line = pending["line"]

        if not pending.get("login") or not pending.get("password"):
            LOGGER.warning(
                "auth file '{}' line {}: entry lacks a login or a password, "
                "ignoring it".format(filename, line)
            )
            return
        #end if

        host_and_path = cls._split_machine(pending["machine"])
        if host_and_path is None:
            LOGGER.warning(
                "auth file '{}' line {}: machine is not an https host, "
                "ignoring entry".format(filename, line)
            )
            return
        #end if

        host, path = host_and_path

        entries.append(
            AuthFile.Entry(host, path, pending["login"], pending["password"])
        )
    #end function

    @classmethod
    def _split_machine(cls, machine):
        """
        Host and path prefix of a "machine" value, or None for anything
        that names a scheme other than https: apt sends credentials over
        plain http only when told to, and aept doesn't do it at all.
        """
        if machine[:len(cls.HTTPS_PREFIX)].lower() == cls.HTTPS_PREFIX:
            machine = machine[len(cls.HTTPS_PREFIX):]
        elif "://" in machine:
            return None

        host, slash, path = machine.partition("/")
        host = cls._strip_default_port(host).lower()

        if not host:
            return None

        return host, (slash + path).rstrip("/")
    #end function

    @staticmethod
    def _strip_default_port(authority):
        # A URL may or may not spell out the default https port.
        if authority.endswith(":443"):
            return authority[:-4]
        return authority
    #end function

#end class
