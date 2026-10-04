# -*- encoding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2021 Tobias Koch <tobias.koch@gmail.com>
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

import collections
import json
import logging
import os
import re

from aeltra.miscellaneous.userinfo import UserInfo
from aeltra.distro.config.error import \
        DistroInfoError, ReleaseNotFoundError

LOGGER = logging.getLogger(__name__)

# A package source: its name in aept.conf, the repository and pocket it
# serves, and where.
Source = collections.namedtuple(
    "Source", ["name", "repository", "pocket", "url"]
)

class DistroInfo:

    base_url = "https://archive.aeltra.eu/config/v1"

    # Every pocket a repository can have, in the order sources are listed.
    # A repository has all of them unless releases.json lists its own.
    POCKETS = ["main", "tools", "cross-tools"]

    # Where a pocket lives below <mirror>/<release>/<repository>/<arch>/<libc>.
    POCKET_PATHS = {
        "main":
            "main",
        "tools":
            "tools/{host_arch}",
        "cross-tools":
            "cross-tools/{host_arch}",
    }

    def refresh(self, releases=False, mirrors=False, **kwargs):
        items_to_fetch = []

        if releases:
            items_to_fetch.append("releases")
        if mirrors:
            items_to_fetch.append("mirrors")

        # Imported here, since it brings in urllib, http.client and ssl,
        # which would otherwise slow down every command, even a help text.
        from aeltra.miscellaneous.downloader import Downloader

        os.makedirs(UserInfo.config_folder(), exist_ok=True)
        downloader = Downloader()

        for item in items_to_fetch:
            filename  = "{}.json".format(item)
            src_url   = '/'.join([self.base_url, filename])
            dest_file = os.path.join(UserInfo.config_folder(), filename)

            downloader.download_tagged_file(
                src_url, dest_file, permissions=0o0644
            )
        #end for
    #end function

    def list(
        self,
        supported=False,
        unsupported=False,
        unstable=False,
        **kwargs
    ):
        releases = self._load_json_file("releases")
        result   = []

        for release_name, release_data in releases.items():
            release_data["version_codename"] = release_name

            distro_status = release_data.get("status", "supported")

            is_supported = distro_status == "supported"
            is_unstable  = distro_status == "unstable"

            if (
                (supported and is_supported) or
                (unstable and is_unstable) or
                (unsupported and not (is_supported or is_unstable))
            ):
                result.append(release_data)
        #end for

        result.sort(key=lambda x: float(x.get("version_id", 0)), reverse=True)

        return result
    #end function

    def find(self, release, **kwargs):
        releases = self._load_json_file("releases")

        if release not in releases:
            raise ReleaseNotFoundError(
                "release '{}' not found, need to refresh?".format(release)
            )

        mirrors = self._load_json_file("mirrors")

        for repo_id, repo_dict in \
                releases[release].get("repositories", {}).items():
            repo_mirrors = repo_dict.get("mirrors", [])

            for i in range(len(repo_mirrors)):
                mirror_id = repo_mirrors[i]

                if mirror_id not in mirrors:
                    raise DistroInfoError(
                        "encountered unknown mirror id '{}'."
                        .format(mirror_id)
                    )

                repo_mirrors[i] = mirrors[mirror_id]
            #end for
        #end for

        return releases[release]
    #end function

    def get_git_url_and_ref(self, release, repo_name, **kwargs):
        repo_info = self.find(release).get("repositories", {}).get(repo_name)

        if not repo_info:
            raise DistroInfoError(
                "could not find information for release '{}' and repo '{}'."
                .format(release, repo_name)
            )
        #end if

        rules_url = repo_info.get("rules")
        if not rules_url:
            raise DistroInfoError(
                "could not find package rules for release '{}' and repo '{}'."
                .format(release, repo_name)
            )
        #end if

        m = re.match(
            r"""^
                (?P<url>
                    (?:(?P<proto>[^:]+)://)?
                    (?:[^/@]+@)?
                    (?:[^/@]+/)*
                    (?:[^@]+)
                )
                (?:@(?P<ref>\S+))?
            """,
            rules_url, re.VERBOSE
        )

        return (m.group("url"), m.group("ref") or "master")
    #end function

    def pick_mirror(self, release, repo_name, **kwargs):
        repo_info = self.find(release).get("repositories", {}).get(repo_name)
        if not repo_info:
            raise DistroInfoError(
                "could not find information for release '{}' and repo '{}'."
                .format(release, repo_name)
            )
        #end if

        try:
            return next(iter(repo_info.get("mirrors", [])[0].values()))[0]
        except IndexError:
            raise DistroInfoError(
                "repo '{}' for release '{}' has no mirror information listed."
                .format(repo_name, release)
            )
        #end try
    #end function

    def repository_names(self, release, **kwargs):
        return list(self.find(release).get("repositories", {}).keys())

    def repository_pockets(self, release, repository, **kwargs):
        repo_info = self._repository_info(release, repository)
        return list(repo_info.get("pockets", self.POCKETS))
    #end function

    def repository_sources(self, release, repositories, arch, libc,
            host_arch, pockets, **kwargs):
        """The package sources for the given repositories and pockets,
        named <repository>-<pocket>. A repository that lacks a pocket is
        skipped for it, so a build may ask for every pocket whatever the
        repositories have."""
        for pocket in pockets:
            if pocket not in self.POCKETS:
                raise DistroInfoError("unknown pocket '{}'.".format(pocket))
        #end for

        # In the order sources are listed, whatever the order asked for.
        wanted  = [p for p in self.POCKETS if p in pockets]
        sources = []

        for repository in repositories:
            # Before pick_mirror(): for a repository the release does not
            # have, this one's error lists the repositories it does have.
            repo_pockets = self.repository_pockets(release, repository)
            mirror       = self.pick_mirror(release, repository)

            for pocket in wanted:
                if pocket not in repo_pockets:
                    LOGGER.info(
                        "repository '{}' has no '{}' pocket, skipping."
                        .format(repository, pocket)
                    )
                    continue
                #end if

                url = "/".join([
                    mirror, release, repository, arch, libc,
                    self.POCKET_PATHS[pocket].format(host_arch=host_arch)
                ])
                sources.append(Source(
                    "{}-{}".format(repository, pocket), repository, pocket, url
                ))
            #end for
        #end for

        return sources
    #end function

    # HELPER

    def _repository_info(self, release, repository):
        repositories = self.find(release).get("repositories", {})

        if repository not in repositories:
            raise DistroInfoError(
                "release '{}' has no repository '{}', it has: {}."
                .format(release, repository, ", ".join(repositories))
            )
        #end if

        return repositories[repository]
    #end function

    def _load_json_file(self, which):
        result = collections.OrderedDict()

        json_file = os.path.join(
            UserInfo.config_folder(), "{}.json".format(which)
        )

        if not os.path.exists(json_file):
            self.refresh(**{which: True})

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                result = json.load(
                    f, object_pairs_hook=collections.OrderedDict
                )
            #end with
        except DistroInfoError:
            raise
        except Exception as e:
            raise DistroInfoError(
                "error loading '{}': {}".format(json_file, str(e))
            )

        return result
    #end function

#end class
