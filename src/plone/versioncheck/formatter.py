# -*- coding: utf-8 -*-
from __future__ import print_function
from collections import OrderedDict
from plone.versioncheck import analyser
from plone.versioncheck.utils import color_by_state
from plone.versioncheck.utils import color_init
from plone.versioncheck.utils import dots
import json
import sys
import textwrap


def build_version(
    name,
    pkg,
    pypi,
    tracked,
    key,
    idx,
    flavor='versions',
):
    record = {}
    if flavor == 'versions':
        record['version'] = pkg[key] or "(unset)"
        record['description'] = key
        if idx == 0:
            record['state'] = 'I' if tracked and tracked[1] else 'A'
        elif analyser.is_cfgidx_newer(pkg, idx):
            record['state'] = 'In'
        else:
            record['state'] = 'I'
    else:  # pypi
        if 'pre' in key:
            record['state'] = 'P'
        else:
            record['state'] = 'U'
        record['version'] = pypi[key]
        record['description'] = key.capitalize()
    return record


def builder(pkgsinfo, newer_only=False, limit=None):
    """build
    - OrderedDict with pkgname as keys
    - each entry an record:
      - state: overall package state
      - versions: list of dicts with
        - version number
        - state
        - description
    """
    result = OrderedDict()
    ver_maxlen = 0
    pkgs = pkgsinfo['pkgs']
    pypi = pkgsinfo.get('pypi', {})
    tracked = pkgsinfo.get('tracking', {}).get('versions', {})
    requ = pkgsinfo.get('tracking', {}).get('required_by', {})

    names = sorted(set(tracked.keys()) | set(pkgs.keys()))

    for nidx, name in enumerate(names):
        current_pkg = pkgs.get(name, {})
        record = dict()
        versions = record['versions'] = list()
        unpinned = False
        required_by = requ.get(name, None)
        if required_by:
            record['required_by'] = required_by

        # handle dev-eggs
        devegg = False
        current_tracked = tracked.get(name, None)
        if current_tracked is not None:
            ver_maxlen = max([ver_maxlen, len(current_tracked[0])])
            if current_tracked[1]:
                versions.append({
                    'version': current_tracked[0],
                    'state': 'D',
                    'description': current_tracked[1],
                })
                devegg = True

        # handle versions.cfg and inherited
        for idx, location in enumerate(current_pkg):
            ver_maxlen = max([ver_maxlen, len(current_pkg.get(name, ''))])
            versions.append(
                build_version(
                    name,
                    current_pkg,
                    pypi.get(name, {}),
                    current_tracked,
                    location,
                    idx,
                    flavor='versions',
                )
            )
        if not devegg and current_tracked is not None and not len(versions):
            ver_maxlen = max([ver_maxlen, len(current_tracked[0])])
            versions.append({
                'version': current_tracked[0],
                'state': 'X',
                'description': 'unpinned',
            })
            unpinned = True

        if pypi.get(name, None) is not None:
            current_pypi = pypi[name]
            for label, version in current_pypi.items():
                if version is None:
                    continue
                versions.append(
                    build_version(
                        name,
                        current_pkg,
                        current_pypi,
                        current_tracked,
                        label,
                        idx,
                        flavor='pypi',
                    )
                )

        pkgsinfo['ver_maxlen'] = ver_maxlen
        states = analyser.uptodate_analysis(
            current_pkg,
            pypi.get(name, {}),
        )
        if devegg:
            # dev always wins - not true!
            record['state'] = 'D'
        elif unpinned:
            record['state'] = 'X'
        elif name in pkgs and name not in tracked:
            record['state'] = 'O'
        elif 'pypifinal' in states:
            record['state'] = 'U'
        elif 'cfg' in states:
            record['state'] = 'In'
        elif 'pypifinal' in states:
            record['state'] = 'P'
        else:
            record['state'] = 'A'

        if newer_only and record['state'] == 'A':
            continue

        result[name] = record
    return result


def human(pkgsinfo, newer_only=False, limit=None, show_requiredby=False):
    color_init()
    sys.stderr.write('\nReport for humans\n\n')
    data = builder(pkgsinfo, newer_only=newer_only, limit=limit)
    for name, record in data.items():
        print(color_by_state(record['state']) + name)
        for version in record['versions']:
            print(
                ' ' * 4 +
                color_by_state(version['state']) +
                version['version'] + ' ' +
                dots(version['version'], pkgsinfo['ver_maxlen']-1) +
                ' ' + color_by_state(version['state']) +
                version['state'][0] + ' ' + version['description']
            )
            if show_requiredby and version.get('required_by', False):
                req = ' '.join(version.get('required_by'))
                indent = (pkgsinfo['ver_maxlen']+4)*' '
                print(
                    textwrap.fill(
                        req,
                        80 - pkgsinfo['ver_maxlen'],
                        initial_indent=indent,
                        subsequent_indent=indent,
                    ) + '\n'
                )


def machine(pkgsinfo, newer_only=False, limit=None):
    sys.stderr.write('\nReport for machines\n\n')
    data = builder(pkgsinfo, newer_only=newer_only, limit=limit)
    print(json.dumps(data, indent=4))
