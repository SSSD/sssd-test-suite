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

import nutcli
import argparse
import os
import re

from nutcli.commands import Command
from nutcli.parser import UniqueAppendAction

from util.actor import TestSuiteActor


class VagrantCommandActor(TestSuiteActor):
    def __init__(self, command, ok_rc=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command = command
        self.ok_rc = nutcli.utils.get_as_list(ok_rc)

    def setup_parser(self, parser):
        parser.add_argument(
            'guests', nargs='*',
            choices=['all'] + self.AllGuests,
            action=UniqueAppendAction,
            default='all',
            help='Guest to run the command with. '
                 'Multiple guests can be set. (Default "all")'
        )

        parser.add_argument(
            '-s', '--sequence', action='store_true', dest='sequence',
            help='Run operation on guests in sequence (one by one)'
        )

        parser.add_argument(
            '--argv', dest='argv', nargs=argparse.REMAINDER, default=[],
            help='Additional arguments passed to the command'
        )

    def _exec_vagrant(self, args=None, argv=None, **kwargs):
        if self.cli_args.config is not None:
            config = self.cli_args.config
        else:
            config = os.environ.get(
               'SSSD_TEST_SUITE_CONFIG',
                self.vagrant_dir + '/config.json'
            )

        command = ['vagrant', *self.command.split(' '), *nutcli.utils.get_as_list(args)]
        if argv is not None:
            command += ['--'] + argv

        return self.shell(
            command,
            env={
                'VAGRANT_CWD': self.vagrant_dir,
                'SSSD_TEST_SUITE_CONFIG': config
            },
            **kwargs
        )

    def __call__(self, guests, sequence=False, argv=None):
        argv = nutcli.utils.get_as_list(argv)
        def run_guest(guests, argv):
            try:
                self._exec_vagrant(argv + guests)
            except nutcli.shell.ShellCommandError as err:
                if err.rc not in self.ok_rc:
                    raise

        guests = guests if 'all' not in guests else self.AllGuests
        guests.sort()

        if sequence:
            for guest in guests:
                run_guest([guest], argv)
        else:
            run_guest(guests, argv)


class VagrantStatusActor(VagrantCommandActor):
    def __init__(self, *args, **kwargs):
        super().__init__('status', None, *args, **kwargs)


class VagrantUpActor(VagrantCommandActor):
    def __init__(self, *args, **kwargs):
        super().__init__('up', None, *args, **kwargs)


class VagrantHaltActor(VagrantCommandActor):
    def __init__(self, *args, **kwargs):
        super().__init__('halt', None, *args, **kwargs)


class VagrantDestroyActor(VagrantCommandActor):
    def __init__(self, *args, **kwargs):
        super().__init__('destroy', [2], *args, **kwargs)

    def __call__(self, guests, sequence=False, argv=None):
        argv = nutcli.utils.get_as_list(argv)
        if '-f' not in argv:
            argv.append('-f')

        super().__call__(guests, sequence, argv)


class VagrantReloadActor(VagrantCommandActor):
    def __init__(self, *args, **kwargs):
        super().__init__('reload', None, *args, **kwargs)


class VagrantResumeActor(VagrantCommandActor):
    def __init__(self, *args, **kwargs):
        super().__init__('resume', None, *args, **kwargs)


class VagrantSuspendActor(VagrantCommandActor):
    def __init__(self, *args, **kwargs):
        super().__init__('suspend', None, *args, **kwargs)


class VagrantUpdateActor(VagrantCommandActor):
    def __init__(self, *args, **kwargs):
        super().__init__('box update', None, *args, **kwargs)


class VagrantPackageActor(VagrantCommandActor):
    def __init__(self, *args, **kwargs):
        super().__init__('package', None, *args, **kwargs)


class VagrantPruneActor(VagrantCommandActor):
    def __init__(self, *args, **kwargs):
        super().__init__('box prune', None, *args, **kwargs)

    def setup_parser(self, parser):
        parser.add_argument(
            '-f', '--force', action='store_true', dest='force',
            help='Destroy without confirmation even when box is in use'
        )

        parser.add_argument(
            '--argv', dest='argv', nargs=argparse.REMAINDER, default=[],
            help='Additional arguments passed to the command'
        )

    def __call__(self, force, argv=None):
        regex = re.compile(
            r"^[^']+'([^']+)' \(v([^)]+)\).*$",
            re.MULTILINE
        )

        args = nutcli.utils.get_as_list(argv)
        if force:
            args.append('--force')

        result = self._exec_vagrant(args=args, argv=None, capture_output=True)
        for (box, version) in regex.findall(result.stdout):
            volume = '{box}_vagrant_box_image_{version}.img'.format(
                box=box.replace('/', '-VAGRANTSLASH-'),
                version=version
            )

            self.info(f'Box {box}, version {version} is outdated.')
            self.info(f'  ...removing {volume}')

            self.shell('''
            sudo virsh vol-info {volume} --pool {pool} &> /dev/null
            if [ $? -ne 0 ]; then
                exit 0
            fi

            sudo virsh vol-delete {volume} --pool {pool}
            '''.format(volume=volume, pool='sssd-test-suite'))


class VagrantSSHActor(VagrantCommandActor):
    def __init__(self, *args, **kwargs):
        super().__init__('ssh', None, *args, **kwargs)

    def setup_parser(self, parser):
        parser.add_argument(
            'guest', type=str, choices=self.LinuxGuests
        )

        parser.add_argument(
            'argv', nargs=argparse.REMAINDER,
            help='Additional arguments passed to the SSH client'
        )

    def __call__(self, guest, argv):
        self._exec_vagrant([guest], argv)


class VagrantRDPActor(VagrantCommandActor):
    def __init__(self, *args, **kwargs):
        super().__init__('rdp', None, *args, **kwargs)

    def setup_parser(self, parser):
        parser.add_argument(
            'guest', type=str, choices=self.WindowsGuests
        )

        parser.add_argument(
            'argv', nargs=argparse.REMAINDER,
            help='Additional arguments passed to the RDP client'
        )

    def __call__(self, guest, argv):
        self._exec_vagrant([guest], argv)

Commands = [
    Command('status', 'Show current state of guest machines', VagrantStatusActor()),
    Command('up', 'Bring up guest machines', VagrantUpActor()),
    Command('halt', 'Halt guest machines', VagrantHaltActor()),
    Command('destroy', 'Destroy guest machines', VagrantDestroyActor()),
    Command('reload', 'Restarts guest machines', VagrantReloadActor()),
    Command('resume', 'Resume suspended guest machines', VagrantResumeActor()),
    Command('suspend', 'Suspends guest machines', VagrantSuspendActor()),
    Command('ssh', 'Open SSH to guest machine', VagrantSSHActor()),
    Command('rdp', 'Open remote desktop to guest machine', VagrantRDPActor()),
]
