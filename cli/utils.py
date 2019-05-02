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
import json
import argparse
import subprocess
from collections import OrderedDict

from subprocess import CalledProcessError


class UtilOptions:
    debug = False
    dryrun = False


class ShellProcessError(CalledProcessError):
    def __init__(self, returncode, cmd, env={}, output=None, stderr=None):
        super().__init__(returncode, cmd,  output, stderr)
        self.env = env


class UniqueAppendConstAction(argparse.Action):
    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        if not hasattr(namespace, self.dest):
            setattr(namespace, self.dest, [self.const])
            return

        values = getattr(namespace, self.dest)
        if values is None:
            values = []

        if self.const in values:
            return

        values.append(self.const)
        setattr(namespace, self.dest, values)


class EnvVar:
    def __init__(self, name):
        self.name = name
        self.was_set = self.isset()
        self.orig_value = self.get()

    def get(self):
        return os.environ.get(self.name)

    def set(self, value):
        os.environ[self.name] = value

    def isset(self):
        return True if self.name in os.environ else False

    def restore(self):
        if self.was_set:
            os.environ[self.name] = self.orig_value
            return

        if self.isset():
            del os.environ[self.name]

    def __del__(self):
        self.restore()


class Shell:
    def __init__(self, directory):
        self.cwd = directory

    def env(self, name, value):
        return '%s="%s"' % (name, value)

    def run(self, args, env={}, **kwargs):
        env = OrderedDict(sorted(env.items()))
        newenv = os.environ.copy()
        newenv.update(env)

        if UtilOptions.debug or UtilOptions.dryrun:
            flat = ' '.join(
                '%s=%r' % (key, value) for key, value in env.items()
            )
            flat = flat + ' ' if flat else ''
            print('    [shell] %s%s' % (flat, ' '.join(args)))

        if UtilOptions.dryrun:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=''.encode('utf-8'),
                stderr=''.encode('utf-8')
            )

        try:
            if 'check' not in kwargs:
                kwargs['check'] = True

            result = subprocess.run(args, env=newenv, cwd=self.cwd, **kwargs)
        except CalledProcessError as err:
            raise ShellProcessError(
                err.returncode,
                err.cmd,
                env,
                err.output,
                err.stderr
            ) from None

        return result

    def isCommandAvailable(self, command):
        r = self.run(
            ['which', command],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        return r.returncode == 0

    def installCommand(self, command):
        if self.isCommandAvailable('dnf'):
            print('Installing %s via dnf' % command)
            r = self.run(
                ['sudo', 'dnf', 'install', '-y', command],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            return r.returncode == 0

        return False


class Ansible(Shell):
    def __init__(self, directory):
        super().__init__(directory)

    def run(self, playbook, limit=[], params=[], **kwargs):
        env = {
            'ANSIBLE_SSH_ARGS': '-o UserKnownHostsFile=/dev/null '
                                '-o IdentitiesOnly=yes '
                                '-o ControlMaster=auto '
                                '-o ControlPersist=60s',
            'ANSIBLE_HOST_KEY_CHECKING': 'false'
        }

        limit = ','.join(limit) if limit else 'all'

        args = [
            '--limit', limit,
            '--inventory-file', '%s/provision/inventory.yml' % self.cwd
        ] + params + ['%s/provision/%s' % (self.cwd, playbook)]

        return super().run(['ansible-playbook'] + args, env, **kwargs)


class Vagrant(Shell):
    def __init__(self, directory):
        super().__init__(directory)

    def run(self, args, params=[], **kwargs):
        env = {
            'VAGRANT_CWD': self.cwd
        }

        if params:
            params = ['--'] + params

        return super().run(['vagrant'] + args + params, env, **kwargs)
