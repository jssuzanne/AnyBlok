# This file is a part of the AnyBlok project
#
#    Copyright (C) 2014 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#    Copyright (C) 2021 Jean-Sebastien SUZANNE <js.suzanne@gmail.com>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
import sys

from sqlalchemy import text
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.schema import ForeignKeyConstraint
from sqlalchemy.sql.naming import ConventionDict
from pytz.tzinfo import BaseTzInfo

"""Define the prefix for the mapper attribute of the column"""
anyblok_column_prefix = "ANYBLOK_FIELD_"


def all_column_name(constraint, table):
    """Define the convention to merge the column keys

    :param constraint:
    :return:
    """
    if isinstance(constraint, ForeignKeyConstraint):
        return "_".join(constraint.column_keys)
    else:
        return "_".join(constraint.columns.keys())


def model_name(constraint, table):
    """Return a shortest table name

    :param table:
    :return:
    """
    name = table.name.split("_")
    if len(name) == 1:
        return name[0]

    return "".join(x[0] for x in name[:-1]) + "_" + name[-1]


def constraint_name(constraint, table):
    """return a shortest table name"""
    conv = ConventionDict(constraint, table, naming_convention)
    try:
        return conv._key_constraint_name()
    except InvalidRequestError:  # pragma: no cover
        if constraint._pending_colargs:
            return "_".join([x.name for x in constraint._pending_colargs])

        raise


"""table convention for constraint"""
naming_convention = {
    "all_column_name": all_column_name,
    "model_name": model_name,
    "constraint_name": constraint_name,
    "ix": "anyblok_ix_%(model_name)s__%(all_column_name)s",
    "uq": "anyblok_uq_%(model_name)s__%(all_column_name)s",
    "ck": "anyblok_ck_%(model_name)s__%(constraint_name)s",
    "fk": "anyblok_fk_%(model_name)s__%(all_column_name)s",
    "pk": "anyblok_pk_%(table_name)s",
}


def add_autodocs(meth, autodoc):
    """Add autodocs entries

    :param meth:
    :param autodoc:
    """
    if not hasattr(meth, "autodocs"):
        meth.autodocs = []

    meth.autodocs.append(autodoc)


def function_name(function_):
    """Return the name of the function

    :param function_:
    :return:
    """
    return function_.__qualname__


def python_version():  # pragma: no cover
    """Return Python version tuple

    :return:
    """
    vi = sys.version_info
    return (vi.major, vi.minor)


DATABASES_CACHED = {}


def sgdb_in(engine, databases):
    for database in databases:
        if database not in DATABASES_CACHED:
            DATABASES_CACHED[database] = False
            if engine.url.drivername.startswith("mysql"):
                if database == "MySQL":
                    DATABASES_CACHED["MySQL"] = True

                with engine.connect() as conn:
                    res = conn.execute(
                        text("show variables like 'version'")
                    ).fetchone()
                    if res and database in res[1]:
                        # MariaDB
                        DATABASES_CACHED[database] = True  # pragma: no cover

            if (
                engine.url.drivername.startswith("postgres")
                and database == "PostgreSQL"
            ):
                DATABASES_CACHED["PostgreSQL"] = True
            if (
                engine.url.drivername.startswith("mssql")
                and database == "MsSQL"
            ):
                DATABASES_CACHED["MsSQL"] = True  # pragma: no cover

        if DATABASES_CACHED[database]:
            return True

    return False


def return_list(entry):
    if entry is None:
        return []

    elif not isinstance(entry, (list, tuple)):
        entry = [entry]

    return entry

def merge_structure(into_structure, from_structure):
    for key, values in from_structure.items():
        if key == 'bases':
            if key not in into_structure:
                into_structure[key] = []

            for b in values[::-1]:
                if b not in into_structure['bases']:
                    into_structure['bases'].insert(0, b)
        elif isinstance(values, dict):
            if key not in into_structure:
                into_structure[key] = {}

            into_structure[key].update(values)
        elif isinstance(values, set):
            if key not in into_structure:
                into_structure[key] = set()

            into_structure[key] |= values
        elif isinstance(values, bool):
            if key not in into_structure:
                into_structure[key] = False

            into_structure[key] = into_structure[key] or from_structure[key]


def class_to_path(cls):
    return f"{cls.__module__}:{cls.__name__}"


def path_to_class(import_definition):
    if not isinstance(import_definition, str):
        return import_definition

    import_path, import_name = import_definition.split(":")
    module = __import__(import_path, fromlist=[import_name])
    if hasattr(module, import_name):
        return getattr(module, import_name)

    raise ImportError("%s does not exist in %s" % (import_name, import_path))


def resolve_cache(elements):
    if isinstance(elements, list | tuple):
        elements = [resolve_cache(x) for x in elements]
        if len(elements) == 2 and isinstance(elements[0], str):
            mapping = {
                'path_to_class': path_to_class,
                'cache_to_instance': cache_to_instance,
            }
            func = mapping.get(elements[0], None)
            if func:
                return func(elements[1])

        return elements

    if isinstance(elements, dict):
        return {
            k: resolve_cache(v)
            for k, v in elements.items()
        }

    return elements


def adapt_to_cache(obj):
    """
    Transforme récursivement un objet complexe en dictionnaire JSON-compatible.
    """
    from anyblok.mapper import ModelAttribute, ModelRepr

    if isinstance(obj, ModelAttribute | ModelRepr):
        return str(obj)

    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    
    if isinstance(obj, (list, tuple)):
        return [adapt_to_cache(item) for item in obj]
    
    if isinstance(obj, dict):
        return {str(k): adapt_to_cache(v) for k, v in obj.items()}
    
    if isinstance(obj, type):
        if hasattr(obj, '__registry_name__'):
            return obj.__registry_name__

        return ["path_to_class", class_to_path(obj)]

    if isinstance(obj, BaseTzInfo):
        return str(obj)

    if hasattr(obj, 'to_cache'):
        return ["cache_to_instance", obj.to_cache()]
    
    if hasattr(obj, "__dict__"):
        return adapt_to_cache(obj.__dict__)
        
    return str(obj)


def cache_to_instance(cache):
    args = resolve_cache(cache[1])
    kwargs = resolve_cache(dict(cache[2]))
    return path_to_class(cache[0])(*args, **kwargs)


class CachableType:

    def to_cache(self):
        return [
            class_to_path(self.__class__),
            adapt_to_cache(self.__called_args),
            list(adapt_to_cache(self.__called_kwargs).items())
        ]

    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls)
        self.__called_args = args
        self.__called_kwargs = kwargs
        return self
