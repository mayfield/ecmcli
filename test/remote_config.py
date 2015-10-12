
import copy
import unittest
from ecmcli.commands import base, remote


class ConfigData(unittest.TestCase):

    def test_todict_noconv(self):
        for x in ({}, 0, None, 1, "", True, False, 0.0, -1, -1.1, 1.1, {1:1}):
            self.assertEqual(base.todict(x), copy.deepcopy(x))

    def test_todict_nesting(self):
        case = {1: {2: 2}}
        self.assertEqual(base.todict(case), copy.deepcopy(case))

    def test_todict_listconv(self):
        case = {1: ['aaa', 'bbb']}
        result = {1: {0: 'aaa', 1: 'bbb'}}
        self.assertEqual(base.todict(case), result)

    def test_todict_listconv_nested(self):
        case = {1: [{11: ['l2a', 'l2b']}, 'bbb']}
        result = {1: {0: {11: {0: 'l2a', 1: 'l2b'}}, 1: 'bbb'}}
        self.assertEqual(base.todict(case), result)

    def test_todict_liststart(self):
        case = ["aaa", "bbb"]
        result = {0: 'aaa', 1: 'bbb'}
        self.assertEqual(base.todict(case), result)

    def test_todict_multi_dim_list(self):
        case = [["aaa", "bbb"]]
        result = {0:{0: 'aaa', 1: 'bbb'}}
        self.assertEqual(base.todict(case), result)
        case = [["aaa", "bbb"], 1]
        result = {0:{0: 'aaa', 1: 'bbb'}, 1:1}
        self.assertEqual(base.todict(case), result)
        case = [["aaa", "bbb"], []]
        result = {0:{0: 'aaa', 1: 'bbb'}, 1:{}}
        self.assertEqual(base.todict(case), result)
        case = [[['a']]]
        result = {0:{0:{0:'a'}}}
        self.assertEqual(base.todict(case), result)
        case = [[[]]]
        result = {0:{0:{}}}
        self.assertEqual(base.todict(case), result)
