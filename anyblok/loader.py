# This file is a part of the AnyBlok project
#
#    Copyright (C) 2024 Jean-Sebastien SUZANNE <js.suzanne@gmail.com>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
from graphlib import CycleError, TopologicalSorter


class AnyBlokLoaderError(Exception):
    """Exception raised by the Blok loader"""


def resolve_dependencies(bloks_dict):
    """Resolve blok dependencies and return an ordered list of blok names.

    :param bloks_dict: dict of {blok_name: blok_instance}
    :return: ordered list of blok names
    :raises AnyBlokLoaderError: if a cycle is detected
    """
    ts = TopologicalSorter()

    for blok_name, blok in bloks_dict.items():
        # required dependencies
        requirements = list(getattr(blok, "required", []))

        # optional dependencies: only add if the blok is in the discovered set
        for optional in getattr(blok, "optional", []):
            if optional in bloks_dict:
                requirements.append(optional)

        ts.add(blok_name, *requirements)

    try:
        ts.prepare()
        ordered = []
        while ts.is_active():
            ready = list(ts.get_ready())
            # Sort ready bloks by priority (lowest first) then name
            ready.sort(
                key=lambda n: (getattr(bloks_dict[n], "priority", 100), n)
            )
            for name in ready:
                ordered.append(name)
                ts.done(name)

        return ordered
    except CycleError as e:
        raise AnyBlokLoaderError(
            "Circular dependency detected in bloks: %s" % str(e)
        )
