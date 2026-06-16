# This file is a part of the AnyBlok project
#
#    Copyright (C) 2014 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#    Copyright (C) 2017 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#    Copyright (C) 2018 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#    Copyright (C) 2019 Jean-Sebastien SUZANNE <js.suzanne@gmail.com>
#    Copyright (C) 2021 Jean-Sebastien SUZANNE <js.suzanne@gmail.com>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
from copy import deepcopy

from sqlalchemy import inspection
from sqlalchemy.orm import declared_attr
from texttable import Texttable

from anyblok import Declarations
from anyblok.common import (
    anyblok_column_prefix,
    merge_structure,
    class_to_path,
    path_to_class,
    cache_to_instance,
)
from anyblok.mapper import ModelAttribute, FakeField, format_schema
from anyblok.registry import RegistryManager

from .exceptions import ModelException
from .factory import ModelFactory
from .plugins import get_model_plugins
from ..environment import EnvironmentManager


def has_sqlalchemy_fields(base):
    for p in base.__dict__.keys():
        attr = base.__dict__[p]
        if inspection.inspect(attr, raiseerr=False) is not None:
            return True

    return False


def autodoc_fields(declaration_cls, model_cls):  # pragma: no cover
    """Produces autodocumentation table for the fields.

    Exposed as a function in order to be reusable by a simple export,
    e.g., from anyblok.mixin.
    """
    structure = model_cls.__anyblok_structure__
    if not structure['has_any_field']:
        return ""

    rows = [["Fields", ""]]
    fields = {}
    fields.update(structure["fields"])
    fields.update(structure["columns"])
    fields.update(structure["relationships"])
    rows.extend([x, y.autodoc()] for x, y in fields.items())
    table = Texttable(max_width=0)
    table.set_cols_valign(["m", "t"])
    table.add_rows(rows)
    return table.draw() + "\n\n"


def update_factory(kwargs):
    if "factory" in kwargs:
        kwargs["__model_factory__"] = kwargs.pop("factory")


def check_model_base(cls, registryname):
    if has_sqlalchemy_fields(cls):
        raise ModelException("the base %r have an SQLAlchemy attribute" % cls)

    if hasattr(cls, "__table_args__"):
        raise ModelException(
            "'__table_args__' attribute is forbidden, on Model : %r (%r)."
            "Use the class method 'define_table_args' to define the value "
            "allow anyblok to fill his own '__table_args__' attribute"
            % (registryname, cls.__table_args__)
        )

    if hasattr(cls, "__mapper_args__"):
        raise ModelException(
            "'__mapper_args__' attribute is forbidden, on Model : %r (%r)."
            "Use the class method 'define_mapper_args' to define the "
            "value allow anyblok to fill his own '__mapper_args__' "
            "attribute" % (registryname, cls.__mapper_args__)
        )


class ModelProxy:

    def __init__(self, registry, namespace):
        # On utilise object.__setattr__ pour éviter de déclencher 
        # une logique de Proxy pendant l'initialisation
        object.__setattr__(self, 'registry', registry)
        object.__setattr__(self, 'namespace', namespace)
        object.__setattr__(self, 'children_namespaces', {})
        object.__setattr__(self, 'parent', None)
        object.__setattr__(self, 'Model', None)
        object.__setattr__(self, 'is_loading', False)

    def __repr__(self):
        return f"<Proxy ({self.namespace})/>"

    def load_model(self, load_dependencies=True):
        object.__setattr__(self, 'is_loading', True)
        if self.Model is None:
            first_step = self.registry.loaded_namespaces_first_step[self.namespace]
            for inherit in first_step['__inherits__']:
                _Model = self.registry.get(inherit)
                if isinstance(_Model, ModelProxy) and not _Model.is_loading:
                    _Model.load_model()

            for relationship in first_step['__anyblok_structure__']['relationships'].values():
                if isinstance(relationship, FakeField):
                    model = relationship.mapper.model_name
                else:
                    model = relationship.model.model_name
            
                _Model = self.registry.get(model)
                if isinstance(_Model, ModelProxy) and not _Model.is_loading:
                    _Model.load_model()

            RealModel = Model.load_namespace_second_step(self.registry, self.namespace)
            object.__setattr__(self, 'Model', RealModel)

        return self.Model

    def __getattr__(self, attribute):
        ns = f"{self.namespace}.{attribute}"
        if ns in self.registry.loaded_namespaces_first_step:
            if attribute in self.children_namespaces:
                return self.children_namespaces[attribute]

            raise AttributeError(f"'{self.namespace}' has no attribute '{attribute}'")

        RealModel = self.load_model()
        return getattr(RealModel, attribute)

    def __setattr__(self, attribut, value):
        if isinstance(value, ModelProxy):
            self.children_namespaces[attribut] = value
            object.__setattr__(value, 'parent', self)

        object.__setattr__(self, attribut, value)

    def __call__(self, *args, **kwargs):
        RealModel = self.load_model()
        return RealModel(*args, **kwargs)

    
@Declarations.add_declaration_type(
    isAnEntry=True,
    pre_assemble="pre_assemble_callback",
    assemble="assemble_callback",
    initialize="initialize_callback",
    to_cache="to_cache",
    from_cache="from_cache",
)
class Model:
    """The Model class is used to define or inherit an SQL table.

    Add new model class::

        @Declarations.register(Declarations.Model)
        class MyModelclass:
            pass

    Remove a model class::

        Declarations.unregister(Declarations.Model.MyModelclass,
                                MyModelclass)

    There are three Model families:

    * No SQL Model: These models have got any field, so any table
    * SQL Model:
    * SQL View Model: it is a model mapped with a SQL View, the insert, update
      delete method are forbidden by the database

    Each model has a:

    * registry name: compose by the parent + . + class model name
    * table name: compose by the parent + '_' + class model name

    The table name can be overloaded by the attribute tablename. the wanted
    value are a string (name of the table) of a model in the declaration.

    ..warning::

        Two models can have the same table name, both models are mapped on
        the table. But they must have the same column.
    """

    autodoc_anyblok_kwargs = True

    autodoc_anyblok_bases = True

    autodoc_anyblok_fields = True

    @classmethod
    def pre_assemble_callback(cls, registry):
        plugins_by = {
            'init': [],
            "before_model_construction": [],
            "after_model_construction": [],
        }
        for plugin in get_model_plugins(registry):
            for attr in plugins_by:
                func = getattr(plugin, attr, None)
                if func:
                    plugins_by[attr].append(func)

        def call_plugins(method, *args, **kwargs):
            """call the method on each plugin"""
            for func in plugins_by.get(method, []):
                func(*args, **kwargs)

        registry.call_plugins = call_plugins
        registry.plugins_by = plugins_by

    @classmethod
    def register(self, parent, name, cls_, **kwargs):
        """add new sub registry in the registry

        :param parent: Existing global registry
        :param name: Name of the new registry to add it
        :param cls_: Class Interface to add in registry
        """
        _registryname = parent.__registry_name__ + "." + name
        check_model_base(cls_, _registryname)

        if "tablename" in kwargs:
            tablename = kwargs.pop("tablename")
            if not isinstance(tablename, str):
                tablename = tablename.__tablename__

        elif hasattr(parent, name):
            tablename = getattr(parent, name).__tablename__
        else:
            if parent is Declarations or parent is Declarations.Model:
                tablename = name.lower()
            elif hasattr(parent, "__tablename__"):
                tablename = parent.__tablename__
                tablename += "_" + name.lower()

        if not hasattr(parent, name):
            p = {
                "__tablename__": tablename,
                "__registry_name__": _registryname,
                "use": lambda x: ModelAttribute(_registryname, x),
            }
            ns = type(name, tuple(), p)
            setattr(parent, name, ns)

        if parent is Declarations:
            return  # pragma: no cover

        kwargs["__registry_name__"] = _registryname
        kwargs["__tablename__"] = tablename
        update_factory(kwargs)

        RegistryManager.add_entry_in_register(
            "Model", _registryname, cls_, **kwargs
        )
        setattr(cls_, "__anyblok_kwargs__", kwargs)

    @classmethod
    def unregister(self, entry, cls_):
        """Remove the Interface from the registry

        :param entry: entry declaration of the model where the ``cls_``
            must be removed
        :param cls_: Class Interface to remove in registry
        """
        RegistryManager.remove_in_register(cls_)

    @classmethod
    def declare_field(
        cls,
        registry,
        name,
        field,
        namespace,
        properties,
    ):
        """Declare the field/column/relationship to put in the properties
        of the model

        :param registry: the current  registry
        :param name: name of the field / column or relationship
        :param field: the declaration field / column or relationship
        :param namespace: the namespace of the model
        :param properties: the properties of the model
        """
        if isinstance(field, FakeField):
            return

        if field.must_be_copied_before_declaration():
            field = deepcopy(field)

        attr_name = name
        if field.use_hybrid_property:
            attr_name = anyblok_column_prefix + name

        if field.must_be_declared_as_attr():
            # All the declaration are seen as mixin for sqlalchemy
            # some of them need de be defered for the initialisation
            # cause of the mixin as relation ship and column with foreign key
            def wrapper(cls):
                return field.get_sqlalchemy_mapping(
                    registry, namespace, name, properties
                )

            properties[attr_name] = declared_attr(wrapper)
            properties[attr_name].anyblok_field = field
        else:
            properties[attr_name] = field.get_sqlalchemy_mapping(
                registry, namespace, name, properties
            )

        if field.use_hybrid_property:
            properties[name] = field.get_property(
                registry, namespace, name, properties
            )
            properties[name].sqla_column = properties[attr_name]

            properties["hybrid_property_columns"].append(name)

        def field_description():
            return registry.get(namespace).fields_description(name)[name]

        def from_model():
            return registry.get(namespace)

        properties[name].anyblok_field_name = name
        properties[name].anyblok_registry_name = namespace
        properties[name].field_description = field_description
        properties[name].from_model = from_model
        properties["loaded_columns"].append(name)
        field.update_properties(registry, namespace, name, properties)

    @classmethod
    def load_namespace_first_step(cls, registry, namespace):
        """Return the properties of the declared bases for a namespace.
        This is the first step because some actions need to known all the
        properties

        :param registry: the current registry
        :param namespace: the namespace of the model
        :rtype: dict of the known properties
        """
        if namespace in registry.loaded_namespaces_first_step:
            return registry.loaded_namespaces_first_step[namespace]

        ns = registry.loaded_registries[namespace]
        properties = {}
        db_schema = format_schema(None, namespace)
        Factory = ns["properties"].get("__model_factory__", ModelFactory)
        model_factory = Factory(registry)

        final_structure = {
            "columns": {},
            "relationships": {},
            "fields": {},
            "caches": {},
            "hybrid_methods": set(),
            "events": set(),
            "sqlalchemy_events": set(),
            "bases": [],
        }
        inherits = []

        def _merge_structure(cls_):
            final_structure['bases'].insert(0, cls_)
            merge_structure(final_structure, getattr(cls_, '__anyblok_pre_structure__', {}))

        for b in ns["bases"][::-1]:
            if b in registry.removed:
                continue

            for b_ns in b.__anyblok_bases__:
                inherited_properties = cls.load_namespace_first_step(
                    registry, b_ns.__registry_name__)
                anyblok_structure = deepcopy(inherited_properties['__anyblok_structure__'])
                if b_ns.__registry_name__.startswith('Model.'):
                    anyblok_structure['bases'] = [b_ns.__registry_name__]
                    anyblok_structure['fields'] = {}
                    anyblok_structure['columns'] = {}
                    anyblok_structure['relationships'] = {}
                    inherits.append(b_ns.__registry_name__)

                merge_structure(final_structure, anyblok_structure)

            # Aggregation from Registry Mixin cache
            _merge_structure(b)
            if hasattr(b, "__db_schema__"):
                db_schema = format_schema(b.__db_schema__, namespace)

        final_structure['has_any_field'] = has_any_field = any(
            [any(final_structure.get(x, [])) for x in ('fields', 'columns', 'relationships')]
        )
        properties.update(
            {
                "__registry_name__": namespace,
                "__db_schema__": db_schema,
                "__model_factory__": model_factory,
                "loaded_columns": [],
                "hybrid_property_columns": [],
                "loaded_fields": {},
                "__anyblok_structure__": (
                    model_factory.get_structure(final_structure)
                    if namespace.startswith('Model.') else final_structure
                ),
                "__inherits__": inherits,
            }
        )

        if has_any_field and "__tablename__" in ns["properties"]:
            properties["__tablename__"] = ns["properties"]["__tablename__"]

        registry.loaded_namespaces_first_step[namespace] = properties
        return properties

    @classmethod
    def apply_inheritance_base(
        cls,
        registry,
        properties,
    ):
        bases = []
        for base in properties["__anyblok_structure__"]["bases"][::-1]:
            if isinstance(base, str):
                if ':' in base:
                    try:
                        EnvironmentManager.set("current_blok", f"db_{registry.db_name}")
                        bases.insert(0, path_to_class(base))
                    finally:
                        EnvironmentManager.set("current_blok", None)
                elif base == 'DeclarativeBase':
                    bases.insert(0, registry.declarativebase)
                elif base in registry.loaded_registries["Model_names"]:
                    bs = cls.load_namespace_second_step(registry, base)
                    bases.insert(0, bs)
                else:
                    raise ModelException(  # pragma: no cover
                        "You have not to inherit the %r "
                        "Only the 'Mixin' and %r types are allowed"
                        % (base, cls.__name__)
                    )
            else:
                bases.insert(0, base)

        properties['__anyblok_structure__']['bases'] = bases

    @classmethod
    def declare_all_fields(cls, registry, namespace, properties):
        # do in the first time the fields and columns
        # because for the relationship on the same model
        # the primary keys must exist before the relationship
        # load all the base before do relationship because primary key
        # can be come from inherit
        for key in (
            "fields",
            "columns",
            "relationships",
        ):
            for p, f in properties['__anyblok_structure__'][key].items():
                cls.declare_field(
                    registry,
                    p,
                    f,
                    namespace,
                    properties,
                )

    @classmethod
    def apply_existing_table(
        cls,
        registry,
        namespace,
        tablename,
        properties,
    ):
        if "__tablename__" in properties:
            del properties["__tablename__"]

        properties['__table__'] = registry.declarativebase.metadata.tables.get(tablename)

        for p, f in properties["__anyblok_structure__"]["fields"].items():
            cls.declare_field(
                registry,
                p,
                f,
                namespace,
                properties,
            )

    @classmethod
    def load_namespace_second_step(
        cls,
        registry,
        namespace,
    ):
        """Return the bases and the properties of the namespace

        :param registry: the current registry
        :param namespace: the namespace of the model
        :param realregistryname: the name of the model if the namespace is a
            mixin
        :rtype: the list od the bases and the properties
        :exception: ModelException
        """
        pmodel = registry.loaded_namespaces[namespace]
        if not isinstance(pmodel, ModelProxy):
            return pmodel

        first_step = registry.loaded_namespaces_first_step[namespace].copy()
        tablename = first_step.get("__tablename__")
        modelname = namespace.replace(".", "")
        registry.call_plugins("init", first_step)
        cls.apply_inheritance_base(registry, first_step)

        if tablename in registry.declarativebase.metadata.tables:
            cls.apply_existing_table(
                registry,
                namespace,
                tablename,
                first_step,
            )
        else:
            cls.declare_all_fields(
                registry,
                namespace,
                first_step,
            )

        registry.call_plugins("before_model_construction", first_step)
        base = first_step["__model_factory__"].build_model(
            modelname, first_step
        )

        registry.add_in_registry(namespace, base)

        registry.loaded_namespaces[namespace] = base
        registry.call_plugins("after_model_construction", base)
        return base

    @classmethod
    def assemble_callback(cls, registry):
        """Assemble callback is called to assemble all the Model
        from the installed bloks

        :param registry: registry to update
        """
        registry.loaded_namespaces_first_step = {}
        registry.loaded_views = {}
        registry.auto_load = []

        # get all the information to create a namespace
        for namespace in registry.loaded_registries["Model_names"]:
            properties = registry.loaded_registries[namespace]['properties']
            cls.load_namespace_first_step(registry, namespace)
            model = ModelProxy(registry, namespace)
            registry.add_in_registry(namespace, model)
            registry.loaded_namespaces[namespace] = model
            if properties.get('auto_load'):
                registry.auto_load.append(namespace)

        for namespace in registry.loaded_registries["Model_names"]:
            cls.load_namespace_second_step(registry, namespace)


    @classmethod
    def initialize_callback(cls, registry):
        """initialize callback is called after assembling all entries

        This callback updates the database information about

        * Model
        * Column
        * RelationShip

        :param registry: registry to update
        """
        for Model in registry.loaded_namespaces.values():
            Model.initialize_model()
            Model.clear_all_model_caches()

        Blok = registry.System.Blok
        registry.update_blok_list()

        bloks = Blok.list_by_state("touninstall")
        Blok.uninstall_all(*bloks)
        res = Blok.apply_state(*registry.ordered_loaded_bloks)

        return res

    @classmethod
    def to_cache(cls, registry):
        cache = {
            'auto_load': registry.auto_load,
            'ordered_models': registry.loaded_registries['Model_names'],
            'models': {},
            'plugins': {},
        }
        for plugin, funcs in registry.plugins_by.items():
            cache['plugins'][plugin] = [class_to_path(x.__self__.__class__) for x in funcs]

        for model in cache['ordered_models']:
            fs = registry.loaded_namespaces_first_step[model]
            model_cache = {
                x: fs[x]
                for x in ('__db_schema__', '__inherits__', '__registry_name__', '__tablename__')
                if x in fs
            }
            model_cache.update({
                "loaded_columns": [],
                "hybrid_property_columns": [],
                "loaded_fields": {},
            })
            model_cache['__model_factory__'] = class_to_path(fs['__model_factory__'].__class__)
            model_cache['structure'] = {
                'bases': [],
            }
            for key, values in fs['__anyblok_structure__'].items():
                if key == 'bases':
                    for base in values:
                        if base is registry.declarativebase:
                            model_cache['structure']['bases'].append('DeclarativeBase')
                        else:
                            model_cache['structure']['bases'].append(class_to_path(base))
                elif isinstance(values, set):
                    model_cache['structure'][key] = set(
                    )
                elif isinstance(values, dict):
                    model_cache['structure'][key] = {
                        k: v.to_cache()
                        for k, v in values.items()
                        if hasattr(v, 'to_cache')
                    }
                elif isinstance(values, bool):
                    model_cache['structure'][key] = values

            cache['models'][model] = model_cache

        return cache

    @classmethod
    def from_cache(cls, registry, cache):
        plugins_by = {}
        plugins_ = {}
        
        def get_plugin(name):
            if name not in plugins_:
                plugins_[name] = path_to_class(name)(registry)
        
            return plugins_[name]
        
        for func, plugins in cache['plugins'].items():
            plugins_by[func] = [
                getattr(get_plugin(x), func)
                for x in plugins
            ]
        
        def call_plugins(method, *args, **kwargs):
            """call the method on each plugin"""
            for func in plugins_by.get(method, []):
                func(*args, **kwargs)
        
        registry.call_plugins = call_plugins
        registry.plugins_by = plugins_by

        registry.loaded_namespaces_first_step = cache['models']
        for namespace in cache['ordered_models']:
            cls.add_in_declaration(registry, namespace)
            first_step = cache['models'][namespace]
            cls.model_from_cache(registry, first_step)
            model = ModelProxy(registry, namespace)
            registry.add_in_registry(namespace, model)
            registry.loaded_namespaces[namespace] = model
            if namespace in cache['auto_load']:
                model.load_model()

    @classmethod
    def add_in_declaration(cls, registry, namespace):
        current_node = Declarations.Model
        for part in namespace.split('.')[1:]:
            if not hasattr(current_node, part):
                new_node = type(part, (), {
                    "__tablename__": registry.loaded_namespaces_first_step[namespace].get('__tablename__', namespace[1:].replace('.', '_')),
                    "__registry_name__": namespace,
                    "use": lambda x: ModelAttribute(namespace, x),
                    "__declaration_type__": 'Model',
                })
                setattr(current_node, part, new_node)

            current_node = getattr(current_node, part)

    @classmethod
    def model_from_cache(cls, registry, first_step):
        if not isinstance(first_step['__model_factory__'], str):
            return

        first_step['__model_factory__'] = path_to_class(first_step['__model_factory__'])(registry)
        structure = first_step.pop('structure')
        try:
            blok_name = f"db_{registry.db_name}"
            EnvironmentManager.set("current_blok", blok_name)

            for key, values in structure.items():
                if key == 'bases':
                    continue
                    bases = []
                    for base in values[::-1]:
                        if base == 'DeclarativeBase': 
                            bases.insert(0, registry.declarative_base)
                        else:
                            bases.insert(0, path_to_class(base))
                    structure[key] = bases
                elif isinstance(values, set):
                    structure[key] = set(cache_to_instance(x) for x in values)
                elif isinstance(values, dict):
                    structure[key] = {
                        k: cache_to_instance(v) for k, v in values.items()
                    }
                else:
                    structure[key] = values

        finally:
            EnvironmentManager.set("current_blok", None)

        first_step['__anyblok_structure__'] = structure
