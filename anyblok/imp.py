# This file is a part of the AnyBlok project
#
#    Copyright (C) 2014 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
from importlib import reload as reload_module
from time import sleep
from anyblok.environment import EnvironmentManager


def reload_module_if_blok_is_reloading(module):
    from anyblok.environment import EnvironmentManager

    if EnvironmentManager.get("reload", default=False):
        reload_module(module)


class ImportManagerException(AttributeError):
    """Exception for Import Manager"""


class ImportManager:
    """Used to import bloks or reload the blok imports

    To add a blok and import its modules::

        blok = ImportManager.add('my blok')
        blok.imports()

    To reload the modules of a blok::

        if ImportManager.has('my blok'):
            blok = ImportManager.get('my blok')
            blok.reload()
    """

    modules = {}

    @classmethod
    def add(cls, blok):
        """Store the blok so that we know which bloks to reload if needed

        :param blok: name of the blok to add
        :rtype: loader instance
        :exception: ImportManagerException
        """
        from anyblok.blok import BlokManager

        if cls.has(blok):
            return cls.get(blok)

        if not BlokManager.has(blok):
            raise ImportManagerException("Unexisting blok")  # pragma: no cover

        loader = Loader(blok)
        cls.modules[blok] = loader
        return loader

    @classmethod
    def get(cls, blok):
        """Return the module imported for this blok

        :param blok: name of the blok to add
        :rtype: loader instance
        :exception: ImportManagerException
        """
        if not cls.has(blok):
            raise ImportManagerException("Unexisting blok %r" % blok)
        return cls.modules[blok]

    @classmethod
    def has(cls, blok):
        """Return True if the blok was imported

        :param blok: name of the blok to add
        :rtype: boolean
        """
        return blok in cls.modules

    @classmethod
    def reload_all(cls, ordered_bloks):
        for blok in ordered_bloks:
            if cls.has(blok):
                mod = cls.get(blok)
                mod.reload()


class Loader:
    def __init__(self, blok):
        self.blok = blok
        self.loaded = False

    def imports(self):
        """Imports modules and / or packages listed in the blok path"""
        if self.loaded:
            return

        from anyblok.blok import BlokManager

        if EnvironmentManager.get("current_blok"):
            while EnvironmentManager.get("current_blok"):  # pragma: no cover
                sleep(0.1)

        EnvironmentManager.set("current_blok", self.blok)
        try:
            b = BlokManager.get(self.blok)
            b.import_declaration_module()
            self.loaded = True
        finally:
            EnvironmentManager.set("current_blok", None)

    def reload(self):
        """Reload all the imports for this module

        :exception: ImportManagerException
        """
        from anyblok.blok import BlokManager
        from anyblok.environment import EnvironmentManager
        from anyblok.registry import RegistryManager

        b = BlokManager.get(self.blok)
        if not hasattr(b, "reload_declaration_module"):
            return


        if EnvironmentManager.get("current_blok"):
            while EnvironmentManager.get("current_blok"):  # pragma: no cover
                sleep(0.1)

        EnvironmentManager.set("current_blok", self.blok)
        try:
            EnvironmentManager.set("reload", True)
            RegistryManager.init_blok(self.blok)
            b.reload_declaration_module(reload_module)
        finally:
            EnvironmentManager.set("reload", False)
            EnvironmentManager.set("current_blok", None)
