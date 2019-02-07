#!/usr/bin/python3
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

import os
import re
import sys
import shutil
import hashlib
import argparse
import datetime
import textwrap
import subprocess

from utils import *

if len(sys.argv) >= 2 and sys.argv[1] != 'provision-host':
    from vagrant_cloud import *


class Command:
    def __init__(self, subparser, name, help):
        self.dir = os.path.dirname(os.path.realpath(__file__)) + '/..'
        self.pool = '%s/pool' % self.dir
        self.shell = Shell(self.dir)
        self.vagrant = Vagrant(self.dir)
        self.ansible = Ansible(self.dir)
        self.linux = ['ipa', 'ldap', 'client']
        self.windows = ['ad', 'ad-child']
        self.guests = self.windows + self.linux

        self.name = name
        self.parser = subparser.add_parser(name, help=help, description=help)
        self.parser.set_defaults(func=self.run)

    def run(self, args, params=[]):
        raise NotImplementedError()


class BasicVagrantCommand(Command):
    def __init__(self, subparser, name, help, command=None):
        super().__init__(subparser, name, help)

        self.command = [self.name] if command is None else command

        self.parser.add_argument(
            '--all', action='store_const', dest='guests',
            const=self.guests, help='Run command on all machines (default)'
        )

        self.parser.add_argument(
            '--ad', action=UniqueAppendConstAction, dest='guests',
            const='ad', help='Run command on AD machine'
        )

        self.parser.add_argument(
            '--ad-child', action=UniqueAppendConstAction, dest='guests',
            const='ad-child', help='Run command on AD child machine'
        )

        self.parser.add_argument(
            '--ipa', action=UniqueAppendConstAction, dest='guests',
            const='ipa', help='Run command on IPA machine'
        )

        self.parser.add_argument(
            '--ldap', action=UniqueAppendConstAction, dest='guests',
            const='ldap', help='Run command on LDAP machine'
        )

        self.parser.add_argument(
            '--client', action='append_const', dest='guests',
            const='client', help='Run command on client machine'
        )

        self.parser.add_argument(
            '-s', '--sequence', action='store_true', dest='sequence',
            help='Run operation on guests in sequence (one by one)'
        )

    def run(self, args, params=[]):
        runon = []

        if args.guests is None:
            args.guests = self.guests

        for guest in args.guests:
            runon.append(guest)

        if args.sequence:
            for guest in runon:
                self.vagrant.run(self.command + [guest], params)
            return

        self.vagrant.run(self.command + runon, params)


class SSHVagrantCommand(Command):
    def __init__(self, subparser, name, help):
        super().__init__(subparser, name, help)

        self.parser.add_argument(
            'guest',
            type=str,
            choices=self.linux
        )

    def run(self, args, params=[]):
        self.vagrant.run([self.name] + [args.guest], params)


class RDPVagrantCommand(Command):
    def __init__(self, subparser, name, help):
        super().__init__(subparser, name, help)

        self.parser.add_argument(
            'guest',
            type=str,
            choices=self.windows
        )

    def run(self, args, params=[]):
        self.vagrant.run([self.name] + [args.guest], params)


class ProvisionHostCommand(Command):
    def __init__(self, subparser, name, help):
        super().__init__(subparser, name, help)

        self.parser.add_argument(
            '-p', '--pool', action='store', type=str, dest='pool',
            help='Location of libvirt storage pool that '
                 'will be named as "sssd-test-suite"',
            required=True
        )

    def run(self, args, params=[]):
        if not self.installAnsible():
            print("Please, install 'ansible' first.")
            return

        params.append('--extra-vars')
        params.append('LIBVIRT_STORAGE=%s' % args.pool)
        self.ansible.run('prepare-host.yml', ['localhost'], params)

    def installAnsible(self):
        if self.shell.isCommandAvailable('ansible-playbook'):
            return True

        return self.shell.installCommand('ansible')


class ProvisionGuestsCommand(Command):
    def __init__(self, subparser, name, help):
        super().__init__(subparser, name, help)

        self.parser.add_argument(
            '--all', action='store_true', dest='all',
            help='Provision all machines (default)'
        )

        self.parser.add_argument(
            '--ad', action=UniqueAppendConstAction, dest='guests',
            const='ad', help='Provision AD machine'
        )

        self.parser.add_argument(
            '--ad-child', action=UniqueAppendConstAction, dest='guests',
            const='ad-child', help='Provision AD child machine'
        )

        self.parser.add_argument(
            '--ipa', action=UniqueAppendConstAction, dest='guests',
            const='ipa', help='Provision IPA machine'
        )

        self.parser.add_argument(
            '--ldap', action=UniqueAppendConstAction, dest='guests',
            const='ldap', help='Provision LDAP machine'
        )

        self.parser.add_argument(
            '--client', action='append_const', dest='guests',
            const='client', help='Provision client machine'
        )

        self.parser.add_argument(
            '-e', '--enroll', action='store_true', dest='enroll',
            help='Enroll client to all domains'
        )

    def run(self, args, params=[]):
        if not args.enroll:
            params.append('--skip-tags=enroll-all')

        limit = ['all'] if args.guests is None else args.guests
        self.ansible.run('prepare-guests.yml', limit, params)


class EnrollCommand(Command):
    def __init__(self, subparser, name, help):
        super().__init__(subparser, name, help)

    def run(self, args, params=[]):
        self.ansible.run('enroll.yml', ['all'], params)


class PruneBoxCommand(Command):
    def __init__(self, subparser, name, help):
        super().__init__(subparser, name, help)

        self.re = re.compile(
            "^[^']+'([^']+)' \(v([^)]+)\).*$",
            re.MULTILINE
        )

    def run(self, args, params=[]):
        result = self.vagrant.run(
            ['box', 'prune'],
            params,
            stdout=subprocess.PIPE
        )

        for (box, version) in self.re.findall(result.stdout.decode('utf-8')):
            imgfile = '%s_vagrant_box_image_%s.img' % (
                box.replace('/', '-VAGRANTSLASH-'),
                version
            )
            imgfile = '%s/%s' % (self.pool, imgfile)

            print('Box %s, version %s is outdated.' % (box, version))
            print('   removing %s' % imgfile)

            if os.path.exists(imgfile):
                os.remove(imgfile)


class CreateBoxCommand(Command):
    class Task:
        def __init__(self, name, guests, task):
            self.name = name
            self.guests = guests
            self.task = task

    class Box:
        def __init__(self, createbox, guest, args):
            now = datetime.date.today()

            self.version = now.strftime('%Y%m%d.{}'.format(args.version))
            self.os = args.linux if guest in createbox.linux else args.windows
            self.name = 'sssd-%s-%s-%s' % (self.os, guest, self.version)
            self.file = '%s.box' % self.name
            self.outdir = args.output
            self.path = '%s/%s' % (self.outdir, self.file)
            self.metapath = '%s/%s.json' % (self.outdir, self.name)
            self.img = '%s/sssd-test-suite_%s.img' % (createbox.pool, guest)
            self.backup = '%s.bak' % self.img

            if guest in createbox.linux:
                self.vgfile = '%s/boxes/vagrant-files/linux.vagrantfile'
            else:
                self.vgfile = '%s/boxes/vagrant-files/windows.vagrantfile'

            self.vgfile = self.vgfile % createbox.dir

        def checksum(self, block_size=65536):
            sha256 = hashlib.sha256()
            with open(self.path, 'rb') as f:
                for block in iter(lambda: f.read(block_size), b''):
                    sha256.update(block)

            return sha256.hexdigest()

    def __init__(self, subparser, name, help):
        super().__init__(subparser, name, help)

        self.boxvar = EnvVar('SSSD_TEST_SUITE_BOX')

        self.parser.add_argument(
            '-l', '--linux-os', action='store', type=str, dest='linux',
            help='Linux OS name', default='linux'
        )

        self.parser.add_argument(
            '-w', '--windows-os', action='store', type=str, dest='windows',
            help='Windows OS name', default='windows'
        )

        self.parser.add_argument(
            '-u', '--url', action='store', type=str, dest='url',
            help='URL where the resulting boxes will be stored',
            default='http://'
        )

        self.parser.add_argument(
            '-o', '--output', action='store', type=str, dest='output',
            help='Output directory where new boxes will '
                 'be stored (default = %s/boxes)' % self.dir,
            default=self.dir + '/boxes'
        )

        self.parser.add_argument(
            '-v', '--version', action='store', type=str, dest='version',
            help='Version number appended to current date (default = 01)',
            default='01'
        )

        self.parser.add_argument(
            '--all', action='store_const', dest='guests', const=self.guests,
            help='Create boxes of all guests (default)'
        )

        self.parser.add_argument(
            '--ad', action=UniqueAppendConstAction, dest='guests',
            const='ad', help='Create AD box'
        )

        self.parser.add_argument(
            '--ad-child', action=UniqueAppendConstAction, dest='guests',
            const='ad-child', help='Create AD child box'
        )

        self.parser.add_argument(
            '--ipa', action=UniqueAppendConstAction, dest='guests',
            const='ipa', help='Create IPA box'
        )

        self.parser.add_argument(
            '--ldap', action=UniqueAppendConstAction, dest='guests',
            const='ldap', help='Create LDAP box'
        )

        self.parser.add_argument(
            '--client', action='append_const', dest='guests',
            const='client', help='Create client box'
        )

        self.parser.add_argument(
            '--from-scratch', action='store_true', dest='scratch',
            help='Destroy existing guests and provision new ones'
        )

        self.provision = [
            self.Task('Destroy guests', self.guests, self.taskDestroy),
            self.Task('Update boxes', self.guests, self.taskUpdate),
            self.Task('Bring up guests', self.guests, self.taskUp),
            self.Task('Provision guests',  [], self.taskProvision),
        ]

        self.tasks = [
            self.Task(
                'Make all images readable',
                self.guests, self.taskMakeReadable
            ),
            self.Task(
                'Halting all guests',
                [], self.taskHalt
            ),
            self.Task(
                'Zero out empty space on linux machines',
                self.linux, self.taskZeroDisk
            ),
            self.Task(
                'Create boxes',
                self.guests, self.taskCreateBox
            ),
            self.Task(
                'Create metadata',
                self.guests, self.taskCreateMetadata
            )
        ]

    def run(self, args, params=[]):
        print('This operation may take hours to finish. Be patient.')
        print('It may ask you a sudo password for command: '
              'chmod a+r %s/*.' % self.pool)

        if not args.guests:
            args.guests = self.guests

        tasks = self.tasks
        if args.scratch:
            tasks = self.provision + self.tasks

        total = len(tasks)
        current = 1

        self.boxvar.set('yes')
        try:
            for task in tasks:
                print('[%d/%d] %s' % (current, total, task.name))
                current += 1

                if not task.guests:
                    task.task(args)
                    continue

                for guest in task.guests:
                    if guest in args.guests:
                        box = self.Box(self, guest, args)
                        self.step(guest, 'Task started')
                        task.task(guest, box, args)
        except:
            raise
        finally:
            self.boxvar.restore()

    def step(self, guest, description):
        print('  [%s] %s' % (guest, description))

    def taskDestroy(self, guest, box, args):
        self.vagrant.run(['destroy', guest])

    def taskUpdate(self, guest, box, args):
        self.vagrant.run(['box', 'update', guest])

    def taskUp(self, guest, box, args):
        self.vagrant.run(['up', guest])

    def taskProvision(self, args):
        limit = ['all'] if args.guests is None else args.guests
        self.ansible.run(
            'prepare-guests.yml', limit, ['--skip-tags=enroll-all']
        )

    def taskMakeReadable(self, guest, box, args):
        self.shell.run(['sudo', 'chmod', 'a+r', box.img])

    def taskHalt(self, args):
        self.vagrant.run(['halt'])

    def taskZeroDisk(self, guest, box, args):
        '''
            Zeroing disks takes lots of space because it needs to fill the
            whole space in the sparse file. Therefore it is better to do
            it one guest after another.
        '''
        self.step(guest, 'Starting guest')
        self.vagrant.run(['up', guest])
        self.step(guest, 'Zeroing empty space')
        self.ansible.run('prepare-box.yml', [guest])
        self.step(guest, 'Halting guest')
        self.vagrant.run(['halt', guest])
        self.step(guest, 'Compressing image')
        self.shell.run(['mv', '-f', box.img, box.backup])
        self.shell.run(['qemu-img', 'convert', '-O', 'qcow2',
                        box.backup, box.img])
        self.shell.run(['rm', '-f', box.backup])

    def taskCreateBox(self, guest, box, args):
        self.shell.run(['mkdir', '-p', box.outdir])
        self.vagrant.run([
            'package', guest,
            '--vagrantfile=%s' % box.vgfile,
            '--output=%s' % box.file
        ])
        self.shell.run(['mv', '-f', '%s/%s' % (self.dir, box.file), box.path])
        self.step(guest, 'Box stored as: %s' % box.path)

    def taskCreateMetadata(self, guest, box, args):
        self.step(guest, 'Computing checksum of %s' % box.path)

        if args.dryrun:
            return

        sha = box.checksum()
        meta = textwrap.dedent('''
        {{
            "name": "sssd-{0}-{1}",
            "description": "SSSD Test Suite '{0}' {1}",
            "versions": [
                {{
                    "version": "{2}",
                    "status": "active",
                    "providers": [
                        {{
                            "name": "libvirt",
                            "url": "{3}/sssd-{0}-{1}-{2}.box",
                            "checksum_type": "sha256",
                            "checksum": "{4}"
                        }}
                    ]
                }}
            ]
        }}
        ''')

        meta = meta.format(box.os, guest, box.version, args.url, sha).strip()

        with open(box.metapath, "w") as f:
            f.write(meta)


class VagrantCloudCommand(Command):
    def __init__(self, subparser, name, help):
        super().__init__(subparser, name, help)

        self.parser.add_argument(
            '-t', '--token', action='store', type=str, dest='token',
            default=None, help='Vagrant cloud authentication token'
        )

        self.parser.add_argument(
            '-u', '--username', action='store', type=str, dest='username',
            default=None, help='Vagrant cloud username or organization name '
            'where boxes are stored'
        )


class VagrantCloudSetupCommand(VagrantCloudCommand):
    def __init__(self, subparser, name, help):
        super().__init__(subparser, name, help)

    def run(self, args, params=[]):
        data = {}

        if args.token is not None:
            data['token'] = args.token

        if args.username is not None:
            data['username'] = args.username

        with open('%s/vg-cloud.json' % self.dir, "w") as f:
            f.write(json.dumps(data))


class VagrantCloudListCommand(VagrantCloudCommand):
    def __init__(self, subparser, name, help):
        super().__init__(subparser, name, help)

    def run(self, args, params=[]):
        cloud = VagrantCloud(self.dir, args.token, args.username)
        boxes = cloud.list()

        for box in boxes:
            print('- {:50s} ({})'.format(box.tag, box.version))


class VagrantCloudUploadCommand(VagrantCloudCommand):
    def __init__(self, subparser, name, help):
        super().__init__(subparser, name, help)

        self.parser.add_argument(
            '--ipa', action='store', type=str, dest='ipa', default=None,
            help='Path to IPA box generated by create-box command'
        )

        self.parser.add_argument(
            '--ldap', action='store', type=str, dest='ldap', default=None,
            help='Path to LDAP box generated by create-box command'
        )

        self.parser.add_argument(
            '--client', action='store', type=str, dest='client', default=None,
            help='Path to client box generated by create-box command'
        )

        self.re = re.compile(
            "^sssd-(.+)-.+-(.+)\.box$",
            re.MULTILINE
        )

    def run(self, args, params=[]):
        boxes = {
            'ipa': args.ipa,
            'ldap': args.ldap,
            'client': args.client
        }

        cloud = VagrantCloud(self.dir, args.token, args.username)

        for guest, box in boxes.items():
            if box is None:
                continue

            (os, version) = self.parseBoxPath(box)

            boxname = '%s-%s' % (os, guest)

            print('[%s] Creating box %s (%s)' % (guest, boxname, version))
            cloud.boxCreate(
                boxname, 'sssd-test-suite: %s %s machine' % (os, guest)
            )
            cloud.versionCreate(
                boxname, version,
                'See: https://github.com/SSSD/sssd-test-suite'
            )
            cloud.providerCreate(boxname, version, 'libvirt')
            print('[%s] Uploading box %s' % (guest, box))
            cloud.providerUpload(boxname, version, 'libvirt', box)
            cloud.versionRelease(boxname, version)
            print('[%s] Finished' % guest)

    def parseBoxPath(self, path):
        matches = self.re.findall(os.path.basename(path))
        if not matches or len(matches) > 1:
            raise ValueError('Invalid box path: %s' % path)

        return matches[0]


def main():
    # Split arguments on --
    args = sys.argv[1:]
    params = []

    if '--' in args:
        params = args[args.index('--') + 1:]
        args = args[:args.index('--')]

    # Prepare argument parser
    parser = argparse.ArgumentParser(
        description='SSSD Test Suite Command Line Interface.',
        epilog='All parameters placed after -- will be passed to underlying '
               'vagrant or ansible calls. For example '
               '"sssd-test-suite rdp ad -- -g 90%"'
    )

    parser.add_argument(
        '-c', '--config', action='store', type=str, dest='config',
        help='Path to SSSD Test Suite configuration file',
        default=None
    )

    parser.add_argument(
        '--debug', action='store_true', dest='debug',
        help='Print commands that are executed.'
    )

    parser.add_argument(
        '--dry-run', action='store_true', dest='dryrun',
        help='Do not perform any chanes. Only print commands that '
             'would be executed.'
    )

    subparser = parser.add_subparsers(title='Commands')

    # Setup commands
    BasicVagrantCommand(subparser, 'status', 'Show current state of guest machines')
    BasicVagrantCommand(subparser, 'up', 'Bring up guest machines')
    BasicVagrantCommand(subparser, 'halt', 'Halt guest machines')
    BasicVagrantCommand(subparser, 'destroy', 'Destroy guest machines')
    BasicVagrantCommand(subparser, 'reload', 'Restarts guest machines')
    BasicVagrantCommand(subparser, 'resume', 'Resume suspended guest machines')
    BasicVagrantCommand(subparser, 'suspend', 'Suspends guest machines')
    SSHVagrantCommand(subparser, 'ssh', 'Open SSH to guest machine')
    RDPVagrantCommand(subparser, 'rdp', 'Open remote desktop for guest machine')
    ProvisionHostCommand(subparser, 'provision-host', 'Provision host machine')
    ProvisionGuestsCommand(subparser, 'provision', 'Provision guests machines')
    EnrollCommand(subparser, 'enroll', 'Enroll client to all domains')
    BasicVagrantCommand(subparser, 'update', 'Update vagrant box', command=['box', 'update'])
    PruneBoxCommand(subparser, 'prune', 'Delete outdated vagrant boxes')
    CreateBoxCommand(subparser, 'create-box', 'Create vagrant box')
    VagrantCloudSetupCommand(subparser, 'cloud-setup', 'Setup your vagrant cloud token and username')
    VagrantCloudListCommand(subparser, 'cloud-list', 'List boxes stored in vagrant cloud')
    VagrantCloudUploadCommand(subparser, 'cloud-upload', 'Upload boxes to vagrant cloud')

    # Parse argument and run given command
    args = parser.parse_args(args)

    UtilOptions.debug = args.debug
    UtilOptions.dryrun = args.dryrun

    if args.config:
        config = EnvVar('SSSD_TEST_SUITE_CONFIG')
        config.set(args.config)

    if hasattr(args, 'func'):
        args.func(args, params)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
