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

import copy
import logging
import os
import re
import shutil

from aeltra.error import UnmetDependency, InvocationError, \
        PackagingError, SkipBuild

from aeltra.miscellaneous.platform import Platform
from aeltra.miscellaneous.userinfo import UserInfo

from aeltra.package.aeltrapack.basepackage import BasePackage
from aeltra.package.aeltrapack.changelog import Changelog
from aeltra.package.aeltrapack.debianpackage import DebianPackage
from aeltra.package.aeltrapack.packagedesc import PackageDescription
from aeltra.package.aeltrapack.shlibcache import ShlibCache
from aeltra.package.aeltrapack.sourcecache import SourceCache
from aeltra.package.aeltrapack.sourcepackage import SourcePackage
from aeltra.package.aeltrapack.specfile import Specfile

LOGGER = logging.getLogger(__name__)

class PackageControl:

    # Actions that don't produce any part of the package and therefore neither
    # honour the skip marker nor require the build dependencies to be present.
    NO_BUILD_ACTIONS = {"list_deps", "mk_build_deps", "unpack", "clean"}

    # Actions that must not run for a package marked to be skipped, but that
    # don't touch the build dependencies either.
    NO_DEPS_ACTIONS = {"fetch_sources"}

    def __init__(self, filename, cache_dir=None, **kwargs):
        self.parms = {
            "arch":
                Platform.target_machine(),
            "build_for":
                "target",
            "copy_archives":
                True,
            "debug_pkgs":
                True,
            "disable_packages":
                [],
            "enable_packages":
                [],
            "force_local":
                False,
            "ignore_deps":
                False,
            "libc_name":
                Platform.libc_name(),
            "outdir":
                None,
            "tools_arch":
                Platform.tools_machine()
        }
        self.parms.update(kwargs)

        build_for = self.parms["build_for"]
        pkg_arch  = self.parms["arch"] if build_for == "target" \
                        else self.parms["tools_arch"]

        specfile = Specfile(filename)
        specfile.validate()

        xml_doc = specfile.xml_doc

        if self.parms["enable_packages"]:
            for p in self.parms["enable_packages"]:
                if not xml_doc.xpath("/control/package[@name='%s']" % p):
                    raise InvocationError("unknown binary package '%s'." % p)
            #end for
        #end if

        if self.parms["disable_packages"]:
            for p in self.parms["disable_packages"]:
                if not xml_doc.xpath("/control/package[@name='%s']" % p):
                    raise InvocationError("unknown binary package '%s'." % p)
            #end for
        #end if

        specfile.preprocess(
            true_terms=[
                # Example: "target-build", "tools-x86_64", "riscv64", "glibc"
                "{}-build".format(build_for),
                "tools-{}".format(self.parms["tools_arch"]),
                self.parms["arch"],
                self.parms["libc_name"]
            ]
        )

        if not cache_dir:
            cache_dir = UserInfo.cache_dir()

        self._cache_dir = cache_dir

        # copy maintainer, email, version, revision to package sections
        for attr_name in ["maintainer", "email", "epoch",
                "version", "revision", "date"]:
            xpath = "/control/changelog/release[1]/@%s" % attr_name
            try:
                attr_val = xml_doc.xpath(xpath)[0]
            except IndexError:
                continue
            xpath = "/control/*[name() = 'source' or name() = 'package']"
            for pkg_node in xml_doc.xpath(xpath):
                pkg_node.attrib[attr_name] = attr_val
        #end for

        xpath = "/control/source/@name"
        source_name = xml_doc.xpath(xpath)[0]

        xpath = "/control/source/@repo"
        repo_name = xml_doc.xpath(xpath)[0]

        xpath = "/control/source/@architecture-independent"
        try:
            is_arch_indep = xml_doc.xpath(xpath)[0].lower()
        except IndexError:
            is_arch_indep = "false"
        #end try

        if build_for in ["tools", "cross-tools"]:
            architecture = "tools"
        elif is_arch_indep.lower() == "true":
            architecture = "all"
        else:
            architecture = pkg_arch

        for pkg_node in xml_doc.xpath(
                "/control/*[name() = 'source' or name() = 'package']"):
            pkg_node.attrib["source"] = source_name

            if pkg_node.tag != "source":
                pkg_node.attrib["repo"] = repo_name

            pkg_node.attrib["architecture"] = architecture
        #end for

        xml_doc.xpath("/control/changelog")[0].attrib["source"] = source_name

        self.defines = {
            "AELTRA_SOURCE_DIR": "sources",
            "AELTRA_BUILD_DIR": "sources",
            "AELTRA_INSTALL_DIR": "install",
            "AELTRA_WORK_DIR": os.getcwd(),
            "AELTRA_BUILD_TYPE": Platform.target_type(),
            "AELTRA_TOOLS_TYPE": Platform.tools_type(),
            "AELTRA_BUILD_FOR": build_for,
            "AELTRA_LIBC_NAME": self.parms["libc_name"]
        }

        if build_for == "tools":
            self.defines["AELTRA_HOST_TYPE"] = Platform.tools_type()
            self.defines["AELTRA_TARGET_TYPE"] = Platform.tools_type()
            self.defines["AELTRA_INSTALL_PREFIX"] = "/tools"
        elif build_for == "cross-tools":
            self.defines["AELTRA_HOST_TYPE"] = Platform.tools_type()
            self.defines["AELTRA_TARGET_TYPE"] = Platform.target_type()
            self.defines["AELTRA_INSTALL_PREFIX"] = "/tools"
        else:
            self.defines["AELTRA_HOST_TYPE"] = Platform.target_type()
            self.defines["AELTRA_TARGET_TYPE"] = Platform.target_type()
            self.defines["AELTRA_INSTALL_PREFIX"] = "/usr"
        #end if

        for node in xml_doc.xpath("/control/defines/def"):
            self.defines[node.get("name")] = node.get("value", "")

        # these *must* be absolute paths
        for s in ["SOURCE", "BUILD", "INSTALL"]:
            if os.path.isabs(self.defines["AELTRA_%s_DIR" % s]):
                self.defines["AELTRA_%s_DIR" % s] = os.path.realpath(
                        self.defines["AELTRA_%s_DIR" % s])
            else:
                self.defines["AELTRA_%s_DIR" % s] = os.path.realpath(
                    os.sep.join([self.defines["AELTRA_WORK_DIR"],
                        self.defines["AELTRA_%s_DIR" % s]])
                )
            #end if
        #end for

        source_pkg_node = xml_doc.xpath("/control/source")[0]

        self.src_pkg = SourcePackage(
            copy.deepcopy(source_pkg_node),
            copy_archives=self.parms["copy_archives"],
            build_for=build_for
        )
        self.src_pkg.basedir = os.path.realpath(os.path.dirname(filename))

        self.bin_pkgs = []

        if self.parms.get("action") == "would_build":
            pass
        elif self.parms.get("action") == "mk_build_deps":
            pkg = DebianPackage(
                copy.deepcopy(source_pkg_node),
                debug_pkgs=False,
                install_prefix=self.defines["AELTRA_INSTALL_PREFIX"],
                host_type=self.defines["AELTRA_HOST_TYPE"],
                build_for=build_for
            )

            pkg.name        += "-build-deps"
            pkg.architecture = "all"
            pkg.maintainer   = "Package Control"
            pkg.source       = "no-source"
            pkg.section      = "devel"
            pkg.description  = PackageDescription(
                """
                <description>
                    <summary>Build dependencies for {name} {version}</summary>
                    <p>
                    Install this package to pull in all build dependencies
                    required to build "{name}" version "{version}" for "{arch}".
                    </p>
                </description>
                """  # noqa
                .format(
                    name=self.src_pkg.name,
                    version=pkg.version,
                    arch=architecture
                )
            )

            # The source package duplicates all dependencies, requiring them
            # once for tools and once for target.
            pkg.relations["requires"] = self.src_pkg.relations["requires"]

            self.bin_pkgs.append(pkg)
        else:
            for node in xml_doc.xpath("/control/package"):
                pkg = DebianPackage(
                    node,
                    debug_pkgs=self.parms["debug_pkgs"],
                    install_prefix=self.defines["AELTRA_INSTALL_PREFIX"],
                    host_type=self.defines["AELTRA_HOST_TYPE"],
                    target_type=self.defines["AELTRA_TARGET_TYPE"],
                    parallel_jobs=Platform.parallel_jobs(
                        self.defines.get("AELTRA_PARALLEL_JOBS")
                    ),
                    build_for=build_for
                )

                if self.parms["enable_packages"]:
                    if pkg.name not in self.parms["enable_packages"]:
                        continue
                if self.parms["disable_packages"]:
                    if pkg.name in self.parms["disable_packages"]:
                        continue

                pkg.basedir = self.defines["AELTRA_INSTALL_DIR"]

                if self.parms.get("outdir"):
                    pkg.output_dir = os.path.realpath(self.parms["outdir"])

                self.bin_pkgs.append(pkg)
            #end for
        #end if

        for pkg in self.bin_pkgs:
            if build_for == "tools":
                pkg.name = "tools-" + pkg.name
            elif build_for == "cross-tools":
                pkg.name = "tools-target-" + pkg.name
            #end if
        #end function

        self.changelog = Changelog(xml_doc.xpath('/control/changelog')[0])
    #end function

    def __call__(self, action):
        if action not in self.NO_BUILD_ACTIONS:
            if self.src_pkg.skip:
                raise SkipBuild(
                    'package is marked to be skipped unless "{}".'
                    .format(self.src_pkg.skip)
                )
            #end if

            # Nothing else to do, we return and the app exits with 0, now.
            if action == "would_build":
                return

            if action not in self.NO_DEPS_ACTIONS and \
                    not self.parms.get("ignore_deps"):
                missing_deps = self._missing_build_dependencies()
                if missing_deps.list:
                    msg = "missing dependencies: {}".format(missing_deps)
                    raise UnmetDependency(msg)
                #end if
            #end if
        #end if

        getattr(self, action)()
    #end function

    def mk_build_deps(self):
        pkg = self.bin_pkgs[0]
        pkg.do_pack()

        aeltra_build_deps_symlink = "aeltra-build-deps.aeltra"

        if os.path.islink(aeltra_build_deps_symlink):
            os.unlink(aeltra_build_deps_symlink)
        if os.path.exists(aeltra_build_deps_symlink):
            return

        try:
            os.symlink(pkg.pkg_filename(), aeltra_build_deps_symlink)
        except OSError:
            pass
    #end function

    def list_deps(self):
        print(self.src_pkg.build_dependencies())

    def fetch_sources(self):
        self.src_pkg.fetch_sources(source_cache=self._source_cache())

    def unpack(self):
        directory = self.defines["AELTRA_WORK_DIR"]
        if not os.path.exists(directory):
            os.makedirs(directory)

        self.src_pkg \
            .unpack(directory, source_cache=self._source_cache()) \
            .patch(directory)
    #end function

    def prepare(self):
        directory = self.defines["AELTRA_BUILD_DIR"]
        if not os.path.exists(directory):
            os.makedirs(directory)
        self.src_pkg.run_action("prepare", self.defines)
    #end function

    def build(self):
        directory = self.defines["AELTRA_BUILD_DIR"]
        if not os.path.exists(directory):
            os.makedirs(directory)
        self.src_pkg.run_action("build", self.defines)
    #end function

    def install(self):
        install_dir = self.defines["AELTRA_INSTALL_DIR"]

        if os.path.exists(install_dir):
            shutil.rmtree(install_dir)
        os.makedirs(install_dir)

        self.src_pkg.run_action("install", self.defines)
    #end function

    def package(self):
        shlib_cache = ShlibCache(prefix=self.defines["AELTRA_INSTALL_PREFIX"])
        for pkg in self.bin_pkgs:
            pkg.prepare()
        for pkg in self.bin_pkgs:
            pkg.strip_debug_symbols_and_unarm_rpath()
            pkg.strip_static_libraries()
        for pkg in self.bin_pkgs:
            shlib_cache.overlay_package(pkg)
        for pkg in self.bin_pkgs:
            pkg.find_tools_interpreters()

        try:
            for pkg in self.bin_pkgs:
                pkg.shlib_deps(shlib_cache, self.bin_pkgs)
        finally:
            # also what was found before a dependency was not
            self._report_tools_references()

        if any(pkg.tools_references for pkg in self.bin_pkgs):
            raise PackagingError("packages for the target need the tools.")

        for path in self.build_references():
            LOGGER.warning("'%s' has the folder of the build in it." % path)

        for pkg in self.bin_pkgs:
            pkg.do_pack()

        # Some files have no package on purpose if not all are built.
        if not self.parms["enable_packages"] and \
                not self.parms["disable_packages"]:
            for path in self.unclaimed_files():
                LOGGER.warning(
                    "'%s' was installed but is in no package." % path
                )
            #end for

            for src, target in self.dangling_links():
                LOGGER.warning(
                    "'%s' is a link to '%s', which is in no package." %
                    (src, target)
                )
            #end for
        #end if
    #end function

    def build_references(self):
        """Return the text files in the binary packages that mention the
        folder of the build."""
        work = re.escape(self.defines["AELTRA_WORK_DIR"].encode())
        # not /work/pkg-10 if the folder is /work/pkg-1
        regexp = re.compile(work + rb"(?![\w+~-])")
        result = []

        for pkg in self.bin_pkgs:
            for src, attr in pkg.contents.items():
                if not attr.stats.is_file:
                    continue

                abs_path = os.path.normpath(pkg.basedir + os.sep + src)

                with open(abs_path, "rb") as f:
                    content = f.read()

                if b"\0" not in content and regexp.search(content):
                    result.append(src)
            #end for
        #end for

        return result
    #end function

    def dangling_links(self):
        """Return the symbolic links that lead to nothing in any of the
        binary packages, as pairs of the link and its target. Links of
        libraries are checked by shlib_deps(), and those out of the prefix
        may well lead to a file of another package."""
        prefix = self.defines["AELTRA_INSTALL_PREFIX"] + os.sep
        work   = self.defines["AELTRA_WORK_DIR"] + os.sep
        result = []

        contents = set()
        for pkg in self.bin_pkgs:
            contents.update(
                os.sep + os.path.normpath(src).lstrip(os.sep)
                for src in pkg.contents
            )

        for pkg in self.bin_pkgs:
            for src, attr in pkg.contents.items():
                if not attr.stats.is_symbolic_link or src.endswith(".so"):
                    continue

                target = attr.stats.link_target

                if os.path.isabs(target):
                    # into the folder of the build, which is never right
                    dangling = target.startswith(work)
                else:
                    path = os.path.normpath(
                        os.path.join(os.path.dirname(src), target)
                    )
                    dangling = path.startswith(prefix) and \
                        path not in contents
                #end if

                if dangling:
                    result.append((src, target))
            #end for
        #end for

        return result
    #end function

    # Files that packages are not expected to have: documentation,
    # libtool archives, compiled Python files (they come with their
    # source) and what Perl writes down about an installation.
    UNCLAIMED_IGNORE = re.compile(
        r"/share/(doc|gtk-doc|help|info|man)/"
        r"|\.la$"
        r"|/__pycache__/"
        r"|/perllocal\.pod$|/\.packlist$"
    )

    # A folder with more unclaimed entries than this is reported in place of
    # them, see unclaimed_files().
    UNCLAIMED_MANY = 5

    def unclaimed_files(self):
        """Return what is in the install folder but in none of the binary
        packages, as paths below the install folder. A folder of which
        nothing is packaged is returned in place of its files, with a
        slash at the end, if these would be many."""
        install_dir = self.defines["AELTRA_INSTALL_DIR"]

        claimed = set()
        for pkg in self.bin_pkgs:
            for src in pkg.contents:
                claimed.add(os.sep + os.path.normpath(src).lstrip(os.sep))

        # It is the path in a package that counts: a recipe may copy files to
        # the folders of packages, which are folders of the install folder,
        # or install variants of which a file is only needed once.
        def is_claimed(rel_path):
            parts = rel_path.split(os.sep)
            return any(
                os.sep + os.sep.join(parts[i:]) in claimed
                for i in range(1, len(parts))
            )
        #end inline function

        # The folders for debug information are made while packaging.
        debug_dir = os.sep.join(
            [self.defines["AELTRA_INSTALL_PREFIX"], "lib", "debug", ""]
        )

        def collect(directory):
            """Return what is unclaimed in the directory, and whether
            anything at all in it is claimed."""
            result, any_claimed = [], False

            for entry in sorted(os.scandir(directory), key=lambda e: e.name):
                rel_path = entry.path[len(install_dir):]

                if entry.is_dir(follow_symlinks=False):
                    if debug_dir in rel_path + os.sep:
                        continue

                    sub_result, sub_claimed = collect(entry.path)

                    if not sub_claimed and \
                            len(sub_result) > self.UNCLAIMED_MANY:
                        sub_result = [rel_path + os.sep]

                    any_claimed = any_claimed or sub_claimed
                    result += sub_result
                elif is_claimed(rel_path):
                    any_claimed = True
                elif self.UNCLAIMED_IGNORE.search(rel_path):
                    pass
                elif self.defines["AELTRA_INSTALL_PREFIX"] == "/tools" and \
                        re.search(r"^(/[^/]+)?/(etc|var)/", rel_path):
                    # shared with the target, see generate_file_list()
                    pass
                else:
                    result.append(rel_path)
                #end if
            #end for

            return result, any_claimed
        #end inline function

        return collect(install_dir)[0]
    #end function

    def repackage(self):
        self.install()
        self.package()
    #end function

    def clean(self):
        self.src_pkg.run_action("clean", self.defines)

    def default(self):
        self.unpack()
        self.prepare()
        self.build()
        self.install()
        self.package()
    #end function

    # PRIVATE

    def _report_tools_references(self):
        """All of them are reported before the build is stopped."""
        for pkg in self.bin_pkgs:
            for msg in pkg.tools_references:
                LOGGER.error(msg)
    #end function

    def _source_cache(self):
        return SourceCache(self._cache_dir, self.parms["release"],
                force_local=self.parms["force_local"])

    def _missing_build_dependencies(self):
        unfulfilled_dependency_spec = BasePackage.DependencySpecification()

        for alternatives in self.src_pkg.relations["requires"].list:
            fulfilled = False

            for dep in alternatives:
                if dep.is_fulfilled:
                    fulfilled = True
                    break
            #end for

            if not fulfilled:
                for dep in alternatives:
                    unfulfilled_dependency_spec.index[dep.name] = dep
                unfulfilled_dependency_spec.list.append(alternatives)
            #end if
        #end for

        return unfulfilled_dependency_spec
    #end function

#end class
