# -*- coding: utf-8 -*-
#
#    Authors:
#        Pavel Březina <pbrezina@redhat.com>
#
#    Copyright (C) 2019 Red Hat
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import json
import re
import textwrap

from nutcli.commands import Command, CommandGroup, CommandParser
from nutcli.parser import UniqueAppendAction
from nutcli.tasks import Task, TaskList

from util.actor import TestSuiteActor
from util.vgcloud import VagrantCloud


class CloudActor(TestSuiteActor):
    def __init__(self):
        super().__init__()

        self.cloud_config_file = '{}/vg-cloud.json'.format(self.vagrant_dir)

    def setup_parser(self, parser):
        parser.add_argument(
            '-u', '--username', action='store', type=str, dest='username',
            default=None, help='Vagrant cloud username or organization name '
            'where boxes are stored'
        )

        parser.add_argument(
            '-t', '--token', action='store', type=str, dest='token',
            default=None, help='Vagrant cloud authentication token'
        )

    def get_credentials(self, username, token):
        try:
            with open(self.cloud_config_file) as file:
                data = json.load(file)

            username = data.get('username', username)
            token = data.get('token', token)
        except FileNotFoundError:
            pass
        except Exception:
            raise

        return (username, token)

    def save_credentials(self, username, token):
        with open(self.cloud_config_file, "w") as f:
            f.write(json.dumps({
                'username': username,
                'token': token
            }))

    def get_cloud_api(self, username, token):
        (username, token) = self.get_credentials(username, token)
        return VagrantCloud(username, token)


class CloudGetCredentialsActor(CloudActor):
    def setup_parser(self, parser):
        pass

    def __call__(self):
        (username, token) = self.get_credentials(None, None)
        print('Username: {}'.format(username))
        print('Token: {}'.format(token))


class CloudSetCredentialsActor(CloudActor):
    def __call__(self, username, token):
        self.save_credentials(username, token)


class CloudListActor(CloudActor):
    def __call__(self, username, token):
        api = self.get_cloud_api(username, token)
        for box in api.list_boxes():
            print('- {:50s} ({})'.format(box.tag, box.version))


class CloudPruneActor(CloudActor):
    def setup_parser(self, parser):
        super().setup_parser(parser)

        parser.add_argument(
            '-k', '--keep', action='store', type=int, dest='keep',
            default=2, help='How many versions should be kept (Default 2)'
        )

        parser.description = textwrap.dedent('''
        This will iterate over all available boxes and delete outdated versions.
        Only last two versions (by default, can be set with --keep) will be
        kept.
        ''')

    def __call__(self, username, token, keep=2):
        api = self.get_cloud_api(username, token)
        for box in api.list_boxes():
            versions = api.list_versions(box.name)
            for version in versions[:-keep]:
                self.info(f'Removing {box.name} {version}')
                api.version_delete(box.name, version)


class CloudUploadActor(CloudActor):
    def setup_parser(self, parser):
        super().setup_parser(parser)

        parser.add_argument(
            'boxes', nargs='+', action=UniqueAppendAction,
            help='Path to vagrant boxes that should be uploaded to cloud.'
        )

        parser.epilog = textwrap.dedent('''
        The box files names must be in the same format as is created by
        'box create' command. That is:
          sssd-$os-$guest-$date.$version.box

        For example:
          sssd-fedora30-client-20190530.01.box
        ''')

    def __call__(self, username, token, boxes):
        api = self.get_cloud_api(username, token)
        tasks = TaskList('Upload Box', logger=self.logger)
        for box_file in boxes:
            info = self.get_box_info(box_file)
            tasks.append(
                Task('Creating box {name} ({version})'.format(**info))(
                    self.upload_task, api, box_file, info
                )
            )
        tasks.execute()

    def upload_task(self, api, box_file, info):
        self.create_container(api, info)
        self.upload(api, info, box_file)

    def create_container(self, api, info):
        api.box_create(
            info['name'], 'sssd-test-suite: {os} {guest} machine'.format(**info)
        )

        api.version_create(
            info['name'], info['version'],
            'See: https://github.com/SSSD/sssd-test-suite'
        )

        api.provider_create(info['name'], info['version'], 'libvirt')

    def upload(self, api, info, box_file):
        api.provider_upload(info['name'], info['version'], 'libvirt', box_file)
        api.version_release(info['name'], info['version'])

    def get_box_info(self, box_file):
        matches = re.finditer(
            r'^.*/?sssd-(?P<os>.+)-(?P<guest>\w+)-(?P<version>[\d\.]+)\.box$',
            box_file,
            re.MULTILINE
        )

        for match in matches:
            d = match.groupdict()
            d['name'] = '{os}-{guest}'.format(**d)
            return d

        return None


Commands = Command('cloud', 'Access vagrant cloud', CommandParser(
    description=textwrap.dedent('''
    These commands access vagrant cloud at https://app.vagrantup.com.

    All commands takes --username and --token parameters that represents your
    username and access token. You can use 'set-creds' command to save
    these parameters in ./sssd-test-suite/vg-cloud.json. Please, keep in mind
    that authentication token is stored in plain text.
    '''))([
        CommandGroup('Cloud Operations')([
            Command('list', 'List boxes stored in vagrant cloud', CloudListActor()),
            Command('upload', 'Upload boxes to vagrant cloud', CloudUploadActor()),
            Command('prune', 'Delete outdated versions of available boxes', CloudPruneActor()),
        ]),
        CommandGroup('Local Credentials')([
            Command('get-creds', 'Print your current credentials', CloudGetCredentialsActor()),
            Command('set-creds', 'Save your vagrant cloud token and username', CloudSetCredentialsActor()),
        ])
    ])
)
