# This file is a part of the AnyBlok project
#
#    Copyright (C) 2017 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
from anyblok.mapper import ModelAttribute, ModelMapper

from .plugins import ModelPluginBase


class ORMEventException(Exception):
    pass


class EventPlugin(ModelPluginBase):
    def __init__(self, registry):
        if not hasattr(registry, "events"):
            registry.events = {}

        super(EventPlugin, self).__init__(registry)

    def before_model_construction(self, properties):
        if properties['__anyblok_structure__']["events"]:
            events = self.registry.events
            for event_ in properties['__anyblok_structure__']["events"]:
                mapper = event_.mapper
                attr = event_.attribute
                model = mapper.model.model_name
                event = mapper.event

                ev1 = events.setdefault(model, {})
                ev2 = ev1.setdefault(event, [])

                val = (properties['__registry_name__'], attr)
                if val not in ev2:
                    ev2.append(val)


class SQLAlchemyEventPlugin(ModelPluginBase):

    def before_model_construction(self, properties):
        namespace = properties['__registry_name__']
        for event_ in properties['__anyblok_structure__']["sqlalchemy_events"]:
            mapper = event_.mapper
            attr = event_.attribute
            self.registry._sqlalchemy_known_events.append(
                (
                    mapper,
                    namespace,
                    ModelAttribute(namespace, attr),
                )
            )


class AutoSQLAlchemyORMEventPlugin(ModelPluginBase):
    def after_model_construction(self, base):
        for eventtype in (
            "before_insert",
            "after_insert",
            "before_update",
            "after_update",
            "before_delete",
            "after_delete",
        ):
            attr = eventtype + "_orm_event"
            if hasattr(base, attr):
                if not hasattr(getattr(base, attr), "__self__"):
                    raise ORMEventException(
                        "On %s %s is not a classmethod" % (base, attr)
                    )

                self.registry._sqlalchemy_known_events.append(
                    (
                        ModelMapper(base, eventtype),
                        base.__registry_name__,
                        ModelAttribute(base.__registry_name__, attr),
                    )
                )
