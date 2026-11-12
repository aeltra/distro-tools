# -*- encoding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2016-2018 Tobias Koch <tobias.koch@gmail.com>
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

import os
import re
import ctypes
import stat
import pwd
import grp
import weakref

from ctypes.util import find_library

lib = ctypes.cdll.LoadLibrary(find_library("archive"))

################################## CONSTANTS ##################################

FORMAT_AR = 1
FORMAT_AR_BSD = 2
FORMAT_AR_SVR4 = 3
FORMAT_CPIO = 4
FORMAT_CPIO_NEWC = 5
FORMAT_MTREE = 6
FORMAT_TAR = 7
FORMAT_TAR_GNUTAR = 8
FORMAT_TAR_PAX_INTERCHANGE = 9
FORMAT_TAR_PAX_RESTRICTED = 10
FORMAT_TAR_USTAR = 11
FORMAT_TAR_OLDTAR = 12
FORMAT_ZIP = 13
FORMAT_RAW = 14

COMPRESSION_BZIP2 = 14
COMPRESSION_COMPRESS = 15
COMPRESSION_GZIP = 16
COMPRESSION_LZMA = 17
COMPRESSION_XZ = 18
COMPRESSION_NONE = 19
COMPRESSION_ZSTD = 20

STATUS_OK = 0
STATUS_EOF = 1
STATUS_WARN = -20
STATUS_FATAL = -30

EXTRACT_PERM = 0x0002
EXTRACT_TIME = 0x0004
EXTRACT_SECURE_SYMLINKS = 0x0100
EXTRACT_SECURE_NODOTDOT = 0x0200

################################### CTYPES ####################################

# The types in libarchive's prototypes that ctypes has no name for. time_t
# it knows from Python 3.12 on; before that, long is time_t wherever the
# latter isn't 64 bits on a 32-bit system. dev_t is 64 bits with glibc and
# with musl, on every architecture.
_c_time_t = getattr(ctypes, "c_time_t", ctypes.c_long)
_c_dev_t  = ctypes.c_uint64
_c_mode_t = ctypes.c_uint

_format_functions = {
    FORMAT_AR: "archive_write_set_format_ar_svr4",
    FORMAT_AR_BSD: "archive_write_set_format_ar_bsd",
    FORMAT_AR_SVR4: "archive_write_set_format_ar_svr4",
    FORMAT_CPIO: "archive_write_set_format_cpio",
    FORMAT_CPIO_NEWC: "archive_write_set_format_cpio_newc",
    FORMAT_MTREE: "archive_write_set_format_mtree",
    FORMAT_TAR: "archive_write_set_format_ustar",
    FORMAT_TAR_GNUTAR: "archive_write_set_format_gnutar",
    FORMAT_TAR_PAX_INTERCHANGE: "archive_write_set_format_pax",
    FORMAT_TAR_PAX_RESTRICTED: "archive_write_set_format_pax_restricted",
    FORMAT_TAR_USTAR: "archive_write_set_format_ustar",
    FORMAT_ZIP: "archive_write_set_format_zip",
    FORMAT_RAW: "archive_write_set_format_raw",
}

for func_name in _format_functions.values():
    try:
        func = getattr(lib, func_name)
        func.argtypes = [ctypes.c_void_p]
    except AttributeError:
        pass
#end for

_compression_functions = {
    COMPRESSION_BZIP2: "archive_write_add_filter_bzip2",
    COMPRESSION_COMPRESS: "archive_write_add_filter_compress",
    COMPRESSION_GZIP: "archive_write_add_filter_gzip",
    COMPRESSION_LZMA: "archive_write_add_filter_lzma",
    COMPRESSION_XZ: "archive_write_add_filter_xz",
    COMPRESSION_ZSTD: "archive_write_add_filter_zstd",
    COMPRESSION_NONE: "archive_write_add_filter_none",
    None: "archive_write_add_filter_none"
}

for func_name in _compression_functions.values():
    try:
        func = getattr(lib, func_name)
        func.argtypes = [ctypes.c_void_p]
    except AttributeError:
        pass
#end for

lib.archive_entry_atime.argtypes = [ctypes.c_void_p]
lib.archive_entry_atime.restype = _c_time_t
lib.archive_entry_clear.argtypes = [ctypes.c_void_p]
lib.archive_entry_clear.restype = ctypes.c_void_p
lib.archive_entry_clone.argtypes = [ctypes.c_void_p]
lib.archive_entry_clone.restype = ctypes.c_void_p
lib.archive_entry_copy_gname.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.archive_entry_copy_gname.restype = None
lib.archive_entry_copy_hardlink.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.archive_entry_copy_hardlink.restype = None
lib.archive_entry_copy_pathname.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.archive_entry_copy_pathname.restype = None
lib.archive_entry_copy_symlink.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.archive_entry_copy_symlink.restype = None
lib.archive_entry_copy_uname.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.archive_entry_copy_uname.restype = None
lib.archive_entry_ctime.argtypes = [ctypes.c_void_p]
lib.archive_entry_ctime.restype = _c_time_t
lib.archive_entry_dev.argtypes = [ctypes.c_void_p]
lib.archive_entry_dev.restype = _c_dev_t
lib.archive_entry_devmajor.argtypes = [ctypes.c_void_p]
lib.archive_entry_devmajor.restype = _c_dev_t
lib.archive_entry_devminor.argtypes = [ctypes.c_void_p]
lib.archive_entry_devminor.restype = _c_dev_t
lib.archive_entry_filetype.argtypes = [ctypes.c_void_p]
lib.archive_entry_filetype.restype = _c_mode_t
lib.archive_entry_free.argtypes = [ctypes.c_void_p]
lib.archive_entry_free.restype = None
lib.archive_entry_gid.argtypes = [ctypes.c_void_p]
lib.archive_entry_gid.restype = ctypes.c_int64
lib.archive_entry_gname.argtypes = [ctypes.c_void_p]
lib.archive_entry_gname.restype = ctypes.c_char_p
lib.archive_entry_hardlink.argtypes = [ctypes.c_void_p]
lib.archive_entry_hardlink.restype = ctypes.c_char_p
lib.archive_entry_ino.argtypes = [ctypes.c_void_p]
lib.archive_entry_ino.restype = ctypes.c_int64
lib.archive_entry_mode.argtypes = [ctypes.c_void_p]
lib.archive_entry_mode.restype = _c_mode_t
lib.archive_entry_mtime.argtypes = [ctypes.c_void_p]
lib.archive_entry_mtime.restype = _c_time_t
lib.archive_entry_new.argtypes = []
lib.archive_entry_new.restype = ctypes.c_void_p
lib.archive_entry_nlink.argtypes = [ctypes.c_void_p]
lib.archive_entry_nlink.restype = ctypes.c_uint
lib.archive_entry_pathname.argtypes = [ctypes.c_void_p]
lib.archive_entry_pathname.restype = ctypes.c_char_p
lib.archive_entry_rdevmajor.argtypes = [ctypes.c_void_p]
lib.archive_entry_rdevmajor.restype = _c_dev_t
lib.archive_entry_rdevminor.argtypes = [ctypes.c_void_p]
lib.archive_entry_rdevminor.restype = _c_dev_t
lib.archive_entry_set_atime.argtypes = \
    [ctypes.c_void_p, _c_time_t, ctypes.c_long]
lib.archive_entry_set_atime.restype = None
lib.archive_entry_set_ctime.argtypes = \
    [ctypes.c_void_p, _c_time_t, ctypes.c_long]
lib.archive_entry_set_ctime.restype = None
lib.archive_entry_set_dev.argtypes = [ctypes.c_void_p, _c_dev_t]
lib.archive_entry_set_dev.restype = None
lib.archive_entry_set_devmajor.argtypes = [ctypes.c_void_p, _c_dev_t]
lib.archive_entry_set_devmajor.restype = None
lib.archive_entry_set_devminor.argtypes = [ctypes.c_void_p, _c_dev_t]
lib.archive_entry_set_devminor.restype = None
lib.archive_entry_set_filetype.argtypes = [ctypes.c_void_p, ctypes.c_uint]
lib.archive_entry_set_filetype.restype = None
lib.archive_entry_set_gid.argtypes = [ctypes.c_void_p, ctypes.c_int64]
lib.archive_entry_set_gid.restype = None
lib.archive_entry_set_ino.argtypes = [ctypes.c_void_p, ctypes.c_int64]
lib.archive_entry_set_ino.restype = None
lib.archive_entry_set_mode.argtypes = [ctypes.c_void_p, _c_mode_t]
lib.archive_entry_set_mode.restype = None
lib.archive_entry_set_mtime.argtypes = \
    [ctypes.c_void_p, _c_time_t, ctypes.c_long]
lib.archive_entry_set_mtime.restype = None
lib.archive_entry_set_nlink.argtypes = [ctypes.c_void_p, ctypes.c_uint]
lib.archive_entry_set_nlink.restype = None
lib.archive_entry_set_rdevmajor.argtypes = [ctypes.c_void_p, _c_dev_t]
lib.archive_entry_set_rdevmajor.restype = None
lib.archive_entry_set_rdevminor.argtypes = [ctypes.c_void_p, _c_dev_t]
lib.archive_entry_set_rdevminor.restype = None
lib.archive_entry_set_size.argtypes = [ctypes.c_void_p, ctypes.c_int64]
lib.archive_entry_set_size.restype = None
lib.archive_entry_set_uid.argtypes = [ctypes.c_void_p, ctypes.c_int64]
lib.archive_entry_set_uid.restype = None
lib.archive_entry_size.argtypes = [ctypes.c_void_p]
lib.archive_entry_size.restype = ctypes.c_int64
lib.archive_entry_symlink.argtypes = [ctypes.c_void_p]
lib.archive_entry_symlink.restype = ctypes.c_char_p
lib.archive_entry_uid.argtypes = [ctypes.c_void_p]
lib.archive_entry_uid.restype = ctypes.c_int64
lib.archive_entry_uname.argtypes = [ctypes.c_void_p]
lib.archive_entry_uname.restype = ctypes.c_char_p

for func_name in [
        "archive_entry_gname_utf8",
        "archive_entry_hardlink_utf8",
        "archive_entry_pathname_utf8",
        "archive_entry_symlink_utf8",
        "archive_entry_uname_utf8"]:
    func = getattr(lib, func_name)
    func.argtypes = [ctypes.c_void_p]
    func.restype = ctypes.c_char_p
#end for

lib.archive_error_string.argtypes = [ctypes.c_void_p]
lib.archive_error_string.restype = ctypes.c_char_p
lib.archive_errno.argtypes = [ctypes.c_void_p]
lib.archive_errno.restype = ctypes.c_int

lib.archive_write_free.argtypes = [ctypes.c_void_p]
lib.archive_write_free.restype = ctypes.c_int
lib.archive_write_header.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.archive_write_header.restype = ctypes.c_int
lib.archive_write_new.argtypes = []
lib.archive_write_new.restype = ctypes.c_void_p
lib.archive_write_open_filename.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.archive_write_open_filename.restype = ctypes.c_int
lib.archive_write_data.argtypes = \
    [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
lib.archive_write_data.restype = ctypes.c_ssize_t
lib.archive_write_finish_entry.argtypes = [ctypes.c_void_p]
lib.archive_write_finish_entry.restype = ctypes.c_int
lib.archive_write_close.argtypes = [ctypes.c_void_p]
lib.archive_write_close.restype = ctypes.c_int
lib.archive_write_disk_new.argtypes = []
lib.archive_write_disk_new.restype = ctypes.c_void_p
lib.archive_write_disk_set_options.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.archive_write_disk_set_options.restype = ctypes.c_int

lib.archive_read_free.argtypes = [ctypes.c_void_p]
lib.archive_read_free.restype = ctypes.c_int
lib.archive_read_data.argtypes = \
    [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
lib.archive_read_data.restype = ctypes.c_ssize_t
lib.archive_read_new.argtypes = []
lib.archive_read_new.restype = ctypes.c_void_p
lib.archive_read_next_header2.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.archive_read_next_header2.restype = ctypes.c_int
lib.archive_read_open_filename.argtypes = \
    [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
lib.archive_read_open_filename.restype = ctypes.c_int
lib.archive_read_open_fd.argtypes = \
    [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t]
lib.archive_read_open_fd.restype = ctypes.c_int

# la_ssize_t (*)(struct archive *, void *client_data, const void **buffer)
ARCHIVE_READ_CALLBACK = ctypes.CFUNCTYPE(
    ctypes.c_ssize_t,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p)
)

lib.archive_read_open.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ARCHIVE_READ_CALLBACK,
    ctypes.c_void_p
]
lib.archive_read_open.restype = ctypes.c_int
lib.archive_read_support_filter_all.argtypes = [ctypes.c_void_p]
lib.archive_read_support_filter_all.restype = ctypes.c_int
lib.archive_read_support_filter_program.argtypes = \
    [ctypes.c_void_p, ctypes.c_char_p]
lib.archive_read_support_filter_program.restype = ctypes.c_int
lib.archive_read_support_format_all.argtypes = [ctypes.c_void_p]
lib.archive_read_support_format_all.restype = ctypes.c_int
lib.archive_read_support_format_raw.argtypes = [ctypes.c_void_p]
lib.archive_read_support_format_raw.restype = ctypes.c_int
lib.archive_read_support_format_empty.argtypes = [ctypes.c_void_p]
lib.archive_read_support_format_empty.restype = ctypes.c_int

lib.archive_write_set_option.argtypes = \
    [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
lib.archive_write_set_option.restype = ctypes.c_int

############################### IMPLEMENTATION ################################

def error_string(c_archive_p):
    # NULL when nothing set an error, e.g. a read callback that failed.
    # Not necessarily UTF-8 either: messages may quote pathnames.
    msg = lib.archive_error_string(c_archive_p)
    return msg.decode("utf-8", "replace") if msg else "unknown error"

class ArchiveError(Exception):
    pass

class ArchiveEntry:

    def __init__(self):
        self.__c_entry_p = lib.archive_entry_new()
        if not self.__c_entry_p:
            raise MemoryError("libarchive could not allocate an entry")
    #end function

    def __del__(self):
        self.free()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.free()

    @property
    def _c_entry_p(self):
        # libarchive would dereference the NULL pointer of a freed entry.
        if not self.__c_entry_p:
            raise ArchiveError("the archive entry has been freed")
        return self.__c_entry_p
    #end function

    def free(self):
        if self.__c_entry_p:
            lib.archive_entry_free(self.__c_entry_p)
            self.__c_entry_p = None
    #end function

    def _get_string(self, utf8_func, func):
        #
        # The UTF-8 form doesn't depend on the locale, but there is none
        # where the archive stores bytes that aren't valid in the locale's
        # charset, e.g. a Latin-1 name in an old tar header. Those come
        # as they are, with surrogateescape, which encodes them back to
        # the same bytes. None when the entry has no such name at all.
        #
        value = utf8_func(self._c_entry_p)
        if value is None:
            value = func(self._c_entry_p)
        if value is None:
            return None
        return value.decode("utf-8", "surrogateescape")
    #end function

    @staticmethod
    def _to_bytes(value):
        return value.encode("utf-8", "surrogateescape")

    def clear(self):
        lib.archive_entry_clear(self._c_entry_p)

    @property
    def is_file(self):
        return stat.S_ISREG(self.filetype) != 0 and not self.is_hardlink

    @property
    def is_directory(self):
        return stat.S_ISDIR(self.filetype) != 0

    @property
    def is_symbolic_link(self):
        return stat.S_ISLNK(self.filetype) != 0

    @property
    def is_block_device(self):
        return stat.S_ISBLK(self.filetype) != 0

    @property
    def is_char_device(self):
        return stat.S_ISCHR(self.filetype) != 0

    @property
    def is_fifo(self):
        return stat.S_ISFIFO(self.filetype) != 0

    @property
    def is_socket(self):
        return stat.S_ISSOCK(self.filetype) != 0

    @property
    def is_hardlink(self):
        return bool(self.hardlink)

    @property
    def filetype(self):
        return lib.archive_entry_filetype(self._c_entry_p) & 0o170000

    @filetype.setter
    def filetype(self, filetype):
        lib.archive_entry_set_filetype(self._c_entry_p, filetype)

    @property
    def devmajor(self):
        return lib.archive_entry_devmajor(self._c_entry_p)

    @devmajor.setter
    def devmajor(self, devmajor):
        lib.archive_entry_set_devmajor(self._c_entry_p, devmajor)

    @property
    def devminor(self):
        return lib.archive_entry_devminor(self._c_entry_p)

    @devminor.setter
    def devminor(self, devminor):
        lib.archive_entry_set_devminor(self._c_entry_p, devminor)

    @property
    def atime(self):
        return lib.archive_entry_atime(self._c_entry_p)

    @atime.setter
    def atime(self, atime):
        lib.archive_entry_set_atime(self._c_entry_p, atime, 0)

    @property
    def ctime(self):
        return lib.archive_entry_ctime(self._c_entry_p)

    @ctime.setter
    def ctime(self, ctime):
        lib.archive_entry_set_ctime(self._c_entry_p, ctime, 0)

    def clone(self):
        # Without __init__, which would allocate an entry of its own.
        entry = ArchiveEntry.__new__(ArchiveEntry)
        entry.__c_entry_p = lib.archive_entry_clone(self._c_entry_p)
        if not entry.__c_entry_p:
            raise MemoryError("libarchive could not allocate an entry")
        return entry
    #end function

    @property
    def dev(self):
        return lib.archive_entry_dev(self._c_entry_p)

    @dev.setter
    def dev(self, dev):
        lib.archive_entry_set_dev(self._c_entry_p, dev)

    @property
    def gid(self):
        return lib.archive_entry_gid(self._c_entry_p)

    @gid.setter
    def gid(self, gid):
        lib.archive_entry_set_gid(self._c_entry_p, gid)

    @property
    def gname(self):
        return self._get_string(lib.archive_entry_gname_utf8,
            lib.archive_entry_gname)

    @gname.setter
    def gname(self, gname):
        lib.archive_entry_copy_gname(self._c_entry_p, self._to_bytes(gname))

    @property
    def hardlink(self):
        return self._get_string(lib.archive_entry_hardlink_utf8,
            lib.archive_entry_hardlink)

    @hardlink.setter
    def hardlink(self, hardlink):
        lib.archive_entry_copy_hardlink(self._c_entry_p,
                self._to_bytes(hardlink))

    @property
    def inode(self):
        return lib.archive_entry_ino(self._c_entry_p)

    @inode.setter
    def inode(self, inode):
        lib.archive_entry_set_ino(self._c_entry_p, inode)

    @property
    def mode(self):
        return lib.archive_entry_mode(self._c_entry_p) & 0o7777

    @mode.setter
    def mode(self, mode):
        lib.archive_entry_set_mode(self._c_entry_p, mode)

    @property
    def mtime(self):
        return lib.archive_entry_mtime(self._c_entry_p)

    @mtime.setter
    def mtime(self, mtime):
        lib.archive_entry_set_mtime(self._c_entry_p, mtime, 0)

    @property
    def nlink(self):
        return lib.archive_entry_nlink(self._c_entry_p)

    @nlink.setter
    def nlink(self, nlink):
        lib.archive_entry_set_nlink(self._c_entry_p, nlink)

    @property
    def pathname(self):
        return self._get_string(lib.archive_entry_pathname_utf8,
            lib.archive_entry_pathname)

    @pathname.setter
    def pathname(self, pathname):
        lib.archive_entry_copy_pathname(self._c_entry_p,
                self._to_bytes(pathname))
    #end function

    @property
    def rdevmajor(self):
        return lib.archive_entry_rdevmajor(self._c_entry_p)

    @rdevmajor.setter
    def rdevmajor(self, rdevmajor):
        lib.archive_entry_set_rdevmajor(self._c_entry_p, rdevmajor)

    @property
    def rdevminor(self):
        return lib.archive_entry_rdevminor(self._c_entry_p)

    @rdevminor.setter
    def rdevminor(self, rdevminor):
        lib.archive_entry_set_rdevminor(self._c_entry_p, rdevminor)

    @property
    def size(self):
        return lib.archive_entry_size(self._c_entry_p)

    @size.setter
    def size(self, size):
        lib.archive_entry_set_size(self._c_entry_p, size)

    @property
    def symlink(self):
        return self._get_string(lib.archive_entry_symlink_utf8,
            lib.archive_entry_symlink)

    @symlink.setter
    def symlink(self, symlink):
        lib.archive_entry_copy_symlink(self._c_entry_p,
                self._to_bytes(symlink))
    #end function

    @property
    def uid(self):
        return lib.archive_entry_uid(self._c_entry_p)

    @uid.setter
    def uid(self, uid):
        lib.archive_entry_set_uid(self._c_entry_p, uid)

    @property
    def uname(self):
        return self._get_string(lib.archive_entry_uname_utf8,
            lib.archive_entry_uname)

    @uname.setter
    def uname(self, uname):
        lib.archive_entry_copy_uname(self._c_entry_p,
                self._to_bytes(uname))
    #end function

    def copy_stat(self, filename, no_atime=False, no_mtime=False,
            no_ctime=False):
        if not os.path.exists(filename):
            raise ArchiveError("no such file or directory: '%s'" % filename)

        kwargs = {
            "no_atime": no_atime,
            "no_mtime": no_mtime,
            "no_ctime": no_ctime
        }

        self._copy_raw_stat(os.lstat(filename), **kwargs)
    #end function

    def _copy_raw_stat(self, stats, **kwargs):
        no_atime = kwargs.get("no_atime", False)
        no_mtime = kwargs.get("no_mtime", False)
        no_ctime = kwargs.get("no_ctime", False)

        self.filetype = stats.st_mode
        self.mode     = stats.st_mode
        self.dev      = stats.st_dev
        self.inode    = stats.st_ino
        self.nlink    = stats.st_nlink

        self.uid      = stats.st_uid
        self.gid      = stats.st_gid

        try:
            self.uname = pwd.getpwuid(stats.st_uid).pw_name
        except KeyError:
            pass
        try:
            self.gname = grp.getgrgid(stats.st_gid).gr_name
        except KeyError:
            pass

        self.size     = stats.st_size

        if not no_atime:
            self.atime = int(stats.st_atime)
        if not no_mtime:
            self.mtime = int(stats.st_mtime)
        if not no_ctime:
            self.ctime = int(stats.st_ctime)
    #end function

#end class

class ArchiveFileWriter:

    def __init__(self, filename, archive_format, compression=None,
            options=None):
        self._c_archive_p = lib.archive_write_new()
        self._filename = filename
        self._hardlinks = {}

        if not self._c_archive_p:
            raise MemoryError("libarchive could not allocate an archive")

        try:
            func = getattr(lib, _compression_functions[compression])
            func(self._c_archive_p)
        except (KeyError, AttributeError):
            self._free()
            raise ArchiveError("invalid or unsupported compression scheme.")
        #end try

        try:
            func = getattr(lib, _format_functions[archive_format])
            func(self._c_archive_p)
        except (KeyError, AttributeError):
            self._free()
            raise ArchiveError("invalid or unsupported archive format.")
        #end try

        if options is not None:
            for mod, key, val in options:
                self.__set_filter_option(mod, key, val)
        #end if

        if lib.archive_write_open_filename(
                self._c_archive_p, filename.encode("utf-8")) != STATUS_OK:
            msg = error_string(self._c_archive_p)
            self._free()
            raise ArchiveError(msg)
        #end if
    #end function

    def __del__(self):
        # Python reports an error raised here on stderr, so the archive
        # being incomplete doesn't go unnoticed even if nobody closes it.
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.close()
            return
        #end if

        # The archive is incomplete anyway: the error that made it so is
        # the one to report.
        try:
            self.close()
        except ArchiveError:
            pass
    #end function

    def close(self):
        """
        Writes out what is still buffered and finishes the compression.
        Raises an ArchiveError if that fails, in which case the archive is
        incomplete.
        """
        if not self._c_archive_p:
            return

        msg = None

        try:
            if lib.archive_write_close(self._c_archive_p) != STATUS_OK:
                msg = error_string(self._c_archive_p)

                # E.g. just "Write error", without saying why.
                errno = lib.archive_errno(self._c_archive_p)
                if errno > 0:
                    msg = "{}: {}".format(msg, os.strerror(errno))

                msg = "failed to write '{}': {}".format(self._filename, msg)
            #end if
        finally:
            lib.archive_write_free(self._c_archive_p)
            self._c_archive_p = None
        #end try

        if msg is not None:
            raise ArchiveError(msg)
    #end function

    def _free(self):
        # Without asking how closing went: for an archive that never got
        # opened, that would only add an error of its own.
        if self._c_archive_p:
            lib.archive_write_free(self._c_archive_p)
            self._c_archive_p = None
    #end function

    def write_entry(self, entry):
        if not isinstance(entry, ArchiveEntry):
            msg = "first argument to write_entry must be an ArchiveEntry."
            raise ValueError(msg)

        # automatic hardlink handling
        if entry.nlink > 1 and entry.inode:
            path = self._hardlinks.setdefault(entry.dev, {}).get(entry.inode)

            if not path:
                self._hardlinks[entry.dev][entry.inode] = entry.pathname
            else:
                entry.hardlink = path
            #end if
        #end if

        if lib.archive_write_header(self._c_archive_p,
                entry._c_entry_p) != STATUS_OK:
            raise ArchiveError(error_string(self._c_archive_p))
    #end function

    def write_data(self, data):
        if not isinstance(data, bytes):
            msg = "data passed to write_data has to be a 'bytes' string."
            raise ValueError(msg)
        bytes_written = lib.archive_write_data(self._c_archive_p,
                data, len(data))
        if bytes_written < 0:
            raise ArchiveError(error_string(self._c_archive_p))
        return bytes_written
    #end function

    def add_file(self, source_file, pathname=None, uname=None, gname=None):
        if not os.path.isfile(source_file):
            raise ArchiveError("No such file: {}".format(source_file))
        if not pathname:
            pathname = source_file

        with ArchiveEntry() as archive_entry:
            archive_entry.copy_stat(source_file)
            archive_entry.pathname = pathname

            if uname:
                archive_entry.uname = uname
            if gname:
                archive_entry.gname = gname

            self.write_entry(archive_entry)

            with open(source_file, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    self.write_data(chunk)
            #end with
        #end with
    #end function

    def __set_filter_option(self, mod, key, val):
        m = mod.encode("utf-8") if mod is not None else None
        k = key.encode("utf-8") if key is not None else None
        v = val.encode("utf-8") if val is not None else None

        if self._c_archive_p:
            rval = lib.archive_write_set_option(
                    self._c_archive_p, m, k, v)

            if rval != STATUS_OK:
                msg = error_string(self._c_archive_p)
                raise ArchiveError(msg)
            #end if
        #end if
    #end function

#end class

class ArchiveFileReader:

    def __init__(self, source, cmd=None, raw=False, buf_size=4096):
        """
        Reads an archive from source, which is one of:

        * the name of a file,
        * the number of a file descriptor open for reading, which is read
          from its current position and left open,
        * another ArchiveFileReader, whose current entry is read: an archive
          inside an archive, decompressed as it is read and never written
          out anywhere. It reads from the outer reader, which mustn't be
          used until it is done; moving the outer reader on to its next
          entry or closing it closes this one.
        """
        self._c_archive_p   = lib.archive_read_new()
        self._parent        = None
        self._child         = None
        self._read_buffer   = None
        self._read_callback  = None
        self._read_error     = None
        self._read_interrupt = None

        if not self._c_archive_p:
            raise MemoryError("libarchive could not allocate an archive")

        try:
            self.__init_helper(source, cmd=cmd, raw=raw)
        except Exception:
            msg = self._error_string()
            self.close()
            self._raise_interrupt()
            raise ArchiveError(msg)
        #end try
    #end function

    def __init_helper(self, source, cmd=None, raw=False):
        if cmd:
            if lib.archive_read_support_filter_program(self._c_archive_p,
                    cmd) != STATUS_OK:
                raise Exception()
        else:
            if lib.archive_read_support_filter_all(self._c_archive_p) != \
                    STATUS_OK:
                raise Exception()
        #end if

        if raw:
            if lib.archive_read_support_format_raw(self._c_archive_p) != \
                    STATUS_OK:
                raise Exception()
            if lib.archive_read_support_format_empty(self._c_archive_p) != \
                    STATUS_OK:
                raise Exception()
        else:
            if lib.archive_read_support_format_all(self._c_archive_p) != \
                    STATUS_OK:
                raise Exception()
        #end if

        if isinstance(source, ArchiveFileReader):
            if not source._c_archive_p:
                self._read_error = "the outer archive is closed"
                raise Exception()

            source._close_child()

            self._parent        = source
            self._read_buffer   = ctypes.create_string_buffer(64 * 1024)
            self._read_callback = ARCHIVE_READ_CALLBACK(self._read_parent)

            # A weak reference, so the outer reader doesn't keep this one
            # alive; this one keeps the outer one alive through _parent.
            source._child = weakref.ref(self)

            rval = lib.archive_read_open(self._c_archive_p, None, None,
                self._read_callback, None)
        elif isinstance(source, int):
            rval = lib.archive_read_open_fd(self._c_archive_p, source, 10240)
        else:
            rval = lib.archive_read_open_filename(self._c_archive_p,
                source.encode("utf-8"), 4096)
        #end if

        if rval != STATUS_OK:
            raise Exception()
    #end function

    def _read_parent(self, c_archive_p, client_data, c_buffer_pp):
        #
        # Called from within libarchive: an exception must not get out,
        # because ctypes would only print it and return 0, which reads
        # as the end of the data. That includes SystemExit and
        # KeyboardInterrupt from a signal handler, which are raised
        # again once libarchive has returned.
        #
        try:
            parent = self._parent

            if parent is None or not parent._c_archive_p:
                self._read_error = "the outer archive is closed"
                return STATUS_FATAL
            #end if

            rval = lib.archive_read_data(parent._c_archive_p,
                ctypes.addressof(self._read_buffer), len(self._read_buffer))

            if rval < 0:
                self._read_error = error_string(parent._c_archive_p)
                return STATUS_FATAL
            #end if

            c_buffer_pp[0] = ctypes.addressof(self._read_buffer)
            return rval
        except Exception as e:
            self._read_error = str(e)
            return STATUS_FATAL
        except BaseException as e:
            self._read_error     = "interrupted"
            self._read_interrupt = e
            return STATUS_FATAL
        #end try
    #end function

    def _raise_interrupt(self):
        interrupt, self._read_interrupt = self._read_interrupt, None
        if interrupt is not None:
            raise interrupt
    #end function

    def _close_child(self):
        child = self._child() if self._child else None
        if child is not None:
            child.close()
        self._child = None
    #end function

    def _check_open(self):
        # libarchive would dereference the NULL pointer. An inner archive
        # is closed implicitly, when the outer one moves on.
        if not self._c_archive_p:
            raise ArchiveError("the archive is closed")
    #end function

    def _error_string(self):
        # What went wrong reading the outer archive, if that's where the
        # error lies: libarchive doesn't know.
        if self._read_error:
            return self._read_error
        return error_string(self._c_archive_p)
    #end function

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __iter__(self):
        #
        # Each entry frees itself once nothing refers to it any more: in
        # a loop, when the next one takes its place. Freeing it here would
        # leave an entry the caller kept around pointing at nothing.
        #
        while True:
            archive_entry = self.next_entry()
            if archive_entry is None:
                break
            yield archive_entry
        #end while
    #end function

    def close(self):
        # An inner archive first: it reads from this one.
        self._close_child()

        if self._c_archive_p:
            lib.archive_read_free(self._c_archive_p)
            self._c_archive_p = None

        self._parent        = None
        self._read_callback = None
    #end function

    def next_entry(self):
        self._check_open()
        self._close_child()

        archive_entry = ArchiveEntry()

        rval = lib.archive_read_next_header2(self._c_archive_p,
                archive_entry._c_entry_p)

        if self._read_interrupt is not None:
            archive_entry.free()
            self._raise_interrupt()

        if rval == STATUS_EOF:
            archive_entry.free()
            self.close()
            return None
        elif rval in (STATUS_OK, STATUS_WARN):
            # A warning still gives a usable entry, e.g. one whose names
            # can't be converted to the locale's charset: the properties
            # read their UTF-8 form first.
            return archive_entry
        else:
            archive_entry.free()
            raise ArchiveError(self._error_string())
    #end function

    def read_data(self, size=0):
        result = []

        if size > 0:
            result = [self.__read_data(size)]
        else:
            while True:
                buf = self.__read_data(8*1024)
                if not buf:
                    break
                result.append(buf)
            #end while
        #end function

        return b"".join(result)
    #end function

    def unpack_to_disk(self, base_dir=".", strip_components=0,
            sane_file_modes=True):
        """
        Unpacks directories, regular files and symbolic links below
        base_dir and refuses any other kind of entry. Modes are kept as
        they are, except for the setuid, setgid and sticky bits, which are
        dropped; with sane_file_modes the owner may also always read and
        write files and enter directories. Owners are not restored.

        The writing is left to libarchive, which refuses to write to a
        path that contains ".." or that leads through a symbolic link, so
        a crafted archive can't write outside of base_dir. Either way,
        unpacking stops at the first entry that can't be unpacked.
        """
        # Without symbolic links, which libarchive would refuse to write
        # through.
        base_dir = os.path.realpath(base_dir)

        c_disk_p = lib.archive_write_disk_new()
        if not c_disk_p:
            raise MemoryError("libarchive could not allocate an archive")

        try:
            lib.archive_write_disk_set_options(
                c_disk_p,
                EXTRACT_PERM |
                EXTRACT_TIME |
                EXTRACT_SECURE_SYMLINKS |
                EXTRACT_SECURE_NODOTDOT
            )

            for entry in self:
                name = entry.pathname

                pathname = name.strip()
                pathname = re.sub(r"^(?:\.+/+)", "", pathname)
                pathname = pathname.lstrip(os.sep)

                components = pathname.split(os.sep)[strip_components:]

                # base_dir itself, or above where the stripping starts.
                if not "".join(components):
                    continue

                if entry.is_directory:
                    sane_mode = 0o700
                elif entry.is_file:
                    sane_mode = 0o600
                elif entry.is_symbolic_link:
                    sane_mode = None
                else:
                    raise ArchiveError(
                        "Don't know how to create '%s' with special file "
                        "type." % name
                    )
                #end if

                if sane_mode is not None:
                    mode = entry.mode & 0o777
                    if sane_file_modes:
                        mode |= sane_mode
                    entry.mode = entry.filetype | mode
                #end if

                entry.pathname = os.sep.join([base_dir, ] + components)

                self._check_disk_status(c_disk_p, name,
                    lib.archive_write_header(c_disk_p, entry._c_entry_p))

                if entry.is_file:
                    for chunk in iter(lambda: self.read_data(65536), b""):
                        if lib.archive_write_data(c_disk_p, chunk,
                                len(chunk)) < 0:
                            self._check_disk_status(c_disk_p, name,
                                STATUS_FATAL)
                    #end for
                #end if

                self._check_disk_status(c_disk_p, name,
                    lib.archive_write_finish_entry(c_disk_p))
            #end for

            # Sets the modes and times of the directories, which are left
            # writable until then.
            self._check_disk_status(c_disk_p, base_dir,
                lib.archive_write_close(c_disk_p))
        finally:
            lib.archive_write_free(c_disk_p)
        #end try
    #end function

    @staticmethod
    def _check_disk_status(c_disk_p, name, rval):
        # A warning is about metadata that couldn't be restored, such as a
        # time; failing means the entry wasn't written.
        if rval < STATUS_WARN:
            raise ArchiveError(
                "failed to unpack '{}': {}"
                .format(name, error_string(c_disk_p))
            )
        #end if
    #end function

    def __read_data(self, size):
        self._check_open()

        buf = ctypes.create_string_buffer(size)

        rval = lib.archive_read_data(self._c_archive_p,
                ctypes.addressof(buf), size)
        self._raise_interrupt()
        if rval < 0:
            raise ArchiveError(self._error_string())

        return buf[0:rval]
    #end function

#end class
