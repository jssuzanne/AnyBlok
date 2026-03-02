# This file is a part of the AnyBlok project
#
#    Copyright (C) 2017 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
from sqlalchemy.ext.hybrid import hybrid_method

from .plugins import ModelPluginBase


class HybridMethodPlugin(ModelPluginBase):

    def after_model_construction(self, base):
        def apply_wrapper(attr):
            def wrapper(self, *args, **kwargs):
                if self is base:
                    return getattr(super(base, self), attr)(
                        self, *args, **kwargs
                    )
                elif hasattr(self, "_aliased_insp"):
                    return getattr(
                        super(base, self._aliased_insp._target), attr
                    )(self, *args, **kwargs)
                else:
                    return getattr(super(base, self), attr)(*args, **kwargs)

            setattr(base, attr, hybrid_method(wrapper))

        for attr in base.__anyblok_structure__["hybrid_methods"]:
            apply_wrapper(attr)
