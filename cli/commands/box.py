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

import datetime
import hashlib
import re
import subprocess
import textwrap


from commands.provision import ProvisionGuestsActor
from commands.vagrant import VagrantCommandActor
from lib.actions import UniqueAppendAction
from lib.command import Command, CommandParser
from lib.shell import Shell
from lib.task import Task
from util.actor import TestSuiteActor


class BoxInfo:
    def __init__(self, guest, root_dir, args):
        now = datetime.date.today()

        self.guest = guest
        self.version = now.strftime('%Y%m%d.{}'.format(args.version))
        self.os = args.linux if guest in TestSuiteActor.LinuxGuests else args.windows
        self.name = 'sssd-{}-{}-{}'.format(self.os, guest, self.version)
        self.boxfile = '{}.box'.format(self.name)
        self.metafile = '{}.json'.format(self.name)
        self.imagepath = '{}/pool/sssd-test-suite_{}.img'.format(root_dir, guest)

        if guest in TestSuiteActor.LinuxGuests:
            self.vagrantfile = '{}/boxes/vagrant-files/linux.vagrantfile'.format(root_dir)
        else:
            self.vagrantfile = '{}/boxes/vagrant-files/windows.vagrantfile'.format(root_dir)


class CreateBoxActor(TestSuiteActor):
    def __init__(self):
        super().__init__()
        self.shell = Shell(env={'SSSD_TEST_SUITE_BOX': 'yes'})

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
            help='URL where the resulting boxes will be stored',
            default='http://'
        )

        parser.add_argument(
            '-o', '--output', action='store', type=str, dest='output',
            help='Output directory where new boxes will '
                 'be stored (Default "{}/boxes").'.format(self.root_dir),
            default='{}/boxes'.format(self.root_dir)
        )

        parser.add_argument(
            '-v', '--version', action='store', type=str, dest='version',
            help='Version number appended to current date (default = 01).',
            default='01'
        )

        parser.add_argument(
            'guests', nargs='*', choices=['all'] + self.AllGuests,
            action=UniqueAppendAction, default='all',
            help='Guests to box. Multiple guests can be set. (Default "all")'
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

        parser.epilog = textwrap.dedent('''
        Create new vagrant boxes of selected guests.
        The boxes are named "sssd-$os-$guest-$date.$version"

        If --scratch-build is selected the guests are recreated from scratch.
        This includes several tasks:
        - Destroy current guests
        - Update current boxes (if --update is specified)
        - Bring up and provision guests

        This command may ask you for a sudo password during some steps.

        Creating new boxes takes some time, so be patient.
        ''')

    def run(self, args):
        if 'all' in args.guests:
            args.guests = self.AllGuests

        boxes = []
        for guest in args.guests:
            boxes.append(BoxInfo(guest, self.root_dir, args))

        tasks = self.tasklist('Create Boxes')

        if args.scratch:
            tasks.add('Destroy guests', self.destroy, args)
            if args.update:
                tasks.add('Update boxes', self.update, args)
            tasks.add('Bring up guests', self.up, args)
            tasks.add('Provision guests', self.provision, args)

        tasks.add_list([
            Task('Make all images readable', self.make_readable, args, boxes),
            Task('Halt guests', self.halt, args),
            Task('Zero out empty space', self.zero_disks, args, boxes),
            Task('Create boxes', self.create_boxes, args, boxes),
        ])

        if args.metadata:
            tasks.add('Create metadata', self.create_metadata, args, boxes)

        tasks.add('Finish', self.finish, args, boxes)

        tasks.run()

    def destroy(self, task, args):
        self.call(VagrantCommandActor('destroy'), args)

    def update(self, task, args):
        self.call(VagrantCommandActor('box update'), args)

    def up(self, task, args):
        self.call(VagrantCommandActor('up'), args)

    def provision(self, task, args):
        self.call(ProvisionGuestsActor(), args)

    def make_readable(self, task, args, boxes):
        for box in boxes:
            self.shell('sudo chmod a+r {}'.format(box.imagepath))

    def halt(self, task, args):
        self.call(VagrantCommandActor('halt'), args)

    def zero_disks(self, task, args, boxes):
        '''
            Zeroing disks takes lots of space because it needs to fill the
            whole space in the sparse file. Therefore it is better to do
            it one guest after another.
        '''
        for box in boxes:
            task.step('Starting guest', box.guest)
            self.vagrant(args.config, 'up', [box.guest])

            task.step('Zeroing empty space', box.guest)
            self.ansible('prepare-box.yml', True, limit=[box.guest])

            task.step('Halting guest', box.guest)
            self.vagrant(args.config, 'halt', [box.guest])

            task.step('Compressing image', box.guest)
            self.shell('mv -f "{0}" "{0}.bak"'.format(box.imagepath))
            self.shell('qemu-img convert -O qcow2 "{0}.bak" "{0}"'.format(box.imagepath))
            self.shell('rm -f "{}.bak"'.format(box.imagepath))

    def create_boxes(self, task, args, boxes):
        self.shell(['mkdir', '-p', args.output])

        for box in boxes:
            self.vagrant(args.config, 'package', [
                box.guest,
                '--vagrantfile', box.vagrantfile,
                '--output', box.boxfile
            ])

            self.shell('mv -f "{}" {}'.format(box.boxfile, args.output))
            task.step('Box stored at {}/{}'.format(args.output, box.boxfile), box.guest)

    def create_metadata(self, task, args, boxes):
        for box in boxes:
            task.step('Computing checksum', box.guest)

            if args._runner_dry_run:
                continue

            sha = self.checksum('{}/{}'.format(args.output, box.boxfile))
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
                'url': args.url,
                'sha': sha
            }).strip()

            with open('{}/{}'.format(args.output, box.metafile), "w") as f:
                f.write(meta)

    def finish(self, task, args, boxes):
        for box in boxes:
            task.step('Box written: {}/{}'.format(args.output, box.boxfile))

    def checksum(path, block_size=65536):
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                sha256.update(block)

        return sha256.hexdigest()


class PruneBoxActor(TestSuiteActor):
    def setup_parser(self, parser):
        parser.add_argument(
            '-f', '--force', action='store_true', dest='force',
            help='Destroy without confirmation even when box is in use'
        )

    def run(self, args):
        regex = re.compile(
            r"^[^']+'([^']+)' \(v([^)]+)\).*$",
            re.MULTILINE
        )
        
        vgargs = ['--force'] if args.force else []
        result = self.vagrant(args.config, 'box prune', args=vgargs, stdout=subprocess.PIPE)
        for (box, version) in regex.findall(result.stdout.decode('utf-8')):
            volume = '{box}_vagrant_box_image_{version}.img'.format(
                box=box.replace('/', '-VAGRANTSLASH-'),
                version=version
            )

            self.message('Box {}, version {} is outdated.'.format(box, version))
            self.message('  ...removing {}'.format(volume))

            self.shell('''
            sudo virsh vol-info {volume} --pool {pool} &> /dev/null
            if [ $? -ne 0 ]; then
                exit 0
            fi

            sudo virsh vol-delete {volume} --pool {pool}
            '''.format(volume=volume, pool='sssd-test-suite'))


Commands = Command('box', 'Update and create boxes', CommandParser([
    Command('update', 'Update vagrant box', VagrantCommandActor('box update')),
    Command('prune', 'Delete all outdated vagrant boxes', PruneBoxActor),
    Command('create', 'Create new vagrant box', CreateBoxActor),
]))
