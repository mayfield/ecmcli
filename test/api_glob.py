
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

    def test_simple_set(self):
        filters, test = self.glob('foo', '{a,bb,ccc}')
        self.assertFalse(filters)
        self.assertTrue(test(dict(foo='a')))
        self.assertTrue(test(dict(foo='bb')))
        self.assertTrue(test(dict(foo='ccc')))
        self.assertFalse(test(dict(foo='accc')))
        self.assertFalse(test(dict(foo='ccca')))
        self.assertFalse(test(dict(foo='accca')))
        self.assertFalse(test(dict(foo='zccc')))
        self.assertFalse(test(dict(foo='zcccz')))
        self.assertFalse(test(dict(foo='aa')))
        self.assertFalse(test(dict(foo='aaa')))
        self.assertFalse(test(dict(foo='b')))
        self.assertFalse(test(dict(foo='bbb')))
        self.assertFalse(test(dict(foo='bbbb')))
        self.assertFalse(test(dict(foo='c')))
        self.assertFalse(test(dict(foo='cc')))
        self.assertFalse(test(dict(foo='cccc')))
        self.assertFalse(test(dict(foo='ccccc')))
        self.assertFalse(test(dict(foo='cccccc')))
        self.assertFalse(test(dict(foo='ccccccc')))

    def test_wildprefix_set_suffix(self):
        filters, test = self.glob('foo', '*{a,bb}')
        self.assertFalse(filters)
        self.assertTrue(test(dict(foo='a')))
        self.assertTrue(test(dict(foo='bb')))
        self.assertTrue(test(dict(foo='aa')))
        self.assertTrue(test(dict(foo='bbb')))
        self.assertTrue(test(dict(foo='abb')))
        self.assertTrue(test(dict(foo='ba')))
        self.assertTrue(test(dict(foo='Za')))
        self.assertFalse(test(dict(foo='accc')))
        self.assertFalse(test(dict(foo='b')))
        self.assertFalse(test(dict(foo='c')))

    def test_wildsuffix_set_prefix(self):
        filters, test = self.glob('foo', '{a,bb}*')
        self.assertFalse(filters)
        self.assertTrue(test(dict(foo='a')))
        self.assertTrue(test(dict(foo='bb')))
        self.assertTrue(test(dict(foo='aa')))
        self.assertTrue(test(dict(foo='bbb')))
        self.assertTrue(test(dict(foo='abb')))
        self.assertTrue(test(dict(foo='bba')))
        self.assertTrue(test(dict(foo='aZ')))
        self.assertFalse(test(dict(foo='ccca')))
        self.assertFalse(test(dict(foo='b')))
        self.assertFalse(test(dict(foo='c')))

    def test_nested_expr_with_set(self):
        filters, test = self.glob('foo', '{a,b?b}')
        self.assertFalse(filters)
        self.assertTrue(test(dict(foo='a')))
        self.assertTrue(test(dict(foo='bbb')))
        self.assertTrue(test(dict(foo='bab')))
        self.assertTrue(test(dict(foo='bZb')))
        self.assertTrue(test(dict(foo='b?b')))
        self.assertFalse(test(dict(foo='ab')))
        self.assertFalse(test(dict(foo='abbb')))
        self.assertFalse(test(dict(foo='bbba')))
