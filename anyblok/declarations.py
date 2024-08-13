# This file is a part of the AnyBlok project
#
#    Copyright (C) 2014 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
from warnings import warn
from .common import add_autodocs
from .mapper import MapperAdapter


class DeclarationsException(AttributeError):
    """Simple Exception for Declarations"""


class Declarations:
    """Represents all the declarations done by the bloks

    .. warning::
        This is a global information, during the execution you must use the
        registry. The registry is the real assembler of the python classes
        based on the installed bloks

    ::

        from anyblok import Declarations

    """

    declaration_types = {}

    @classmethod
    def register(cls, parent, cls_=None, **kwargs):
        """Method to add the blok in the registry under a type of declaration

        :param parent: An existing blok class in the Declaration
        :param ``cls_``: The ``class`` object to add in the Declaration
        :rtype: ``cls_``
        :exception: DeclarationsException
        """

        def wrapper(self):
            name = kwargs.get("name_", self.__name__)
            if parent.__declaration_type__ not in cls.declaration_types:
                raise DeclarationsException(
                    "No parents %r for %s" % (parent, name)
                )  # pragma: no cover

            declaration = cls.declaration_types[parent.__declaration_type__]
            declaration.register(parent, name, self, **kwargs)

            node = getattr(parent, name)
            setattr(node, "__declaration_type__", parent.__declaration_type__)
            setattr(
                node, "__registry_name__", parent.__registry_name__ + "." + name
            )

            # Only for auto doc with autoanyblok-declaration directive
            setattr(self, "__declaration__", declaration)
            setattr(
                self, "__registry_name__", parent.__registry_name__ + "." + name
            )
            return self

        if cls_:
            return wrapper(cls_)
        else:
            return wrapper

    @classmethod
    def unregister(cls, entry, cls_):
        """Method to remove the blok from a type of declaration

        :param entry: declaration entry of the model where the ``cls_``
            must be removed
        :param ``cls_``: The ``class`` object to remove from the
            Declaration
        :rtype: ``cls_``
        """
        declaration = cls.declaration_types[entry.__declaration_type__]
        declaration.unregister(entry, cls_)

        return cls_

    @classmethod
    def add_declaration_type(
        cls,
        cls_=None,
        isAnEntry=False,
        pre_assemble=None,
        assemble=None,
        initialize=None,
        unload=None,
    ):
        """Add a declaration type

        :param cls_: The ``class`` object to add as a world of the MetaData
        :param isAnEntry: if true the type will be assembled by the registry
        :param pre_assemble: name of the method callback to call (classmethod)
        :param assemble: name of the method callback to call (classmethod)
        :param initialize: name of the method callback to call (classmethod)
        :param unload: name of the method callback to call (classmethod)
        :exception: DeclarationsException
        """

        def wrapper(self):
            from anyblok.registry import RegistryManager

            name = self.__name__
            if name in cls.declaration_types:
                raise DeclarationsException(
                    "The declaration type %r is already defined" % name
                )

            cls.declaration_types[name] = self

            setattr(self, "__registry_name__", name)
            setattr(self, "__declaration_type__", name)
            setattr(cls, name, self)

            if isAnEntry:
                pre_assemble_callback = assemble_callback = None
                initialize_callback = None
                if pre_assemble and hasattr(self, pre_assemble):
                    pre_assemble_callback = getattr(self, pre_assemble)

                if assemble and hasattr(self, assemble):
                    assemble_callback = getattr(self, assemble)

                if initialize and hasattr(self, initialize):
                    initialize_callback = getattr(self, initialize)

                RegistryManager.declare_entry(
                    name,
                    pre_assemble_callback=pre_assemble_callback,
                    assemble_callback=assemble_callback,
                    initialize_callback=initialize_callback,
                )

            # All declaration type can need to be unload declarated values
            if unload and hasattr(self, unload):
                RegistryManager.declare_unload_callback(
                    name, getattr(self, unload)
                )  # pragma: no cover

            return self

        if cls_:
            return wrapper(cls_)
        else:
            return wrapper


class Cache:
    def __init__(self, size=128):
        self.size = size
        self.autodoc = f"**Cached method** with size={size}"

    def __call__(self, func):
        add_autodocs(func, self.autodoc)
        func.is_clasmethod = False
        func.size = self.size
        self.__func__ = func
        return self

    def __get__(self, obj, cls=None):

        def wrapper(*args, **kwargs):
            return self.__func__(obj, *args, **kwargs)

        return wrapper

    def __set_name__(self, owner, name):
        if not hasattr(owner, "__declared_caches__"):
            owner.__declared_caches__ = {}

        owner.__declared_caches__[name] = self.__func__


def cache(size=128):
    warn("cache decorator is deprecated use Cache")
    return Cache(size=size)


class ClassMethodCache(Cache):
    def __init__(self, size=128):
        super().__init__(size=size)
        self.autodoc = f"**Cached classmethod** with size={size}"

    def __get__(self, obj, cls=None):
        if cls is None:
            cls = type(obj)

        if hasattr(type(self.__func__), '__get__'):
            # This code path was added in Python 3.9
            # and was deprecated in Python 3.11.
            return self.__func__.__get__(cls, cls)

        def wrapper(*args, **kwargs):
            return self.__func__(cls, *args, **kwargs)

        return wrapper

    def __call__(self, func):
        super().__call__(func)
        func.is_clasmethod = True
        return self


def classmethod_cache(size=128):
    warn("classmethod_cache decorator is deprecated use ClassMethodCache")
    return ClassMethodCache(size=size)


class HybridMethod:
    def __init__(self, func=None):
        self.autodoc = "**Hybrid method**"
        if func:
            self.__func__ = func
            add_autodocs(func, self.autodoc)

    def __call__(self, func):
        add_autodocs(func, self.autodoc)
        self.__func__ = func
        return self

    def __get__(self, obj, cls=None):
        if obj is None:
            return self.__func__

        def wrapper(*args, **kwargs):
            return self.__func__(obj, *args, **kwargs)

        return wrapper

    def __set_name__(self, owner, name):
        if not hasattr(owner, "__declared_hybrid_method__"):
            owner.__declared_hybrid_method__ = set()

        owner.__declared_hybrid_method__.add(name)


def hybrid_method(func=None):
    warn("hybrid_method decorator is deprecated use HybridMethod")
    return HybridMethod(func=func)


def listen(*args, **kwargs):
    autodoc = """
    **listen** event call with the arguments %(args)r and the positionnal
    argument %(kwargs)r
    """ % dict(
        args=args, kwargs=kwargs
    )

    mapper = MapperAdapter(*args, **kwargs)

    def wrapper(method):
        add_autodocs(method, autodoc)
        mapper.listen(method)
        return classmethod(method)

    return wrapper
