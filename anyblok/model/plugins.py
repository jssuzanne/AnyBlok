# This file is a part of the AnyBlok project
#
#    Copyright (C) 2017 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
from logging import getLogger

from ..pkg_metadata import iter_entry_points

logger = getLogger(__name__)


def get_model_plugins(registry):
    res = []
    for i in iter_entry_points("anyblok.model.plugin"):
        logger.info("AnyBlok Load model plugin: %r", i)
        res.append(i.load()(registry))

    return res


class ModelPluginBase:
    def __init__(self, registry):
        self.registry = registry

    # def init(self, properties):
    #     """ Initialise the transform properties

    #     :param properties: the properties declared in the model
    #     """

    # def before_model_construction(self, properties):
    #     """Do some action before the construction of the Model

    #     :param properties: the properties of the model
    #     """

    # def after_model_construction(self, base)
    #     """Do some action with the constructed Model

    #     :param base: the Model class
    #     """
