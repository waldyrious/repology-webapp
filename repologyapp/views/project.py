# Copyright (C) 2016-2019 Dmitry Marakasov <amdmi3@amdmi3.ru>
#
# This file is part of repology
#
# repology is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# repology is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with repology.  If not, see <http://www.gnu.org/licenses/>.

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from functools import cmp_to_key
from typing import Any, Callable, Collection, Dict, Iterable, List, Optional

import flask

from libversion import version_compare

from repologyapp.afk import AFKChecker
from repologyapp.config import config
from repologyapp.db import get_db
from repologyapp.globals import repometadata
from repologyapp.metapackages import packages_to_summary_items
from repologyapp.package import LinkType, PackageDataDetailed, PackageDataMinimal, PackageDataSummarizable, PackageStatus
from repologyapp.packageproc import packageset_aggregate_by_version, packageset_sort_by_name_version, packageset_sort_by_version
from repologyapp.version import UserVisibleVersionInfo, iter_aggregate_versions
from repologyapp.view_registry import Response, ViewRegistrar


def handle_nonexisting_project(name: str, metapackage: Dict[str, Any]) -> Response:
    # we don't show anything to user when REDIRECTS_PER_PAGE is reached as
    # number of redirect targets is natually limited and we don't expect it to be reached
    redirects = get_db().get_project_redirects(name, limit=config['REDIRECTS_PER_PAGE'])

    if len(redirects) == 1:
        # single redirect - follow it right away
        flask.flash(f'You were redirected from {name}, which was moved or merged here', 'info')
        assert(flask.request.endpoint is not None)
        return flask.redirect(flask.url_for(flask.request.endpoint, name=redirects[0]), 301)

    metapackages: List[Any] = []
    metapackagedata: Dict[str, Any] = {}

    if redirects:
        # show redirects
        metapackages = get_db().get_metapackages(redirects)

        metapackagedata = packages_to_summary_items(
            PackageDataSummarizable(**item)
            for item in get_db().get_metapackages_packages(redirects, summarizable=True)
        )

    if not metapackage:
        return (
            flask.render_template(
                'project-404.html',
                name=name,
                metapackages=metapackages,
                metapackagedata=metapackagedata
            ),
            404
        )
    else:
        return (
            flask.render_template(
                'project-410.html',
                name=name,
                metapackage=metapackage,
                metapackages=metapackages,
                metapackagedata=metapackagedata,
                **get_db().get_project_leftovers_summary(name)
            ),
            404
        )


@ViewRegistrar('/project/<name>/versions')
def project_versions(name: str) -> Response:
    metapackage = get_db().get_metapackage(name)

    if not metapackage or metapackage['num_repos'] == 0:
        return handle_nonexisting_project(name, metapackage)

    packages = [
        PackageDataDetailed(**item)
        for item in get_db().get_metapackage_packages(name, detailed=True, url=True)
    ]

    packages_by_repo: Dict[str, List[PackageDataDetailed]] = defaultdict(list)
    for package in packages:
        packages_by_repo[package.repo].append(package)

    for repo, repo_packages in packages_by_repo.items():
        packages_by_repo[repo] = packageset_sort_by_version(repo_packages)

    return flask.render_template(
        'project-versions.html',
        name=name,
        metapackage=metapackage,
        packages=packages,
        packages_by_repo=packages_by_repo,
        reponames_absent=[reponame for reponame in repometadata.active_names() if reponame not in packages_by_repo]
    )


@ViewRegistrar('/project/<name>/versions-compact')
def project_versions_compact(name: str) -> Response:
    metapackage = get_db().get_metapackage(name)

    if not metapackage or metapackage['num_repos'] == 0:
        return handle_nonexisting_project(name, metapackage)

    packages = [
        PackageDataMinimal(**item)
        for item in get_db().get_metapackage_packages(name, minimal=True)
    ]

    packages_by_repo: Dict[str, List[PackageDataMinimal]] = defaultdict(list)
    for package in packages:
        packages_by_repo[package.repo].append(package)

    versions: Dict[str, List[UserVisibleVersionInfo]] = {
        repo: sorted(iter_aggregate_versions(repo_packages), reverse=True)
        for repo, repo_packages in packages_by_repo.items()
    }

    return flask.render_template(
        'project-versions-compact.html',
        name=name,
        metapackage=metapackage,
        packages=packages,
        versions=versions,
    )


@ViewRegistrar('/project/<name>/packages')
def project_packages(name: str) -> Response:
    metapackage = get_db().get_metapackage(name)

    if not metapackage or metapackage['num_repos'] == 0:
        return handle_nonexisting_project(name, metapackage)

    packages_by_repo: Dict[str, List[PackageDataDetailed]] = defaultdict(list)
    for package in (PackageDataDetailed(**item) for item in get_db().get_metapackage_packages(name, detailed=True)):
        packages_by_repo[package.repo].append(package)

    packages: List[PackageDataDetailed] = []
    for repo in repometadata.active_names():
        if repo in packages_by_repo:
            packages.extend(packageset_sort_by_name_version(packages_by_repo[repo]))

    return flask.render_template(
        'project-packages.html',
        name=name,
        metapackage=metapackage,
        packages=packages,
        links=get_db().get_project_links(name)
    )


@ViewRegistrar('/project/<name>/information')
def project_information(name: str) -> Response:
    metapackage = get_db().get_metapackage(name)

    if not metapackage or metapackage['num_repos'] == 0:
        return handle_nonexisting_project(name, metapackage)

    packages = sorted(
        (
            PackageDataDetailed(**item)
            for item in get_db().get_metapackage_packages(name, detailed=True)
        ),
        key=lambda package: package.repo + package.visiblename + package.version
    )

    information: Dict[str, Any] = {}

    def append_info(infokey: str, infoval: Any, package: PackageDataDetailed) -> None:
        if infokey not in information:
            information[infokey] = {}

        if infoval not in information[infokey]:
            information[infokey][infoval] = set()

        information[infokey][infoval].add(package.family)

    for package in packages:
        append_info('names', package.visiblename, package)
        append_info('versions', package.version, package)
        append_info('repos', package.repo, package)

        if package.comment:
            append_info('summaries', package.comment, package)
        if package.maintainers is not None:
            for maintainer in package.maintainers:
                append_info('maintainers', maintainer, package)
        if package.category:
            append_info('categories', package.category, package)
        if package.licenses is not None:
            for license_ in package.licenses:
                append_info('licenses', license_, package)
        if package.links is not None:
            maybe_raw_links = defaultdict(list)
            for link_type, link_id in package.links:
                if link_type in [LinkType.UPSTREAM_HOMEPAGE, LinkType.PROJECT_HOMEPAGE]:
                    append_info('homepages', link_id, package)
                elif link_type in [LinkType.UPSTREAM_DOWNLOAD, LinkType.PROJECT_DOWNLOAD]:
                    append_info('downloads', link_id, package)
                elif link_type == LinkType.UPSTREAM_ISSUE_TRACKER:
                    append_info('issues', link_id, package)
                elif link_type == LinkType.UPSTREAM_REPOSITORY:
                    append_info('repositories', link_id, package)
                elif link_type == LinkType.UPSTREAM_DOCUMENTATION:
                    append_info('documentation', link_id, package)
                elif link_type == LinkType.PACKAGE_HOMEPAGE:
                    append_info('packages', link_id, package)
                elif link_type == LinkType.PACKAGE_RECIPE:
                    maybe_raw_links['recipes'].append(link_id)
                elif link_type == LinkType.PACKAGE_RECIPE_RAW:
                    maybe_raw_links['recipes_raw'].append(link_id)
                elif link_type == LinkType.PACKAGE_PATCH:
                    maybe_raw_links['patches'].append(link_id)
                elif link_type == LinkType.PACKAGE_PATCH_RAW:
                    maybe_raw_links['patches_raw'].append(link_id)
                elif link_type == LinkType.PACKAGE_BUILD_LOG:
                    maybe_raw_links['buildlogs'].append(link_id)
                elif link_type == LinkType.PACKAGE_BUILD_LOG_RAW:
                    maybe_raw_links['buildlogs_raw'].append(link_id)

            # for links which may have both human-readlabe and raw flavors, we
            # prefer human-readable ones here
            for key in ['recipes', 'patches', 'buildlogs']:
                if key in maybe_raw_links:
                    for link_id in maybe_raw_links[key]:
                        append_info(key, link_id, package)
                elif key + '_raw' in maybe_raw_links:
                    for link_id in maybe_raw_links[key + '_raw']:
                        append_info(key, link_id, package)

    if 'repos' in information:
        # preserve repos order
        information['repos'] = [
            (reponame, information['repos'][reponame])
            for reponame in repometadata.active_names() if reponame in information['repos']
        ]

    versions = packageset_aggregate_by_version(packages, {PackageStatus.LEGACY: PackageStatus.OUTDATED})

    links = get_db().get_project_links(name)

    for key in ['homepages', 'downloads', 'issues', 'repositories', 'patches', 'buildlogs', 'documentation', 'recipes']:
        if key in information:
            information[key] = sorted(
                information[key].items(),
                key=lambda l: links[l[0]]['url'].lower()  # type: ignore
            )

    return flask.render_template(
        'project-information.html',
        name=name,
        metapackage=metapackage,
        information=information,
        versions=versions,
        links=links
    )


@ViewRegistrar('/project/<name>/history')
def project_history(name: str) -> Response:
    def prepare_repos(repos: Collection[str]) -> List[str]:
        if not repos:
            return []

        repos = set(repos)

        # ensure correct ordering
        return [name for name in repometadata.all_names() if name in repos]

    def prepare_versions(versions: List[str]) -> List[str]:
        if not versions:
            return []

        return sorted(versions, key=cmp_to_key(version_compare), reverse=True)

    def timedelta_from_seconds(seconds: int) -> timedelta:
        return timedelta(seconds=seconds)

    def apply_to_field(datadict: Dict[str, Any], key: str, func: Callable[..., Any]) -> None:
        if key in datadict and datadict[key] is not None:
            datadict[key] = func(datadict[key])

    def postprocess_history(history: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        for entry in history:
            data = entry['data']

            if entry['type'] == 'history_start':
                devel_repos = set(data.get('devel_repos', []))
                newest_repos = set(data.get('newest_repos', []))
                all_repos = set(data.get('all_repos', []))

                actual_repos = devel_repos | newest_repos
                old_repos = all_repos - actual_repos

                apply_to_field(data, 'devel_versions', prepare_versions)
                apply_to_field(data, 'newest_versions', prepare_versions)

                data['devel_repos'] = prepare_repos(devel_repos)
                data['newest_repos'] = prepare_repos(newest_repos)
                data['all_repos'] = prepare_repos(all_repos)

                data['actual_repos'] = prepare_repos(actual_repos)
                data['old_repos'] = prepare_repos(old_repos)

                yield entry

            elif entry['type'] == 'version_update':
                apply_to_field(data, 'versions', prepare_versions)
                apply_to_field(data, 'repos', prepare_repos)
                apply_to_field(data, 'passed', timedelta_from_seconds)
                yield entry

            elif entry['type'] == 'catch_up':
                apply_to_field(data, 'repos', prepare_repos)
                apply_to_field(data, 'lag', timedelta_from_seconds)

                if data['repos']:
                    yield entry

            elif entry['type'] == 'repos_update':
                apply_to_field(data, 'repos_added', prepare_repos)
                apply_to_field(data, 'repos_removed', prepare_repos)

                if data['repos_added'] or data['repos_removed']:
                    yield entry

            elif entry['type'] == 'history_end':
                apply_to_field(data, 'last_repos', prepare_repos)
                if data.get('last_repos'):
                    data['last_repo'] = data['last_repos'][0]

                yield entry

    autorefresh = flask.request.args.to_dict().get('autorefresh')

    metapackage = get_db().get_metapackage(name)

    history = list(postprocess_history(get_db().get_metapackage_history(name, limit=config['HISTORY_PER_PAGE'])))

    if (not metapackage or metapackage['num_repos'] == 0) and not history:  # treat specially: allow showing history even for nonexisting projects
        return handle_nonexisting_project(name, metapackage)

    return flask.render_template(
        'project-history.html',
        name=name,
        metapackage=metapackage,
        history=history,
        autorefresh=autorefresh
    )


@ViewRegistrar('/project/<name>/related')
def project_related(name: str) -> Response:
    metapackage = get_db().get_metapackage(name)

    if not metapackage or metapackage['num_repos'] == 0:
        return handle_nonexisting_project(name, metapackage)

    metapackages = get_db().get_project_related_projects(name, limit=config['METAPACKAGES_PER_PAGE'])

    metapackagedata = packages_to_summary_items(
        PackageDataSummarizable(**item)
        for item in get_db().get_metapackages_packages(list(metapackages.keys()), summarizable=True)
    )

    too_many_warning = None
    if len(metapackagedata) == config['METAPACKAGES_PER_PAGE']:
        too_many_warning = config['METAPACKAGES_PER_PAGE']

    return (
        flask.render_template(
            'project-related.html',
            name=name,
            metapackage=metapackage,
            metapackages=metapackages,
            metapackagedata=metapackagedata,
            too_many_warning=too_many_warning
        ),
        200 if metapackages else 404
    )


@ViewRegistrar('/project/<name>/badges')
def project_badges(name: str) -> Response:
    metapackage = get_db().get_metapackage(name)

    if not metapackage or metapackage['num_repos'] == 0:
        return handle_nonexisting_project(name, metapackage)

    repos_present_in = set(
        package['repo']
        for package in get_db().get_metapackage_packages(name, fields=['repo'])
    )
    repos = [repo for repo in repometadata.active_names() if repo in repos_present_in]

    return flask.render_template(
        'project-badges.html',
        name=name,
        metapackage=metapackage,
        repos=repos
    )


@ViewRegistrar('/project/<name>/report', methods=['GET', 'POST'])
def project_report(name: str) -> Response:
    metapackage = get_db().get_metapackage(name)

    reports = get_db().get_metapackage_reports(name)

    if (not metapackage or metapackage['num_repos'] == 0) and not reports:  # treat specially: allow showing reports even for nonexisting projects
        return handle_nonexisting_project(name, metapackage)

    reports_disabled = name in config['DISABLED_REPORTS']

    need_verignore = False
    need_split = False
    need_merge = False
    need_vuln = False
    comment = None
    errors = []

    if flask.request.method == 'POST':
        if reports_disabled:
            errors.append('Could not add report: new reports for this metapackage are disabled')

        if get_db().get_metapackage_reports_count(name) >= config['MAX_REPORTS']:
            errors.append('Could not add report: too many reports for this metapackage')

        need_verignore = 'need_verignore' in flask.request.form
        need_split = 'need_split' in flask.request.form
        need_merge = 'need_merge' in flask.request.form
        need_vuln = 'need_vuln' in flask.request.form
        comment = flask.request.form.get('comment', '').strip().replace('\r', '') or None

        if comment and len(comment) > 10240:
            errors.append('Could not add report: comment is too long')

        if not need_verignore and not need_split and not need_merge and not need_vuln and not comment:
            errors.append('Could not add report: please fill out the form')

        if comment and '<a href' in comment:
            errors.append('Spammers not welcome, HTML not allowed')

        if not errors:
            get_db().add_report(
                name,
                need_verignore,
                need_split,
                need_merge,
                need_vuln,
                comment
            )

            flask.flash('Report for {} added successfully and will be processed in a few days, thank you!'.format(name), 'success')
            return flask.redirect(flask.url_for('metapackage_report', name=name))

    return flask.render_template(
        'project-report.html',
        name=name,
        metapackage=metapackage,
        reports=reports,
        afk_till=AFKChecker(config['STAFF_AFK']).get_afk_end(),
        reports_disabled=reports_disabled,
        need_verignore=need_verignore,
        need_split=need_split,
        need_merge=need_merge,
        need_vuln=need_vuln,
        comment=comment,
        messages=[('danger', error) for error in errors]
    )


@dataclass
class _VersionRange:
    start: Optional[str]
    end: Optional[str]
    start_excluded: bool
    end_excluded: bool
    highlighted: bool = False

    def set_highlight(self, version: Optional[str]) -> '_VersionRange':
        if version is None:
            return self
        if self.start is not None and version_compare(version, self.start) < (1 if self.start_excluded else 0):
            return self
        if self.end is not None and version_compare(version, self.end) > (-1 if self.end_excluded else 0):
            return self

        self.highlighted = True

        return self


@dataclass(unsafe_hash=True)
class _CVEAggregation:
    cve_id: str
    published: str
    last_modified: str
    cpe_vendor: str
    cpe_product: str
    cpe_edition: str
    cpe_lang: str
    cpe_sw_edition: str
    cpe_target_sw: str
    cpe_target_hw: str
    cpe_other: str


@ViewRegistrar('/project/<name>/cves')
def project_cves(name: str) -> Response:
    metapackage = get_db().get_metapackage(name)

    highlight_version = flask.request.args.to_dict().get('version')

    cve_ids = set()
    cves: Dict[_CVEAggregation, List[_VersionRange]] = defaultdict(list)
    for item in get_db().get_project_cves(name, config['CVES_PER_PAGE']):
        cve_ids.add(item[0])
        cves[
            _CVEAggregation(
                *item[0:11]
            )
        ].append(
            _VersionRange(
                *item[11:15]
            ).set_highlight(highlight_version)
        )

    too_many = len(cve_ids) >= config['CVES_PER_PAGE']

    if (not metapackage or metapackage['num_repos'] == 0) and not cves:  # treat specially: allow showing CVEs even for nonexisting projects
        return handle_nonexisting_project(name, metapackage)

    return flask.render_template(
        'project-cves.html',
        name=name,
        metapackage=metapackage,
        highlight_version=highlight_version,
        cves=list(cves.items()),
        too_many_warning=config['CVES_PER_PAGE'] if too_many else None
    )
