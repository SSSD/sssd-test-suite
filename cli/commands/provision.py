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

import subprocess
import textwrap
import nutcli.utils
import argparse

from nutcli.commands import Command, CommandParser
from nutcli.parser import UniqueAppendAction
from nutcli.tasks import Task, TaskList

from util.actor import TestSuiteActor
from commands.vagrant import VagrantUpActor


class AnsibleActor(TestSuiteActor):
    def _exec_ansible(self, playbook, unattended=False, limit=None, argv=None):
        argv = nutcli.utils.get_as_list(argv)

        env = {
            'ANSIBLE_CONFIG': f'{self.ansible_dir}/ansible.cfg'
        }

        limit = ','.join(limit) if limit is not None else 'all'

        if not unattended:
            argv.append('--ask-become-pass')

        args = ['--limit', limit, *argv, playbook]

        return self.shell(['ansible-playbook', *args], env=env)


class ProvisionHostActor(AnsibleActor):
    def setup_parser(self, parser):
        parser.add_argument(
            '-p', '--pool', action='store', type=str, dest='pool',
            help='Location of libvirt directory storage pool that '
                 'will be named as "sssd-test-suite".',
            metavar='POOL-DIRECTORY', required=True
        )

        parser.add_argument(
            '-u', '--unattended', action='store_true',
            default=False, dest='unattended',
            help='Do not ask for sudo password (requires passwordless sudo).'
        )

        parser.add_argument(
            'argv', nargs=argparse.REMAINDER,
            help='Additional arguments passed to the ansible-playbook command'
        )

        parser.epilog = textwrap.dedent('''
        The pool will be created as a new libvirt directory storage type and
        named "sssd-test-suite". The directory location must not be used by
        any other pool. A symbolic link to this directory will be created at
        sssd-test-suite/pool directory.

        This command will ask for sudo password for local machine, unless
        --unattended option is specified. However, using this option requires
        passwordless sudo access to your machine.

        All parameters placed after -- will be passed to ansible-playbook.
        ''')

    def __call__(self, pool, unattended, argv):
        argv += ['--extra-vars', f'LIBVIRT_STORAGE={pool}']
        self._exec_ansible(
            f'{self.ansible_dir}/prepare-host.yml',
            unattended=unattended, limit=None, argv=argv
        )


class ProvisionGuestsActor(AnsibleActor):
    def setup_parser(self, parser):
        parser.add_argument(
            '-p', '--playbook', action='store', type=str, dest='playbook',
            help='Playbook to execute (defaults to prepare-guests.yml)',
            metavar='PLAYBOOK'
        )

        parser.add_argument(
            'guests', nargs='*', choices=['all'] + self.AllGuests,
            action=UniqueAppendAction, default='all',
            help='Guests to provision. '
                 'Multiple guests can be set. (Default "all")'
        )


        parser.add_argument(
            'argv', nargs=argparse.REMAINDER,
            help='Additional arguments passed to the ansible-playbook command'
        )

        parser.epilog = textwrap.dedent('''
        This will provision selected guest machines. The machines will be
        prepared with necessary software and configurations. To enroll client
        to domains use 'enroll' command.

        All parameters placed after -- will be passed to ansible-playbook.
        ''')

    def __call__(self, guests, playbook=None, argv=None):
        guests = guests if 'all' not in guests else ['all']

        if playbook is None:
            playbook = f'{self.ansible_dir}/prepare-guests.yml'

        self._exec_ansible(playbook, unattended=True, limit=guests, argv=argv)


class EnrollActor(AnsibleActor):
    def setup_parser(self, parser):
        parser.add_argument(
            'guests', nargs='*', choices=['all'] + self.AllGuests,
            action=UniqueAppendAction, default='all',
            help='Guests that the client should enroll to. '
                 'Multiple guests can be set. (Default "all")'
        )

        parser.add_argument(
            '-s', '--sequence', action='store_true', dest='sequence',
            help='Start guest one by one instead of in parallel'
        )

        parser.add_argument(
            '-u', '--unattended', action='store_true', dest='unattended',
            help='Do not ask for sudo password (requires passwordless sudo).'
        )

        parser.add_argument(
            'argv', nargs=argparse.REMAINDER,
            help='Additional arguments passed to the ansible-playbook command'
        )

        parser.epilog = textwrap.dedent('''
        This will start up selected guests and then finalize their provisioning.
        Most of all it will enroll client into domains, but it also finishes
        preparation of IPA server. Actions that are executed depends on
        selected guests.

        - When 'ipa' guest is selected, it's CA certificate is copied to the
          local machine (sssd-test-suite/shared-enrollment/ipa/ca.crt)
          and trust to this certificate is established. The CA
          certificate is copied to:
            /etc/pki/ca-trust/source/anchors/sssd-test-suite-ipa.crt

        - When 'ipa' and 'ad' guests are selected, a trust is established
          between IPA and AD servers.

        - When 'ldap' is selected, it's CA certificate is copied to the local
          machine (sssd-test-suite/shared-enrollment/ldap/cacert.asc).

        - When 'client' is selected, it is enrolled into domains. The domains
          it is enrolled to corresponds to selected guests, i.e.: ad, ad-child,
          ipa, ldap.

        This command will ask for sudo password for local machine, unless
        --unattended option is specified. However, using this option requires
        passwordless sudo access to your machine.

        All parameters placed after -- will be passed to ansible-playbook.
        ''')

    def __call__(self, guests, sequence, unattended, argv):
        TaskList('enroll', logger=self.logger)([
            Task('Start Guest Machines', taskarg=False)(
                VagrantUpActor(parent=self), guests, sequence
            ),
            Task('Enroll Machines', taskarg=False)(
                self.enroll, guests, unattended, argv
            ),
        ]).execute()


    def enroll(self, guests, unattended, argv):
        if 'all' in guests:
            limit = ['all']
        else:
            limit = guests
            skip_guests = set(self.AllGuests) - set(guests)
            skip_tags = [f'enroll-{guest}' for guest in skip_guests]
            if 'ipa' in skip_guests:
                skip_tags.append('enroll-local')
            else:
                limit.append('localhost')

            argv += ['--skip-tags', ','.join(skip_tags)]

        self._exec_ansible(
            f'{self.ansible_dir}/enroll.yml',
            unattended=unattended, limit=guests, argv=argv
        )


class ProvisionLDAPActor(TestSuiteActor):
    def setup_parser(self, parser):
        parser.add_argument(
            'ldif', nargs='*', action=UniqueAppendAction,
            help='Path to ldif file. Multiple paths can be set.'
        )

        parser.add_argument(
            '--clear', action='store_true', dest='clear',
            help='Remove existing content from LDAP'
        )

    def __call__(self, ldif, clear=False):
        tasklist = TaskList('LDAP', logger=self.logger)

        if not clear and not ldif:
            self.error('You have to specify at least one parameter.')
            return 1

        if clear:
            tasklist.tasks.append(
                Task('Clear current content', taskarg=False)(self.clear)
            )

        for ldif in ldif:
            tasklist.tasks.append(
                Task(f'Import {ldif}', taskarg=False)(self.import_ldif, ldif)
            )

        tasklist.execute()

    def clear(self):
        self.shell(r'''
        LDAP_URI="ldap://192.168.100.20"
        BASE_DN="dc=ldap,dc=vm"
        BIND_DN="cn=Directory Manager"
        BIND_PW="123456789"

        FILTER="(&(objectClass=*)(!(cn=Directory Administrators)))"
        SEARCH=`ldapsearch -x -D "$BIND_DN" -w "$BIND_PW" -H "$LDAP_URI" -b "$BASE_DN" -s one "$FILTER"`
        ret=$?
        if [ $ret -ne 0 ]; then
            exit $ret
        fi

        OBJECTS=`echo "$SEARCH" | grep dn | sed "s/dn: \(.*\)/'\1'/" | paste -sd " "`

        echo "$SEARCH" | grep numEntries &> /dev/null
        if [ $? -ne 0 ]; then
            echo "LDAP server is already clear. Nothing to do."
            exit 0
        fi

        echo "Removing existing objects."
        eval "ldapdelete -r -x -D '$BIND_DN' -w '$BIND_PW' -H '$LDAP_URI' $OBJECTS"
        exit $?
        ''')

    def import_ldif(self, ldif):
        self.shell(f'''
        LDAP_URI="ldap://192.168.100.20"
        BASE_DN="dc=ldap,dc=vm"
        BIND_DN="cn=Directory Manager"
        BIND_PW="123456789"

        ldapadd -x -D "$BIND_DN" -w "$BIND_PW" -H "$LDAP_URI" -f "{ldif}"
        exit $?
        ''')


class RearmWindowsActor(AnsibleActor):
    def setup_parser(self, parser):
        parser.add_argument(
            'guests', nargs='*', choices=['all'] + self.WindowsGuests,
            action=UniqueAppendAction, default='all',
            help='Guests that the client should enroll to. '
                 'Multiple guests can be set. (Default "all")'
        )

        parser.add_argument(
            'argv', nargs=argparse.REMAINDER,
            help='Additional arguments passed to the ansible-playbook command'
        )

        parser.epilog = textwrap.dedent('''
        This will renew the Windows evaluation license when it is expired. It
        will trigger guest reboot after the renewal.

        The renewal can be done only 6 times. You have to recreate the machine
        after that.

        All parameters placed after -- will be passed to ansible-playbook.
        ''')

    def __call__(self, guests, argv):
        guests = guests if 'all' not in guests else ['all']
        self._exec_ansible(
            f'{self.ansible_dir}/rearm-windows-license.yml',
            unattended=True, limit=guests, argv=argv
        )


Commands = Command('provision', 'Provision machines', CommandParser()([
    Command('host', 'Provision host machine', ProvisionHostActor()),
    Command('guest', 'Provision selected guests machines', ProvisionGuestsActor()),
    Command('enroll', 'Setup trusts and enroll client to domains', EnrollActor()),
    Command('ldap', 'Import ldif into ldap server', ProvisionLDAPActor()),
    Command('rearm', 'Renew windows license', RearmWindowsActor()),
]))
