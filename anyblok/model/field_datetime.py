# This file is a part of the AnyBlok project
#
#    Copyright (C) 2017 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
from datetime import datetime

from anyblok.column import DateTime
from anyblok.mapper import ModelMapper

from .plugins import ModelPluginBase


class AutoUpdatePlugin(ModelPluginBase):
    def after_model_construction(self, base, namespace=None):
        """Add the sqlalchemy event

        :param base: the Model class
        """
        if namespace is None:
            namespace = base.__registry_name__

        for b in getattr(base, '__anyblok_bases__', []):
            b_ns = b.__registry_name__
            if b_ns.startswith('Model.'):
                self.after_model_construction(self.registry.get(b.__registry_name__), namespace=namespace)

        fields = [
            c
            for c, f in base.__anyblok_structure__["columns"].items()
            if isinstance(f, DateTime) and f.auto_update
        ]

        if fields:
            e = ModelMapper(namespace, "after_update")

            def auto_update_listen(mapper, connection, target):
                now = datetime.now()
                for field in fields:
                    setattr(target, field, now)

            self.registry._sqlalchemy_known_events.append(
                (e, namespace, auto_update_listen)
            )
