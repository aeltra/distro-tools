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

import fnmatch
import glob
import logging
import os
import re
import stat
import subprocess
import textwrap

from collections import OrderedDict
from lxml import etree
from pathlib import Path

from aeltra.error import UnmetDependency, PackagingError

from aeltra.package.aeltrapack.basepackage import BasePackage
from aeltra.package.aeltrapack.packagedesc import PackageDescription
from aeltra.package.aeltrapack.filestats import FileStats

from aeltra.miscellaneous.braceexpand import braceexpand
from aeltra.miscellaneous.platform import Platform
from aeltra.miscellaneous.switch import switch

LOGGER = logging.getLogger(__name__)

class BinaryPackage(BasePackage):

    class EntryAttributes:

        def __init__(self, spec={}):
            self.deftype  = spec.get("deftype", "file")
            self.mode     = spec.get("mode")
            self.owner    = spec.get("owner")
            self.group    = spec.get("group")
            self.conffile = spec.get("conffile")
            self.stats    = spec.get("stats")
            self.dbg_info = None

            if isinstance(self.conffile, str):
                self.conffile = True if self.conffile.lower() == "true" \
                        else False
            if isinstance(self.mode, str):
                self.mode = int("0o%s" % self.mode, 8)
        #end function

    #end class

    def __init__(self, xml_config, **kwargs):
        build_for = kwargs.get("build_for", "target")

        if isinstance(xml_config, etree._Element):
            bin_node = xml_config
        elif isinstance(xml_config, str):
            bin_node = etree.fromstring(xml_config)
        else:
            msg = "expected 'etree._Element' or 'str' but got '%s'" % \
                    xml_config.__class__.__name__
            raise ValueError(msg)
        #end if

        epoch = \
            bin_node.get("epoch",    0)
        version = \
            bin_node.get("version", "")
        revision = \
            bin_node.get("revision", None)

        self.name = \
            bin_node.get("name")
        self.description = \
            PackageDescription(bin_node.find("description"))
        self.maintainer = \
            bin_node.get("maintainer") + " <" + \
            bin_node.get("email") + ">"

        self.version = \
            (epoch + ":" if int(epoch) > 0 else "") + version + \
            ("-" + revision if revision is not None else "")

        self.section = \
            bin_node.get("section", "unknown")
        self.source = \
            bin_node.get("source")
        self.architecture = \
            bin_node.get("architecture")
        self.date = \
            bin_node.get("date")

        self.make_debug_pkgs = \
            kwargs.get("debug_pkgs", True)
        self.install_prefix = \
            kwargs.get("install_prefix", "/usr")
        self.host_type = \
            kwargs.get("host_type", Platform.target_type())

        self.relations = {}

        for dep_type in ["requires", "provides", "conflicts", "replaces"]:
            dep_node = bin_node.find(dep_type)

            if dep_node is None:
                continue

            for pkg_node in dep_node.findall(".//package"):
                dep_version = pkg_node.get("version", "").strip()

                if dep_version.endswith("=="):
                    pkg_node.attrib["version"] = dep_version[:-1] \
                        + " " + self.version

                pkg_prefix = pkg_node.get(build_for + "-prefix", None)

                if pkg_prefix is None:
                    if self.architecture == "tools":
                        pkg_prefix = "tools-"
                if pkg_prefix is not None:
                    pkg_node.attrib["name"] = pkg_prefix + \
                            pkg_node.attrib["name"]
            #end for

            self.relations[dep_type] = BasePackage.DependencySpecification\
                    .from_xml(dep_node)
        #end for

        self.contents = {}
        self.content_spec = {}
        prefix_regex = re.compile("^" + re.escape("${prefix}"))

        for node in bin_node.findall('contents/*'):
            src = prefix_regex.sub(
                self.install_prefix, node.get("src").strip()
            )

            if len(src) > 1:
                src = src.rstrip(os.sep)

            # '<file>' nodes have precedence over '<dir>'
            entry = self.content_spec.get(src)
            if entry and entry.deftype == "file" and node.tag == "dir":
                continue

            self.content_spec[src] = BinaryPackage.EntryAttributes({
                "deftype":  node.tag,
                "mode":     node.get("mode"),
                "owner":    node.get("owner"),
                "group":    node.get("group"),
                "conffile": node.get("conffile")
            })
        #end for

        self.maintainer_scripts = {}
        for node in bin_node.findall("maintainer-scripts/*"):
            if node.tag in ["preinst", "postinst", "prerm", "postrm"]:
                self.maintainer_scripts[node.tag] = \
                    self._script_header(node) + \
                    etree.tostring(node, method="text", encoding="unicode")
            #end if
        #end for

        self.triggers = None
        trigger_node = bin_node.find("maintainer-scripts/trigger")
        if trigger_node is not None:
            lines = []
            for interest in trigger_node.findall("interest"):
                path = interest.get("path")
                self._validate_trigger_path(path)
                modify_only = interest.get("modify-only", "false").lower()
                if modify_only == "true":
                    lines.append("+" + path)
                else:
                    lines.append(path)
                #end if
            #end for
            self.triggers = "\n".join(lines) + "\n"

            script_node = trigger_node.find("script")
            self.maintainer_scripts["trigger"] = \
                self._script_header(script_node) + \
                etree.tostring(script_node, method="text", encoding="unicode")
        #end if

        content_node = bin_node.find("contents")
        if content_node is not None:
            self.content_subdir = content_node.get("subdir")
            if content_node.get("collect-py-cache-files", "false")\
                    .lower() == "true":
                self.collect_py_cache_files = True
            else:
                self.collect_py_cache_files = False
            #end if
        else:
            self.content_subdir = ""
            self.collect_py_cache_files = False
        #end function

        self.basedir        = os.path.realpath(".")
        self.output_dir     = "."
    #end function

    @property
    def version_tuple(self):
        regexp = r"^(?:(\d+):)?([-.+~a-zA-Z0-9]+?)(?:-([.~+a-zA-Z0-9]+)){0,1}$"
        m = re.match(regexp, self.version)
        return m.group(1, 2, 3)
    #end function

    @property
    def basedir(self):
        return self._basedir

    @basedir.setter
    def basedir(self, basedir):
        real_base_dir = os.path.realpath(basedir)
        if basedir:
            self._basedir = real_base_dir
        if self.content_subdir:
            self._basedir = real_base_dir + os.sep + self.content_subdir
    #end function

    @property
    def output_dir(self):
        return self._output_dir

    @output_dir.setter
    def output_dir(self, output_dir):
        self._output_dir = os.path.realpath(output_dir)

    def prepare(self):
        try:
            self.generate_file_list()
        except ValueError as e:
            raise PackagingError("error generating file list: " + str(e))
    #end function

    def pack(self, shlib_cache, bin_pkgs):
        self.shlib_deps(shlib_cache, bin_pkgs)
        self.do_pack()
    #end function

    # Files with these names are not executable, see default_mode().
    MODE_0644_PATTERNS = [
        # libraries and related files
        "*.so.*", "*.so", "*.la", "*.a",
        # web application related files
        "*.js", "*.css", "*.scss", "*.sass",
        # images
        "*.jpeg", "*.jpg", "*.png", "*.gif",
        # OCaml native-code shared objects
        "*.cmxs",
        # Node bindings
        "*.node",
    ]

    @staticmethod
    def default_mode(src, stats, install_prefix="/usr"):
        """
        Returns the mode a file or directory gets in a package when its
        entry in the package file states none. It is the one that
        dh_fixperms of Debian's debhelper would give it, whose rules are
        applied in the same order.

        First 0755 for a directory and for a file that anybody may
        execute, 0644 for any other file. This is what "chmod
        go=rX,u+rw,a-s" makes of the mode on disk, which depends on the
        umask of the build and on what the build system of the sources
        does. So a setuid, setgid or sticky bit is dropped, and a file
        that group or others cannot read is opened to them. Such a mode is
        in a package only when the package file states it. The one
        difference to chmod: a file that only group or others may execute
        is executable for its owner too.

        Then, for files, by where they are and what they are called:

        * not executable: documentation except examples, manual pages,
          headers, desktop files, themes, the overrides for lintian, Perl
          modules, and libraries, scripts for the web and images by their
          names (MODE_0644_PATTERNS);
        * executable: everything in the folders for programs and in
          /etc/init.d, also when a name says otherwise;
        * not writable: the .ali files of Ada;
        * executable: cli.js and bin.js of a package for Node.js;
        * 0440: the files in /etc/sudoers.d.

        src is the path in the package. The folders are looked for below
        install_prefix, where dh_fixperms has "usr".
        """
        if stats.is_directory:
            return 0o755

        mode = 0o755 if (stats.mode & 0o111) else 0o644

        def below(*folders):
            for folder in folders:
                if src.startswith(folder.rstrip(os.sep) + os.sep):
                    return True
            return False
        #end inline function

        prefix = install_prefix.rstrip(os.sep)
        name   = os.path.basename(src)

        doc_dir = prefix + "/share/doc"

        if below(doc_dir) and not re.match(
                re.escape(doc_dir) + r"/[^/]*/examples/.*", src):
            mode = 0o644

        if below(
            prefix + "/share/man",
            prefix + "/include",
            prefix + "/share/applications",
            prefix + "/share/lintian/overrides",
            prefix + "/share/themes"
        ):
            mode = 0o644

        if name.endswith(".pm") and (mode & 0o005) == 0o005 and \
                below(prefix + "/lib/perl5", prefix + "/share/perl5"):
            mode &= ~0o111

        for pattern in BinaryPackage.MODE_0644_PATTERNS:
            if fnmatch.fnmatchcase(name, pattern):
                mode = 0o644
                break

        if below(
            prefix + "/bin",
            "/bin",
            prefix + "/sbin",
            "/sbin",
            prefix + "/games",
            prefix + "/libexec",
            "/etc/init.d"
        ):
            mode |= 0o111

        if name.endswith(".ali") and below(prefix + "/lib"):
            mode &= ~0o222

        if name in ["cli.js", "bin.js"] and below(prefix + "/lib/nodejs"):
            mode = 0o755

        if below("/etc/sudoers.d"):
            mode = 0o440

        return mode
    #end function

    def apply_default_modes(self, contents):
        """
        Gives every directory and regular file in contents whose entry
        states no mode the default mode, see default_mode(), and warns
        when that takes away a setuid, setgid or sticky bit or opens what
        group or others could not read or enter on disk.

        The root directory is the folder the build installed into. Its
        mode on disk says nothing about the package, so it gets the
        default mode without a warning.
        """
        for src, attr in contents.items():
            if attr.mode is not None:
                continue
            if not (attr.stats.is_directory or attr.stats.is_file):
                continue

            on_disk   = attr.stats.mode
            attr.mode = BinaryPackage.default_mode(
                src, attr.stats, self.install_prefix
            )

            if src == os.sep:
                continue

            special = stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX
            opened  = attr.mode & ~on_disk & \
                (0o055 if attr.stats.is_directory else 0o044)

            if (on_disk & special) or opened:
                LOGGER.warning(
                    "'%s' has mode %04o on disk and gets %04o: state "
                    "its mode in the package file to keep it." %
                    (src, on_disk, attr.mode)
                )
            #end if
        #end for
    #end function

    def generate_file_list(self):
        contents = {}

        for src, attr in self.content_spec.items():
            rel_path = os.path.normpath(src.lstrip(os.sep))
            abs_path = os.path.normpath(os.sep.join([self.basedir, src]))

            deftype  = attr.deftype
            mode     = attr.mode
            owner    = attr.owner
            group    = attr.group
            conffile = attr.conffile

            listing  = []

            for case in switch(deftype):
                if case("dir"):
                    attr.stats = FileStats.default_dir_stats()
                    contents[src] = attr
                    break
                if case("file"):
                    if glob.escape(src) != src or "{" in src:
                        # entry is a glob pattern
                        if "{" in src:
                            expansions = list(braceexpand(rel_path))
                        else:
                            expansions = [rel_path]
                        #end if
                        for pattern in expansions:
                            listing += list(Path(self.basedir).glob(pattern))
                    elif os.path.isdir(abs_path) and not \
                            os.path.islink(abs_path):
                        # entry is a real directory
                        listing = list(
                            Path(self.basedir).rglob(rel_path + "/**/*")
                        )
                        if src not in contents:
                            attr.stats = \
                                FileStats.detect_from_filename(abs_path)
                            contents.setdefault(src, attr)
                    else:
                        # entry is a symlink or file
                        attr.stats = FileStats.detect_from_filename(abs_path)
                        contents[src] = attr
                    break
                #end if
            #end switch

            for path in listing:
                abs_path = path.as_posix()
                pkg_path = os.sep + path.relative_to(self.basedir).as_posix()
                if pkg_path in contents:
                    continue
                stats = FileStats.detect_from_filename(abs_path)
                contents[pkg_path] = BinaryPackage.EntryAttributes({
                    "deftype":  "file",
                    "mode":     mode,
                    "owner":    owner,
                    "group":    group,
                    "conffile": False if not stats.is_file else conffile,
                    "stats":    stats
                })
            #end for
        #end for

        # make sure directories are included and collect byte code files
        extra_contents = {}
        for k in contents:
            if self.collect_py_cache_files and k.endswith(".py"):
                py2_style = False

                for letter in ["c", "o"]:
                    k_opt = k + letter
                    abs_path = self.basedir + os.sep + k_opt
                    if not os.path.isfile(abs_path):
                        continue
                    py2_style = True
                    if (k_opt in contents) or (k_opt in extra_contents):
                        continue
                    extra_contents[k_opt] = BinaryPackage.EntryAttributes({
                        "deftype": "file",
                        "stats":   FileStats.detect_from_filename(abs_path)
                    })
                #end for

                if py2_style:
                    continue

                k_cache_dir = os.path.dirname(k) + os.sep + "__pycache__"
                k_base_name = os.path.basename(k)[0:-3]
                if not os.path.isdir(self.basedir + os.sep + k_cache_dir):
                    continue
                listing = list(Path(self.basedir).glob(
                    k_cache_dir.lstrip(os.sep) + os.sep + k_base_name +
                        ".cpython*.pyc"))
                if not listing:
                    continue

                extra_contents[k_cache_dir] = BinaryPackage.EntryAttributes({
                    "deftype": "dir",
                    "stats":   FileStats.default_dir_stats()
                })

                for path in listing:
                    abs_path = path.as_posix()
                    pkg_path = os.sep + path.relative_to(self.basedir)\
                            .as_posix()
                    if pkg_path in contents:
                        continue
                    extra_contents[pkg_path] = BinaryPackage.EntryAttributes({
                        "deftype": "file",
                        "stats":   FileStats.detect_from_filename(abs_path)
                    })
                #end for
            #end if

            while k != "/" and k != "":
                k = os.path.dirname(k)

                if (k not in contents) and (k not in extra_contents):
                    abs_path = self.basedir + os.sep + k
                    if os.path.exists(abs_path):
                        extra_contents[k] = BinaryPackage.EntryAttributes({
                            "deftype": "dir",
                            "stats": FileStats.detect_from_filename(abs_path)
                        })
                    #end if
                #end if
            #end while
        #end for
        contents.update(extra_contents)

        if self.architecture == "tools":
            # filter out /etc and /var directories, these are shared
            def filter_etc_var(item):
                return False if item[0][0:4] in ["/etc", "/var"] \
                        else True
            #end inline function
            self.contents = OrderedDict(sorted(filter(filter_etc_var,
                set(contents.items())), key=lambda x: x[0]))
        else:
            self.contents = \
                OrderedDict(sorted(set(contents.items()), key=lambda x: x[0]))
        #end if

        # After the filter above: what is not in the package needs no mode.
        self.apply_default_modes(self.contents)

        return self.contents
    #end function

    def strip_debug_symbols_and_unarm_rpath(self):
        objcopy = Platform.find_executable(
            self.host_type + "-objcopy", "objcopy"
        )

        chrpath = Platform.find_executable("chrpath")
        hardlinks = {}
        install_prefix = self.install_prefix.lstrip("/")

        # strip unstripped objects
        for src, attr in self.contents.items():
            if not (attr.stats.is_file and attr.stats.is_elf_binary):
                continue
            if attr.stats.is_stripped:
                continue
            if attr.stats.machine == "no machine":
                continue

            dev = attr.stats.device
            ino = attr.stats.inode

            # no need to strip hardlinked content again
            if hardlinks.setdefault(dev, {}).get(ino):
                continue

            build_id = attr.stats.build_id
            src_path = os.path.normpath(os.sep.join([self.basedir, src]))

            if build_id:
                pkg_path = os.sep + os.path.join(
                    install_prefix, "lib", "debug", ".build-id", build_id[0:2],
                    build_id[2:] + ".debug"
                )
            else:
                pkg_path = os.path.normpath(os.sep + os.sep.join([
                    install_prefix, "lib", "debug", src + ".debug"
                ]))

            dbg_path = os.path.normpath(os.sep.join([self.basedir, pkg_path]))

            hardlinks[dev][ino] = 1
            attr.dbg_info = pkg_path

            os.makedirs(os.path.dirname(dbg_path), exist_ok=True)

            # if u+w bit is missing objcopy will bail out
            if not (attr.stats.mode & stat.S_IWUSR):
                os.chmod(src_path, attr.stats.mode | stat.S_IWUSR)

            # separate debug information
            if build_id:
                cmd_list = [
                    ([objcopy, "--only-keep-debug", src_path, dbg_path], True),
                    ([objcopy, "--strip-unneeded",  src_path          ], True),
                ]
            else:
                dbg_file = os.path.basename(dbg_path)
                cmd_list = [
                    ([objcopy, "--only-keep-debug", src_path, dbg_file], True),
                    ([objcopy, "--strip-unneeded",  src_path          ], True),
                    (
                        [objcopy, "--add-gnu-debuglink", dbg_file, src_path],
                        True
                    ),
                    (["mv", dbg_file, dbg_path], True),
                ]

            for cmd, check_retval in cmd_list:
                subprocess.run(cmd, stderr=subprocess.STDOUT,
                        check=check_retval)

            if not chrpath:
                raise PackagingError(
                    "unable to find the chrpath executable."
                )

            subprocess.run(
                [chrpath, "-c", src_path ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )

            # file size has changed
            attr.stats.restat(src_path)
        #end for
    #end function

    def shlib_deps(self, shlib_cache, bin_pkgs):
        objdump = Platform.find_executable(
            self.host_type + "-objdump", "objdump"
        )

        for src, attr in self.contents.items():
            fallback = None

            if attr.stats.is_symbolic_link and src.endswith(".so"):
                link_target = attr.stats.link_target

                if not os.path.isabs(link_target):
                    link_target = os.path.normpath(os.path.dirname(src) +
                            os.sep + link_target)
                else:
                    fallback = "/usr"
                #end if

                self._find_and_register_dependency(link_target, shlib_cache,
                        bin_pkgs, hard_relation=True, fallback=fallback)
                continue

            if not attr.stats.is_file or not attr.stats.is_elf_binary:
                continue

            abs_path  = os.path.normpath(self.basedir + os.sep + src)
            word_size = attr.stats.arch_word_size
            cmd       = [objdump, "-p", abs_path]

            with subprocess.Popen(cmd, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, universal_newlines=True) as proc:
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        break

                    m = re.match(r"^\s*NEEDED\s+(\S+)", line)
                    if not m:
                        continue
                    lib_name = m.group(1)
                    self._find_and_register_dependency(lib_name, shlib_cache,
                            bin_pkgs, word_size=word_size)
                #end for
            #end with
        #end for
    #end function

    # PRIVATE

    def _find_and_register_dependency(self, lib_name, shlib_cache,
            bin_pkgs, word_size=None, hard_relation=False, fallback=None):
        found  = False
        relation = "=" if hard_relation else ">="

        # in 99% of all cases, we should find the object here
        for shared_obj in shlib_cache.get(lib_name, [], fallback=fallback):
            if word_size and shared_obj.arch_word_size() != word_size:
                continue

            pkg_name, version = shared_obj.package_name_and_version()

            if not pkg_name or not version:
                continue
            if pkg_name == self.name:
                found = True
                break

            if "requires" not in self.relations:
                self.relations["requires"] = \
                        BasePackage.DependencySpecification()

            self.relations["requires"][pkg_name] = BasePackage\
                    .Dependency(pkg_name, "%s %s" % (relation, version))
            found = True
        #end for

        # last resort in case .so is a linker script, for example
        if not found:
            for pkg in bin_pkgs:
                if lib_name not in pkg.contents:
                    continue

                found = True

                if pkg.name != self.name:
                    if "requires" not in self.relations:
                        self.relations["requires"] = \
                                BasePackage.DependencySpecification()
                    self.relations["requires"][pkg_name] = \
                            BasePackage.Dependency(pkg_name, "%s %s" %
                                    (relation, self.version))
                #end if

                break
            #end for
        #end if

        if not found:
            raise UnmetDependency("'%s' dependency '%s' not found in any "
                "installed or built package." % (self.name, lib_name))
    #end function

    def _script_header(self, script_node):
        """The first lines of a maintainer or trigger script. The package
        manager runs a script with the interpreter its first line names.
        A recipe cannot name one freely, it chooses from the ones that are
        there on every system:

        sh:      /bin/sh, the default.
        busybox: The shell of busybox, called through busybox itself. For
                 the scripts that have to work without the link /bin/sh,
                 which are those of busybox.

        The kernel passes what follows the interpreter as one argument,
        so "set -e" is a line of its own."""
        interpreter = script_node.get("interpreter", "sh")

        if interpreter == "sh":
            first_line = "#!/bin/sh"
        elif interpreter == "busybox":
            if self.install_prefix == "/tools":
                first_line = "#!/tools/bin/busybox sh"
            else:
                first_line = "#!/bin/busybox sh"
            #end if
        else:
            raise PackagingError(
                "invalid interpreter '%s' for the %s script of '%s': "
                "must be 'sh' or 'busybox'" %
                    (interpreter, script_node.tag, self.name)
            )
        #end if

        return first_line + "\n" + textwrap.dedent(

                """\

            set -e

            export AELTRA_INSTALL_PREFIX="%s"
            export AELTRA_HOST_TYPE="%s"
            export PATH="%s"

            if [ -d "/tools" ]; then
                export PATH="%s:$PATH"
            fi

            """ % (self.install_prefix, self.host_type,
                   Platform.SYSTEM_PATH, Platform.TOOLS_PATH)

        )
    #end function

    _TRIGGER_PATH_RE = re.compile(
        r'^(/[a-zA-Z0-9_.+\-*?\[\]]+)+$'
    )

    def _validate_trigger_path(self, path):
        if not self._TRIGGER_PATH_RE.match(path):
            raise PackagingError(
                "invalid trigger interest path '%s': must be an absolute "
                "path using only valid path and glob characters" % path
            )
        #end if

        components = path.split('/')
        for comp in components[1:]:
            if comp in ('.', '..'):
                raise PackagingError(
                    "invalid trigger interest path '%s': "
                    "'.' and '..' components are not allowed" % path
                )
            #end if
        #end for

        if '**' in path:
            raise PackagingError(
                "invalid trigger interest path '%s': "
                "'**' is not supported (use '*' instead)" % path
            )
        #end if

        depth = 0
        for ch in path:
            if ch == '[':
                depth += 1
                if depth > 1:
                    raise PackagingError(
                        "invalid trigger interest path '%s': "
                        "nested brackets" % path
                    )
                #end if
            elif ch == ']':
                depth -= 1
                if depth < 0:
                    raise PackagingError(
                        "invalid trigger interest path '%s': "
                        "unmatched ']'" % path
                    )
                #end if
            #end if
        #end for

        if depth != 0:
            raise PackagingError(
                "invalid trigger interest path '%s': unclosed '['" % path
            )
        #end if
    #end function

#end class
