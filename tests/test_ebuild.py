#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    test_ebuild.py
    ~~~~~~~~~~~~~~
    
    ebuild test suite
    
    :copyright: (c) 2013 by Jauhien Piatlicki
    :license: GPL-2, see LICENSE for more details.
"""

import collections
import os
import unittest

from g_sorcery.compatibility import TemporaryDirectory
from g_sorcery.g_collections import Package
from g_sorcery.ebuild import EbuildGeneratorFromFile, DefaultEbuildGenerator
from g_sorcery.package_db import PackageDB

from tests.base import BaseTest


Layout = collections.namedtuple("Layout",
    ["vars_before_inherit", "inherit",
     "vars_after_description", "vars_after_keywords"])

class TestEbuildGenerator(BaseTest):

    ebuild_data = {"herd": ["testers", "crackers"],
                   'maintainer': [{'email': 'test@example.com',
                                   'name': 'tux'}],
                   "longdescription": "very long description here",
                   "use": {"flag": {"use1": "testing use1", "use2": "testing use2"}},
                   "homepage": "example.com",
                   "description": "testing ebuild",
                   "array": "(a b c d)"}
    package = Package("app-test", "metadata_tester", "0.1")

    def setUp(self):
        super(TestEbuildGenerator, self).setUp()
        self.pkg_db = PackageDB(self.tempdir.name)
        self.pkg_db.add_category("app-test")
        self.pkg_db.add_package(self.package, self.ebuild_data)

    def test_ebuild_generator_from_file(self):
        template = os.path.join(self.tempdir.name, "test.tmpl")
        os.system("echo 'TEST_SUBST=%(array)s' > " + template)
        
        ebuild_g = EbuildGeneratorFromFile(self.pkg_db, template)
        ebuild = ebuild_g.generate(self.package)
        self.assertEqual(ebuild, ['TEST_SUBST=(a b c d)'])

    def test_default_ebuild_generator(self):
        vars_before_inherit = \
          [{"name":"test_raw_value", "value":"raw_value", "raw":True},
           {"name":"test_value", "value":"value"}]

        inherit = ["g-test"]
        
        vars_after_description = \
          ["homepage"]

        vars_after_keywords = \
          [{"name":"array"},
           {"name":"array", "raw":True}]

        layout = Layout(vars_before_inherit,
                    inherit, vars_after_description, vars_after_keywords)

        ebuild_g = DefaultEbuildGenerator(self.pkg_db, layout)
        ebuild = ebuild_g.generate(self.package)
        self.assertEqual(ebuild, ['# automatically generated by g-sorcery',
                                  '# please do not edit this file', '',
                                  'EAPI=5', '',
                                  'TEST_RAW_VALUE=raw_value', 'TEST_VALUE="value"', '',
                                  'inherit g-test', '',
                                  'DESCRIPTION="testing ebuild"', '',
                                  'HOMEPAGE="example.com"', '',
                                  'SLOT="0"', 'KEYWORDS="~amd64 ~x86"', '',
                                  'ARRAY="(a b c d)"', 'ARRAY=(a b c d)', ''])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(TestEbuildGenerator('test_ebuild_generator_from_file'))
    suite.addTest(TestEbuildGenerator('test_default_ebuild_generator'))
    return suite