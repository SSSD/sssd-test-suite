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

import argparse
import datetime
import hashlib
import os
import re
import textwrap

import nutcli
from nutcli.commands import Command, CommandParser
from nutcli.parser import UniqueAppendAction
from nutcli.tasks import Task, TaskList

from commands.provision import ProvisionGuestsActor
from commands.vagrant import (VagrantDestroyActor, VagrantHaltActor,
                              VagrantPackageActor, VagrantPruneActor,
                              VagrantUpActor, VagrantUpdateActor)
from util.actor import TestSuiteActor


class VagrantBox(object):
    def __init__(
        self, actor, guest, project_dir,
        argv, version, linux, windows, output_dir
    ):
        self.actor = actor
        self.shell = actor.shell
        self.logger = actor.logger
        self.project_dir = project_dir

        if guest in TestSuiteActor.LinuxGuests:
            self.os = linux
            self.vagrant_file = f'{project_dir}/boxes/vagrant-files/linux'
        else:
            self.os = windows
            self.vagrant_file = f'{project_dir}/boxes/vagrant-files/windows'

        self.guest = guest
        self.version = datetime.date.today().strftime(f'%Y%m%d.{version}')
        self.box_name = f'sssd-{self.os}-{self.guest}-{self.version}.box'
        self.image_path = f'{project_dir}/pool/sssd-test-suite_{guest}.img'
        self.output_dir = output_dir
        self.argv = argv

    def _make_readable(self):
        self.shell(f'sudo chmod a+r {self.image_path}')

    def _zero_disk(self):
        ProvisionGuestsActor(parent=self.actor)(
            guests=[self.guest],
            argv=self.argv,
            playbook=f'{self.project_dir}/provision/prepare-box.yml'
        )

    def _compress_image(self):
        self.shell(f'mv -f "{self.image_path}" "{self.image_path}.bak"')
        self.shell(f'qemu-img convert -O qcow2 "{self.image_path}.bak" "{self.image_path}"')
        self.shell(f'rm -f "{self.image_path}.bak"')

    def _package_box(self, task):
        self.shell(['mkdir', '-p', self.output_dir])

        VagrantPackageActor(parent=self.actor)(
            guests=[self.guest],
            argv=['--vagrantfile', self.vagrant_file, '--output', self.box_name]
        )

        self.shell(f'mv -f "{self.box_name}" {self.output_dir}/')
        task.info(f'Box stored at {self.output_dir}/{self.box_name}')

    def get_tasklist(self):
        return TaskList(
            tag=self.guest,
            name=f'Creating {self.guest}',
            logger=self.logger
        )([
            Task('Make image readable')(
                self._make_readable
            ),
            Task('Start guest')(
                VagrantUpActor(parent=self.actor), [self.guest]
            ),
            Task('Zero out empty space on disk')(
                self._zero_disk
            ),
            Task('Halt guest')(
                VagrantHaltActor(parent=self.actor), [self.guest]
            ),
            Task('Compress image')(
                self._compress_image
            ),
            Task('Package box')(
                self._package_box
            ),
        ])

    def get_output_path(self):
        return f'{self.output_dir}/{self.box_name}'


class CreateBoxActor(TestSuiteActor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shell = nutcli.shell.Shell(env={'SSSD_TEST_SUITE_BOX': 'yes'})

    def setup_parser(self, parser):
        parser.add_argument(
            '-l', '--linux-os', action='store', type=str, dest='linux',
            help='Linux distribution name', default='linux'
        )

        parser.add_argument(
            '-w', '--windows-os', action='store', type=str, dest='windows',
            help='Windows OS name', default='windows'
        )

        parser.add_argument(
            '-o', '--output', action='store', type=str, dest='output_dir',
            help='Output directory where new boxes will '
                 'be stored (Default "{}/boxes").'.format(self.vagrant_dir),
            default='{}/boxes'.format(self.vagrant_dir)
        )

        parser.add_argument(
            '-v', '--version', action='store', type=str, dest='version',
            help='Version number appended to current date (default = 01).',
            default='01'
        )

        parser.add_argument(
            '--from-scratch', action='store_true', dest='scratch',
            help='Destroy existing guests and provision new ones.'
        )

        parser.add_argument(
            '--update', action='store_true', dest='update',
            help='Update current boxes before recreating guests.'
        )

        parser.add_argument(
            '-s', '--sequence', action='store_true', dest='sequence',
            help='Run operation on guests in sequence (one by one)'
        )

        parser.add_argument(
            'guests', nargs='*', choices=['all'] + self.AllGuests,
            action=UniqueAppendAction, default='all',
            help='Guests to box. Multiple guests can be set. (Default "all")'
        )

        parser.add_argument(
            '--argv', nargs=argparse.REMAINDER,
            help='Additional arguments passed to the ansible-playbook command'
        )

        parser.epilog = textwrap.dedent('''
        Create new vagrant boxes of selected guests.
        The boxes are named "sssd-$os-$guest-$date.$version"

        If --from-scratch is selected the guests are recreated from scratch.
        This includes several tasks:
        - Destroy current guests
        - Update current boxes (if --update is specified)
        - Bring up and provision guests

        This command may ask you for a sudo password during some steps unless
        you have passwordless sudo.

        Creating new boxes takes some time, so be patient.
        ''')

    def __call__(
        self,
        linux,
        windows,
        output_dir,
        version,
        scratch,
        update,
        sequence,
        guests,
        argv
    ):
        guests = guests if 'all' not in guests else self.AllGuests
        guests.sort()

        boxes = [VagrantBox(
            self, guest, self.project_dir, argv, version, linux, windows, output_dir
        ) for guest in guests]

        TaskList('Create Boxes', logger=self.logger)([
            TaskList(name='Provision from scratch', enabled=scratch)([
                Task('Destroy guests')(
                    VagrantDestroyActor(parent=self), guests, sequence
                ),
                Task('Update boxes', enabled=update)(
                    VagrantUpdateActor(parent=self), guests, sequence
                ),
                Task('Bring up guests')(
                    VagrantUpActor(parent=self), guests, sequence
                ),
                Task('Provision guests')(
                    ProvisionGuestsActor(parent=self), guests, argv=argv
                ),
            ]),
            *[box.get_tasklist() for box in boxes],
            Task('Output information')(self.display_output, boxes)
        ]).execute()

    def display_output(self, boxes, task):
        for box in boxes:
            task.info(f'Box written: {box.get_output_path()}')


class CreateMetadataActor(TestSuiteActor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setup_parser(self, parser):
        parser.add_argument(
            '-u', '--url', action='store', type=str, dest='url',
            help='URL where the box is available', default='http://'
        )

        parser.add_argument(
            '-o', '--output', action='store', type=str, dest='output',
            help='Output metadata file name (Default: $boxpath/$boxname.json)',
        )

        parser.add_argument(
            '-p', '--print', action='store_true', dest='print_content',
            help='Print metadata to stdout instead of writing it to file',
        )

        parser.add_argument(
            'box', help='Vagrant box file.'
        )

    def __call__(self, url, output, box, print_content):
        outfile = output
        if outfile is None:
            outfile = f'{os.path.splitext(box)[0]}.json'

        box_name = os.path.splitext(os.path.basename(box))[0]

        (box_os, box_guest, box_version) = re.findall(
            r'sssd-(.*)-(.*)-(.*)', box_name
        )[0]

        checksum = self.compute_checksum(box)
        content = self.get_metadata(
            url, outfile, box_os, box_guest, box_version, checksum
        )

        if print_content:
            print(content)
            return 0

        self.write_metadata(outfile, content)
        return 0

    def compute_checksum(self, path, block_size=65536):
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                sha256.update(block)

        return sha256.hexdigest()

    def get_metadata(self, url, outfile, os, guest, version, checksum):
        return textwrap.dedent('''
        {{
            "name": "sssd-{os}-{guest}",
            "description": "SSSD Test Suite '{os}' {guest}",
            "versions": [
                {{
                    "version": "{version}",
                    "status": "active",
                    "providers": [
                        {{
                            "name": "libvirt",
                            "url": "{url}/sssd-{os}-{guest}-{version}.box",
                            "checksum_type": "sha256",
                            "checksum": "{checksum}"
                        }}
                    ]
                }}
            ]
        }}
        ''').strip().format(
            os=os,
            guest=guest,
            version=version,
            url=url,
            checksum=checksum
        )

    @nutcli.decorators.SideEffect()
    def write_metadata(self, outfile, content):
        with open(outfile, "w") as f:
            f.write(content)


Commands = Command('box', 'Update and create boxes', CommandParser()([
    Command('update', 'Update vagrant box', VagrantUpdateActor()),
    Command('prune', 'Delete all outdated vagrant boxes', VagrantPruneActor()),
    Command('create', 'Create new vagrant box', CreateBoxActor()),
    Command('metadata', 'Create box metadata', CreateMetadataActor()),
]))
