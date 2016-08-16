"""
Work with the ECM Router Apps toolset.
"""

import collections
import shellish
import time
from . import base
from .. import ui

versions_res = 'router_sdk_app_versions'
deploy_res = 'router_sdk_group_bindings'


class CommonMixin(object):

    def get_app(self, name_ver, **kwargs):
        """ Get the app version object for a `name:version` identifier. """
        name, version = name_ver.split(':', 1)
        major, minor = version.split('.', 1)
        app = self.api.get(versions_res, app__name=name, major_version=major,
                           minor_version=minor, **kwargs)
        if not app:
            raise SystemExit("Application %s not found" % name_ver)
        return app[0]

    def add_app_argument(self, *keys, **options):
        options.setdefault('metavar', 'APP:VERSION')
        options.setdefault('help', 'The name:version identifier of an app '
                           'version')
        return self.add_argument(*keys, **options)

    def app_ident(self, app_version):
        name = app_version['app'] and app_version['app']['name']
        return '%s:%d.%d' % (name, app_version['major_version'],
                             app_version['minor_version'])


class List(CommonMixin, base.ECMCommand):
    """ List uploaded router apps. """

    name = 'ls'
    expands = (
        'account',
        'app'
    )

    def setup_args(self, parser):
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        versions = self.api.get_pager(versions_res,
                                      expand=','.join(self.expands))
        fields = collections.OrderedDict((
            ('Version ID', 'id'),
            ('App ID', lambda x: x['app'] and x['app']['id']),
            ('App Ident', self.app_ident),
            ('Created', lambda x: ui.time_since(x['created_at']) + ' ago'),
            ('State', 'state'),
        ))
        with self.make_table(headers=fields.keys(),
                             accessors=fields.values()) as t:
            t.print(versions)


class Examine(CommonMixin, base.ECMCommand):
    """ Examine a specific router app. """

    name = 'examine'
    expands = (
        'account',
        'app',
        'groups'
    )

    def setup_args(self, parser):
        self.add_app_argument('appident')
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        app = self.get_app(args.appident, expand=','.join(self.expands))
        routers = self.api.get_pager(urn=app['routers'])
        appfields = app['app'] or {}
        with self.make_table(columns=[20, None], column_padding=1) as t:
            t.print([
                ('Version ID', app['id']),
                ('App ID', appfields.get('id')),
                ('Name', appfields.get('name')),
                ('UUID', appfields.get('uuid')),
                ('Description', appfields.get('description')),
                ('Version', '%d.%d' % (app['major_version'],
                                       app['minor_version'])),
                ('Account', app['account']['name']),
                ('Created', app['created_at']),
                ('Updated', app['updated_at']),
                ('State', '%s %s' % (app['state'],
                                     app.get('state_details') or '')),
                ('Groups', ', '.join(x['name'] for x in app['groups'])),
                ('Routers', ', '.join(x['name'] for x in routers)),
            ])


class Upload(base.ECMCommand):
    """ Upload a new application package. """

    name = 'upload'
    use_pager = False

    def setup_args(self, parser):
        self.add_file_argument('package', mode='rb')
        super().setup_args(parser)

    def run(self, args):
        with args.package as f:
            url = self.api.uri + self.api.urn
            session = self.api.adapter.session
            del session.headers['content-type']
            resp = session.post('%s/%s/' % (url, versions_res), files={
                "archive": f
            }).json()
        if not resp['success']:
            raise SystemExit(resp['message'])
        appid = resp['data']['id']
        print("Checking upload: ", end='', flush=True)
        for i in range(10):
            app = self.api.get_by('id', versions_res, appid)
            if app['state'] != 'uploading':
                break
            time.sleep(0.200)
        else:
            raise SystemExit("Timeout waiting for upload to complete")
        if app['state'] == 'error':
            shellish.vtmlprint("<red>ERROR</red>")
            self.api.delete(versions_res, app['id'])
            raise SystemExit(app['state_details'])
        elif app['state'] == 'ready':
            shellish.vtmlprint("<green>READY</green>")
        else:
            shellish.vtmlprint("<yellow>%s</yellow>" % app['state'].upper())
            if app['state_details']:
                print(app.get('state_details'))


class Remove(CommonMixin, base.ECMCommand):
    """ Remove an application version. """

    name = 'rm'
    use_pager = False

    def setup_args(self, parser):
        self.add_app_argument('appident')
        self.add_argument('-f', '--force', action='store_true',
                          help='Do not prompt for confirmation.')
        super().setup_args(parser)

    def run(self, args):
        app = self.get_app(args.appident)
        if not args.force:
            self.confirm("Delete %s (%s)?" % (args.appident, app['id']))
        self.api.delete(versions_res, app['id'])


class Deploy(CommonMixin, base.ECMCommand):
    """ Show and manage application deployments. """

    name = 'deploys'
    expands = (
        'app_version.app',
        'group'
    )

    def setup_args(self, parser):
        self.add_subcommand(DeployInstall)
        self.add_subcommand(DeployRemove)
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        deploys = self.api.get_pager(deploy_res,
                                     expand=','.join(self.expands))
        fields = collections.OrderedDict((
            ('ID', 'id'),
            ('Created', lambda x: ui.time_since(x['created_at']) + ' ago'),
            ('Group', lambda x: x['group']['name']),
            ('App Ident', lambda x: self.app_ident(x['app_version']))
        ))
        with self.make_table(headers=fields.keys(),
                             accessors=fields.values()) as t:
            t.print(deploys)


class DeployInstall(CommonMixin, base.ECMCommand):
    """ Install an application to a group of routers. """

    name = 'install'
    use_pager = False

    def setup_args(self, parser):
        self.add_app_argument('appident')
        self.add_group_argument('group', metavar='GROUP_ID_OR_NAME')
        super().setup_args(parser)

    def run(self, args):
        app = self.get_app(args.appident)
        group = self.api.get_by_id_or_name('groups', args.group)
        self.api.post(deploy_res, {
            "app_version": app['resource_uri'],
            "group": group['resource_uri'],
            "account": group['account']
        })


class DeployRemove(CommonMixin, base.ECMCommand):
    """ Remove an application from a group of routers. """

    name = 'rm'
    use_pager = False

    def setup_args(self, parser):
        crit = parser.add_mutually_exclusive_group(required=True)
        self.add_argument('--deploy-id', parser=crit, metavar='DEPLOY_ID',
                          complete=self.make_completer(deploy_res, 'id'))
        self.add_app_argument('--app-ident', parser=crit)
        self.add_group_argument('--group', metavar='GROUP_NAME_OR_ID',
                                help='Only remove an app from this group')
        self.add_argument('-f', '--force', action='store_true',
                          help='Do not prompt for confirmation.')
        super().setup_args(parser)

    def run(self, args):
        if args.deploy_id:
            if not args.force:
                self.confirm("Delete %s?" % args.deploy_id)
            self.api.delete(deploy_res, args.deploy_id)
        else:
            app = self.get_app(args.app_ident)
            filters = {
                "app_version": app['id']
            }
            if args.group:
                group = self.api.get_by_id_or_name('groups', args.group)
                filters['group'] = group['id']
            deploys = list(self.api.get_pager(deploy_res, **filters))
            if not deploys:
                raise SystemExit("No deploys to remove")
            if not args.force:
                self.confirm("Delete %s?" % ', '.join(x['id'] for x in deploys))
            for x in deploys:
                self.api.delete(deploy_res, x['id'])


class Apps(base.ECMCommand):
    """ View and edit Router Applications (router-sdk). """

    name = 'apps'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(List, default=True)
        self.add_subcommand(Examine)
        self.add_subcommand(Upload)
        self.add_subcommand(Remove)
        self.add_subcommand(Deploy)

command_classes = [Apps]
