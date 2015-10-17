
import unittest
from ecmcli import api


class GlobFilters(unittest.TestCase):

    def setUp(self):
        self.api = api.ECMService()
        self.glob = self.api.glob_field

    def test_exact(self):
        filters, test = self.glob('foo', 'bar')
        self.assertEqual(filters, {"foo__exact": 'bar'})
        self.assertTrue(test(dict(foo='bar')))
        self.assertFalse(test(dict(foo='baz')))

    def test_just_star(self):
        filters, test = self.glob('foo', '*')
        self.assertFalse(filters)
        self.assertTrue(test(dict(foo='bar')))
        self.assertTrue(test(dict(foo='')))

    def test_just_qmark(self):
        filters, test = self.glob('foo', '?')
        self.assertFalse(filters)
        self.assertFalse(test(dict(foo='no')))
        self.assertTrue(test(dict(foo='y')))

    def test_prefix_with_star_tail(self):
        filters, test = self.glob('foo', 'bar*')
        self.assertEqual(filters, {"foo__startswith": 'bar'})
        self.assertFalse(test(dict(foo='foobar')))
        self.assertTrue(test(dict(foo='barfoo')))
        self.assertTrue(test(dict(foo='bar')))

    def test_prefix_with_star_head(self):
        filters, test = self.glob('foo', '*bar')
        self.assertEqual(filters, {"foo__endswith": 'bar'})
        self.assertTrue(test(dict(foo='foobar')))
        self.assertFalse(test(dict(foo='barfoo')))
        self.assertTrue(test(dict(foo='bar')))

    def test_prefix_with_star_border(self):
        filters, test = self.glob('foo', '*bar*')
        self.assertFalse(filters)
        self.assertFalse(test(dict(foo='ba')))
        self.assertFalse(test(dict(foo='baz')))
        self.assertTrue(test(dict(foo='bar')))
        self.assertTrue(test(dict(foo='foobar')))
        self.assertTrue(test(dict(foo='barfoo')))
        self.assertTrue(test(dict(foo='foobarbaz')))
