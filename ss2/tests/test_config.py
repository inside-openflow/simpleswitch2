# Copyright (c) 2016 Noviflow
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"Test the config loader"

import unittest
import io
import six
from textwrap import dedent
from ss2 import config

if six.PY2:
    import ConfigParser as configparser
else:
    import configparser

# pylint: disable=C0111

class ParseTypesTestCase(unittest.TestCase):
    def test_int(self):
        items = [("foo", "12345"), ("bar", "0xff")]
        parsed = config.parse_types(items)
        self.assertEqual(parsed.foo, 12345)
        self.assertEqual(parsed.bar, 0xff)

    def test_float(self):
        items = [("foo", "1.24"), ("bar", "invalid.float")]
        parsed = config.parse_types(items)
        self.assertAlmostEqual(parsed.foo, 1.24)
        self.assertEqual(parsed.bar, "invalid.float")

    def test_bool(self):
        items = [("foo", "true"), ("bar", "no")]
        parsed = config.parse_types(items)
        self.assertIs(parsed.foo, True)
        self.assertIs(parsed.bar, False)

    def test_dictkey(self):
        items = [
            ("foo.bar", "123"),
            ("foo.baz", "no"),
        ]
        parsed = config.parse_types(items)
        self.assertEqual(parsed.foo.bar, 123)
        self.assertEqual(parsed.foo.baz, False)

        items = [
            ("foo.bar", "123"),
            ("foo", "other")
        ]
        parsed = config.parse_types(items)
        self.assertEqual(parsed.foo, "other")

        items = [
            ("foo.bar", "123"),
            ("foo.baz", "no"),
            ("foo", "other"), # resets the dict
            ("foo.bar", "321")
        ]
        parsed = config.parse_types(items)
        self.assertEqual(parsed.foo.bar, 321)
        self.assertFalse("baz" in parsed.foo)

class SubsectionTestCase(unittest.TestCase):
    def setUp(self):
        # Example intentionally not in order
        example = """
        [ACL]
        foo.baz: ACL
        foo.acl: ACL
        [ACL/Rule A]
        foo.bar: ACL-Rule-A
        [ACL/Rule B]
        foo.baz: ACL-Rule-B
        [DEFAULTS]
        foo.bar: Default
        foo.baz: Default
        [Deep/Subsection/Without/Parents]
        foo.baz: Deep
        [ACL/DEFAULTS]
        foo.bar: ACL-Default
        foo.baz: ACL-Default
        """

        self.parser = config.ConfigParser()
        if six.PY2:
            self.parser.readfp(io.BytesIO(dedent(example)))
        else:
            self.parser.read_string(example)

    def test_no_subsection(self):
        items = config.get_section(self.parser, "ACL")
        c = config.parse_types(items)
        self.assertEqual(c.foo.bar, "Default")
        self.assertEqual(c.foo.baz, "ACL")

    def test_shallow_subsection(self):
        items = config.get_section(self.parser, "ACL/Rule A")
        c = config.parse_types(items)
        self.assertEqual(c.foo.bar, "ACL-Rule-A")
        self.assertEqual(c.foo.baz, "ACL-Default")

        items = config.get_section(self.parser, "ACL/Rule B")
        c = config.parse_types(items)
        self.assertEqual(c.foo.bar, "ACL-Default")
        self.assertEqual(c.foo.baz, "ACL-Rule-B")

    def test_deep_subsection(self):
        items = config.get_section(self.parser, "Deep/Subsection/Without/Parents")
        c = config.parse_types(items)
        self.assertEqual(c.foo.bar, "Default")
        self.assertEqual(c.foo.baz, "Deep")

    def test_no_section(self):
        with self.assertRaises(configparser.NoSectionError):
            config.get_section(self.parser, "Deep/Subsection")

    def test_get_subsections(self):
        subs = config.get_subsections(self.parser, "ACL")
        self.assertEqual(len(subs), 2)
        self.assertNotIn("ACL/DEFAULTS", subs)

    def test_get_subsections_deep(self):
        subs = config.get_subsections(self.parser, "Deep/Subsection")
        self.assertEqual(len(subs), 0)

        subs = config.get_subsections(self.parser, "Deep/Subsection", True)
        self.assertEqual(len(subs), 1)
        self.assertIn("Deep/Subsection/Without/Parents", subs)
