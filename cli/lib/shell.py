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
import subprocess
import textwrap

from .colors import format_colors
from collections import OrderedDict


class ShellScriptError(subprocess.CalledProcessError):
    def __init__(self, returncode, cmd, script=None,
                 cwd=None, env=None, output=None, stderr=None):
        super().__init__(returncode, cmd,  output, stderr)
        self.cwd = cwd if cwd is not None else os.getcwd()
        self.env = env if env is not None else {}
        self.script = script

    def flat_env(self):
        return ' '.join(
            '%s=%r' % (key, value) for key, value in self.env.items()
        )

    def flat_cmd(self):
        return ' '.join(self.cmd)


class ShellScriptTimeoutError(ShellScriptError):
    def __init__(self, timeout, cmd, script=None,
                 cwd=None, env=None, output=None, stderr=None):
        super().__init__(-1, cmd, script, cwd, env, output, stderr)
        self.timeout = timeout


class Shell(object):
    PrintCommand = False
    DryRun = False

    def __init__(self, cwd=None, env=None, clear_env=False, shell='/bin/bash'):
        self.cwd = cwd
        self.env = self.__get_ordered(env) if env is not None else self.__get_ordered({})
        self.clear_env = clear_env
        self.shell = shell

    def run(self, script, clear_env=False, **kwargs):
        args = self.__process_args(clear_env, kwargs)
        command = self.__get_command(script)

        env = self.__get_ordered(kwargs.get('env', {}))
        if not clear_env:
            env.update(self.env)

        try:
            if Shell.PrintCommand:
                self.__print_command(command, env)

            if Shell.DryRun:
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=''.encode('utf-8'),
                    stderr=''.encode('utf-8')
                )

            return subprocess.run(command, **args)
        except subprocess.CalledProcessError as e:
            raise ShellScriptError(
                returncode=e.returncode,
                cmd=command if type(script) is list else command[:2],
                script=None if type(script) is list else script,
                cwd=args['cwd'],
                env=env,
                output=e.output,
                stderr=e.stderr
            ) from None
        except subprocess.TimeoutExpired as e:
            raise ShellScriptTimeoutError(
                timeout=e.timeout,
                cmd=command if type(script) is list else command[:2],
                script=None if type(script) is list else script,
                cwd=args['cwd'],
                env=env,
                output=e.output,
                stderr=e.stderr
            ) from None

    def __get_command(self, script):
        if type(script) is list:
            return script

        return [self.shell, '-c', textwrap.dedent(script)]

    def __print_command(self, command, env=None):
        env = env if env is not None else {}

        flatenv = ' '.join(
            '%s=%r' % (key, value) for key, value in env.items()
        )
        flatenv = flatenv + ' ' if flatenv else ''

        print('{s-b}{c-b}[shell]{s-r} {c-g}{env}{s-r}{s-b}{cmd}{s-r}'.format(
            env=flatenv,
            cmd=' '.join(command),
            **format_colors()
        ), flush=True)

    def __get_ordered(self, d):
        if not isinstance(d, OrderedDict):
            return OrderedDict(sorted(d.items()))

        return d

    def __process_args(self, run_clear_env, args):
        args = args.copy()

        if 'check' not in args:
            args['check'] = True

        if 'cwd' not in args:
            args['cwd'] = self.cwd

        if run_clear_env and 'env' not in args:
            args['env'] = {}
        elif self.clear_env:
            newenv = self.env.copy()
            newenv.update(self.__get_ordered(args.get('env', {})))
            args['env'] = newenv
        else:
            newenv = os.environ.copy()
            newenv.update(self.env)
            newenv.update(self.__get_ordered(args.get('env', {})))
            args['env'] = newenv

        return args

    def __call__(self, *args, **kwargs):
        self.run(*args, **kwargs)
