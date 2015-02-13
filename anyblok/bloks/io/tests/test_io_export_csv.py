# This file is a part of the AnyBlok project
#
#    Copyright (C) 2015 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
from anyblok.tests.testcase import BlokTestCase
from anyblok.registry import RegistryManager


class TestIOExportCSV(BlokTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestIOExportCSV, cls).setUpClass()
        RegistryManager.add_needed_bloks('io')

    def setUp(self):
        super(TestIOExportCSV, self).setUp()