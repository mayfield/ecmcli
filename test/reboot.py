import unittest.mock
from ecmcli.commands import reboot

class ArgSanity(unittest.TestCase):

    def setUp(self):
        api = unittest.mock.Mock()
        fake = dict(name='foo', id='1')
        api.get_by_id_or_name.return_value = fake
        api.get_pager.return_value = [fake]
        self.cmd = reboot.Reboot(api=api)

    def runcmd(self, args):
        args = self.cmd.argparser.parse_args(args.split())
        self.cmd.run(args)

    def test_router_single_ident_arg(self):
        self.runcmd('reboot foo -f')
        self.cmd.api.get_by_id_or_name.assert_called_with('routers', 'foo')
        self.cmd.api.put.asssert_called_with(id='1')

    def test_router_multi_ident_arg(self):
        self.runcmd('reboot foo bar -f')
        self.cmd.api.get_by_id_or_name.assert_any_call('routers', 'foo')
        self.cmd.api.get_by_id_or_name.assert_any_call('routers', 'bar')
        self.cmd.api.put.asssert_called_with(id='1')

    def test_router_no_ident_arg(self):
        self.runcmd('reboot -f')
        self.cmd.api.put.asssert_called_with(id='1')
