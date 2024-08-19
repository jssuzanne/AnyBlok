# This file is a part of the AnyBlok project
#
#    Copyright (C) 2017 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
from functools import lru_cache

from .plugins import ModelPluginBase


class CachePlugin(ModelPluginBase):
    def __init__(self, registry):
        if not hasattr(registry, "caches"):
            registry.caches = {}

        super(CachePlugin, self).__init__(registry)

    def transform_base(
        self, namespace, base, transformation_properties, new_type_properties
    ):
        cache = self.registry.caches.setdefault(namespace, {})
        print(namespace, base)
        if hasattr(base, "__declared_caches__"):
            for method_name, method in base.__declared_caches__.items():
                entry = cache.setdefault(method_name, [])
                wrapper = lru_cache(maxsize=method.size)(method)
                entry.append(wrapper)
                if method.is_clasmethod:
                    new_type_properties[method_name] = classmethod(wrapper)
                else:
                    new_type_properties[method_name] = wrapper

    def after_model_construction(
        self, base, namespace, transformation_properties
    ):
        for dep in base.__depends__:
            if dep in self.registry.caches:
                cache = self.registry.caches.setdefault(namespace, {})
                for method_name, methods in self.registry.caches[dep].items():
                    entry = cache.setdefault(method_name, [])
                    entry.extend(methods)
