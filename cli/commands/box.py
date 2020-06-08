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
import re
import subprocess
import textwrap
import nutcli

from nutcli.commands import Command, CommandParser, CommandGroup
from nutcli.parser import UniqueAppendAction
from nutcli.tasks import Task, TaskList

from commands.vagrant import VagrantUpdateActor, VagrantPruneActor, VagrantDestroyActor, VagrantHaltActor, VagrantUpActor, VagrantPackageActor
from commands.provision import ProvisionGuestsActor
from util.actor import TestSuiteActor


class BoxInfo:
    def __init__(self, guest, root_dir, kwargs):
        now = datetime.date.today()

        self.guest = guest
        self.version = now.strftime(f'%Y%m%d.{kwargs["version"]}')
        self.os = kwargs['linux'] if guest in TestSuiteActor.LinuxGuests else kwargs['windows']
        self.name = f'sssd-{self.os}-{self.guest}-{self.version}'
        self.boxfile = f'{self.name}.box'
        self.metafile = f'{self.name}.json'
        self.imagepath = f'{root_dir}/pool/sssd-test-suite_{guest}.img'

        if guest in TestSuiteActor.LinuxGuests:
            self.vagrantfile = f'{root_dir}/boxes/vagrant-files/linux.vagrantfile'
        else:
            self.vagrantfile = f'{root_dir}/boxes/vagrant-files/windows.vagrantfile'


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
            '-u', '--url', action='store', type=str, dest='url',
            help='URL where the resulting boxes will be available',
            default='http://'
        )

        parser.add_argument(
            '-o', '--output', action='store', type=str, dest='output',
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
            '--metadata', action='store_true', dest='metadata',
            help='Create vagrant metadata for new boxes.'
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

    def __call__(self, **kwargs):
        if 'all' in kwargs['guests']:
            kwargs['guests'] = self.AllGuests

        boxinfo_list = []
        for guest in kwargs['guests']:
            boxinfo_list.append(BoxInfo(guest, self.vagrant_dir, kwargs))

        TaskList('Create Boxes', logger=self.logger)([
            TaskList(name='Provision', enabled=kwargs['scratch'])([
                Task('Destroy guests', taskarg=False)(
                    VagrantDestroyActor(parent=self), kwargs['guests'], kwargs['sequence']
                ),
                Task('Update boxes', enabled=kwargs['update'], taskarg=False)(
                    VagrantUpdateActor(parent=self), kwargs['guests'], kwargs['sequence']
                ),
                Task('Bring up guests', taskarg=False)(
                    VagrantUpActor(parent=self), kwargs['guests'], kwargs['sequence']
                ),
                Task('Provision guests', taskarg=False)(
                    ProvisionGuestsActor(parent=self), kwargs['guests'], kwargs['argv']
                ),
            ]),
            Task('Make all images readable', taskarg=False)(
                self.make_readable, boxinfo_list
            ),
            Task('Halt guests', taskarg=False)(
                VagrantHaltActor(parent=self), kwargs['guests'], kwargs['sequence']
            ),
            Task('Zero out empty space')(
                self.zero_disks, boxinfo_list, kwargs['argv']
            ),
            Task('Create boxes')(
                self.create_boxes, boxes, kwargs['output']
            ),
            Task('Create metadata', enabled=kwargs['metadata'])(
                self.create_metadata, boxes, kwargs['output'], kwargs['url']
            ),
            Task('Finish')(
                self.finish, boxes, kwargs['output']
            ),
        ]).execute()

    def make_readable(self, boxinfo_list):
        for box in boxinfo_list:
            self.shell(f'sudo chmod a+r {box.imagepath}')

    def zero_disks(self, task, boxinfo_list, argv):
        """
            Zeroing disks takes lots of space because it needs to fill the
            whole space in the sparse file. Therefore it is better to do
            it one guest after another.
        """

        for box in boxinfo_list:
            task.info(f'[{box.guest}] Starting guest')
            VagrantUpActor(parent=self)([box.guest])

            task.info(f'[{box.guest}] Zeroing empty space')
            ProvisionGuestActor(parent=self)(
                guests=[box.guest],
                argv=argv,
                playbook=f'{self.ansible_dir}/prepare-box.yml')

            task.info(f'[{box.guest}] Halting guest')
            VagrantHaltActor(parent=self)([box.guest])

            task.info(f'[{box.guest}] Compressing image')
            self.shell('mv -f "{0}" "{0}.bak"'.format(box.imagepath))
            self.shell('qemu-img convert -O qcow2 "{0}.bak" "{0}"'.format(box.imagepath))
            self.shell('rm -f "{}.bak"'.format(box.imagepath))

    def create_boxes(self, task, boxinfo_list, outdir):
        self.shell(['mkdir', '-p', outdir])

        for box in boxinfo_list:
            VagrantPackageActor(parent=self)(
                guests=[box.guest],
                argv=['--vagrantfile', box.vagrantfile, '--output', box.boxfile]
            )

            self.shell(f'mv -f "{box.boxfile}" {outdir}/')
            task.info(f'[{box.guest}] Box stored at {outdir}/{box.boxfile}')

    @nutcli.decorators.SideEffect()
    def create_metadata(self, task, boxinfo_list, outdir, url):
        for box in boxinfo_list:
            task.step('Computing checksum', box.guest)

            sha = self.checksum(f'{outdir}/{box.boxfile}')
            meta = textwrap.dedent('''
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
                                "checksum": "{sha}"
                            }}
                        ]
                    }}
                ]
            }}
            ''')

            meta = meta.format({
                'os': box.os,
                'guest': box.guest,
                'version': box.version,
                'url': url,
                'sha': sha
            }).strip()

            with open(f'{outdir}/{box.metafile}', "w") as f:
                f.write(meta)

    def finish(self, task, boxinfo_list, outdir):
        for box in boxinfo_list:
            task.info(f'Box written: {outdir}/{boxfile}')

    def checksum(self, path, block_size=65536):
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                sha256.update(block)

        return sha256.hexdigest()


Commands = Command('box', 'Update and create boxes', CommandParser()([
    Command('update', 'Update vagrant box', VagrantUpdateActor()),
    Command('prune', 'Delete all outdated vagrant boxes', VagrantPruneActor()),
    Command('create', 'Create new vagrant box', CreateBoxActor()),
]))
