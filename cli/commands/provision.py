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

from commands.vagrant import VagrantCommandActor
from lib.actions import UniqueAppendAction
from lib.command import CommandParser, Command
from lib.task import Task
from util.actor import TestSuiteActor


class ProvisionHostActor(TestSuiteActor):
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

    def run(self, args, argv):
        self.tasklist('Provisioning Host', [
            Task('Install Ansible', self.install_dependencies),
            Task('Run Ansible Playbook', self.run_ansible, args, argv)
        ]).run()

    def install_dependencies(self, task):
        self.shell('''
        which ansible-playbook &> /dev/null && exit 0
        which dnf || exit 1
        dnf install -y ansible
        ''', stdout=subprocess.PIPE)

    def run_ansible(self, task, args, argv):
        argv.append('--extra-vars')
        argv.append('LIBVIRT_STORAGE={}'.format(args.pool))
        self.ansible('prepare-host.yml', args.unattended, argv=argv)


class ProvisionGuestsActor(TestSuiteActor):
    def setup_parser(self, parser):
        parser.add_argument(
            'guests', nargs='*',
            choices=['all'] + self.AllGuests,
            action=UniqueAppendAction,
            default='all',
            help='Guests to provision. '
                 'Multiple guests can be set. (Default "all")'
        )

        parser.epilog = textwrap.dedent('''
        This will provision selected guest machines. The machines will be
        prepared with necessary software and configurations. To enroll client
        to domains use 'enroll' command.

        All parameters placed after -- will be passed to ansible-playbook.
        ''')

    def run(self, args, argv):
        guests = args.guests if 'all' not in args.guests else ['all']
        self.ansible('prepare-guests.yml', True, limit=guests, argv=argv)


class EnrollActor(TestSuiteActor):
    def setup_parser(self, parser):
        parser.add_argument(
            'guests', nargs='*',
            choices=['all'] + self.AllGuests,
            action=UniqueAppendAction,
            default='all',
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

    def run(self, args, argv):
        self.tasklist('Enroll', [
            Task('Start Guest Machines', self.up, args),
            Task('Enroll Machines', self.enroll, args, argv)
        ]).run()

    def up(self, task, args):
        self.call(VagrantCommandActor('up'), args)

    def enroll(self, task, args, argv):
        if 'all' in args.guests:
            limit = ['all']
        else:
            limit = args.guests
            skip_guests = set(self.AllGuests) - set(args.guests)
            skip_tags = ['enroll-{}'.format(guest) for guest in skip_guests]
            if 'ipa' in skip_guests:
                skip_tags.append('enroll-local')
            else:
                limit.append('localhost')

            argv.append('--skip-tags')
            argv.append(','.join(skip_tags))

        self.ansible('enroll.yml', args.unattended, limit=limit, argv=argv)


class LdapActor(TestSuiteActor):
    def setup_parser(self, parser):
        parser.add_argument(
            'ldif', nargs='*',
            action=UniqueAppendAction,
            help='Path to ldif file. Multiple paths can be set.'
        )

        parser.add_argument(
            '--clear', action='store_true', dest='clear',
            help='Remove existing content from LDAP'
        )

    def run(self, args):
        tasks = self.tasklist('LDAP')

        if not args.clear and not args.ldif:
            self.parser.print_help()

        if args.clear:
            tasks.add('Clear current content', self.clear)

        for ldif in args.ldif:
            tasks.add('Import {}'.format(ldif), self.import_ldif, ldif)

        tasks.run()

    def clear(self, task):
        self.shell(r'''
        LDAP_URI="ldap://192.168.100.20"
        BASE_DN="dc=ldap,dc=vm"
        BIND_DN="cn=Directory Manager"
        BIND_PW="123456789"

        FILTER="(&(objectClass=*)(!(cn=Directory Administrators)))"
        SEARCH=`ldapsearch -x -D "$BIND_DN" -w "$BIND_PW" -H "$LDAP_URI" -b "$BASE_DN" -s one "$FILTER"`
        OBJECTS=`echo "$SEARCH" | grep dn | sed "s/dn: \(.*\)/'\1'/" | paste -sd " "`

        echo "$SEARCH" | grep numEntries &> /dev/null
        if [ $? -ne 0 ]; then
            echo "LDAP server is already clear. Nothing to do."
            exit 0
        fi

        echo "Removing existing objects."
        eval "ldapdelete -r -x -D '$BIND_DN' -w '$BIND_PW' -H '$LDAP_URI' $OBJECTS"
        ''')

    def import_ldif(self, task, ldif):
        self.shell('''
        LDAP_URI="ldap://192.168.100.20"
        BASE_DN="dc=ldap,dc=vm"
        BIND_DN="cn=Directory Manager"
        BIND_PW="123456789"

        echo "Importing LDIF: $LDIF"
        ldapadd -x -D "$BIND_DN" -w "$BIND_PW" -H "$LDAP_URI" -f "{ldif}"
        '''.format(ldif=ldif))


Commands = Command('provision', 'Provision machines', CommandParser([
    Command('host', 'Provision host machine', ProvisionHostActor),
    Command('guest', 'Provision selected guests machines', ProvisionGuestsActor),
    Command('enroll', 'Setup trusts and enroll client to domains', EnrollActor),
    Command('ldap', 'Import ldif into ldap server', LdapActor),
]))
