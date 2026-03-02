# This file is a part of the AnyBlok project
#
#    Copyright (C) 2018 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
from sqlalchemy import and_, event, table
from sqlalchemy.orm import Query, relationship
from sqlalchemy_views import CreateView, DropView

from anyblok.common import anyblok_column_prefix, merge_structure

from .exceptions import ModelFactoryException, ViewException


class BaseFactory:
    def __init__(self, registry):
        self.registry = registry

    def get_structure(self, from_structure):
        raise ModelFactoryException("Must be overwritten")  # pragma: no cover

    def build_model(self, modelname, properties):
        raise ModelFactoryException("Must be overwritten")  # pragma: no cover


class ModelFactory(BaseFactory):

    def get_structure(self, from_structure):
        structure = {'bases': []}
        for b in self.registry.loaded_cores['Base'][::-1]:
            if b in self.registry.removed:
                continue
            merge_structure(structure, b.__anyblok_pre_structure__)
            structure['bases'].insert(0, b)

        if from_structure.get("has_any_field", False) is True:
            structure['bases'].insert(0, self.registry.declarativebase)
            for b in self.registry.loaded_cores['SqlBase'][::-1]:
                if b in self.registry.removed:
                    continue
                merge_structure(structure, b.__anyblok_pre_structure__)
                structure['bases'].insert(0, b)

        merge_structure(structure, from_structure)
        return structure

    def build_model(self, modelname, properties):
        if properties.get("ignore_migration") is True:
            self.registry.ignore_migration_for[  # pragma: no cover
                properties["__tablename__"]
            ] = True

        return type(
            modelname,
            tuple(properties['__anyblok_structure__']['bases']),
            properties
        )


def get_columns(view, columns):
    if not isinstance(columns, list):  # pragma: no cover
        if ", " in columns:
            columns = columns.split(", ")
        else:
            columns = [columns]

    return [getattr(view.c, x) for x in columns]


class ViewFactory(BaseFactory):

    def get_structure(self, from_structure):
        structure = {'bases': []}
        for core in ('Base', 'SqlViewBase'):
            for b in self.registry.loaded_cores[core][::-1]:
                if b in self.registry.removed:
                    continue
                merge_structure(structure, b.__anyblok_pre_structure__)
                structure['bases'].insert(0, b)

        merge_structure(structure, from_structure)
        return structure

    # def build_model(self, modelname, bases, properties):
    def build_model(self, modelname, properties):
        Model = type(
            modelname, 
            # tuple(bases), 
            tuple(properties['__anyblok_structure__']['bases']),
            properties,
        )
        self.apply_view(Model, properties)
        return Model

    def apply_view(self, base, properties):
        """Transform the sqlmodel to view model

        :param base: Model cls
        :param properties: properties of the model
        :exception: MigrationException
        :exception: ViewException
        """
        tablename = base.__tablename__
        if hasattr(base, "__view__"):
            view = base.__view__
        elif tablename in self.registry.loaded_views:
            view = self.registry.loaded_views[tablename]
        else:
            if not hasattr(base, "sqlalchemy_view_declaration"):
                raise ViewException(
                    "%r.'sqlalchemy_view_declaration' is required to "
                    "define the query to apply of the view" % base
                )

            view = table(tablename)

            selectable = getattr(base, "sqlalchemy_view_declaration")()

            if isinstance(selectable, Query):
                selectable = selectable.subquery()  # pragma: no cover

            pks_ = set()
            fks_ = set()
            for c in selectable.subquery().columns:
                col = c._make_proxy(view, pks_, fks_)[1]
                view._columns.replace(col)

            view.primary_key.update(pks_)
            view.foreign_keys.update(fks_)

            metadata = self.registry.declarativebase.metadata
            event.listen(
                metadata, "before_create", DropView(view, if_exists=True)
            )
            event.listen(metadata, "after_create", CreateView(view, selectable))
            event.listen(
                metadata, "before_drop", DropView(view, if_exists=True)
            )
            self.registry.loaded_views[tablename] = view

        pks = [
            col
            for col in properties["loaded_columns"]
            if getattr(
                getattr(base, anyblok_column_prefix + col), "primary_key", False
            )
        ]

        if not pks:
            raise ViewException("%r have any primary key defined" % base)

        pks = [getattr(view.c, x) for x in pks]
        mapper_properties = self.get_mapper_properties(base, view, properties)
        base.anyblok.declarativebase.registry.map_imperatively(
            base, view, primary_key=pks, properties=mapper_properties
        )
        setattr(base, "__view__", view)

    def get_mapper_properties(self, base, view, properties):
        mapper_properties = base.define_mapper_args()
        for field in properties["loaded_columns"]:
            if not hasattr(
                properties[anyblok_column_prefix + field], "anyblok_field"
            ):
                mapper_properties[field] = getattr(view.c, field)
                continue

            anyblok_field = properties[
                anyblok_column_prefix + field
            ].anyblok_field
            kwargs = anyblok_field.kwargs.copy()
            if "foreign_keys" in kwargs:
                foreign_keys = kwargs["foreign_keys"][1:][:-1].split(", ")
                foreign_keys = [
                    getattr(view.c, x.split(".")[1]) for x in foreign_keys
                ]
                kwargs["foreign_keys"] = foreign_keys

            if anyblok_field.model.model_name == base.__registry_name__:
                remote_columns = get_columns(
                    view, kwargs["info"]["remote_columns"]
                )
                local_columns = get_columns(
                    view, kwargs["info"]["local_columns"]
                )

                assert len(remote_columns) == len(local_columns)
                primaryjoin = []
                for i in range(len(local_columns)):
                    primaryjoin.append(remote_columns[i] == local_columns[i])

                if len(primaryjoin) == 1:
                    primaryjoin = primaryjoin[0]
                else:
                    primaryjoin = and_(*primaryjoin)

                kwargs["remote_side"] = remote_columns
                kwargs["primaryjoin"] = primaryjoin
                Model = base
            else:
                Model = self.registry.get(anyblok_field.model.model_name)

            mapper_properties[field] = relationship(Model, **kwargs)

        return mapper_properties
