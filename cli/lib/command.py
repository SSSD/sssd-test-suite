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
import colorama
import copy
import inspect
import sys
import textwrap
import traceback

from .actions import SubparsersAction
from .colors import format_colors
from .decorators import TimeoutError
from .shell import Shell,  ShellScriptError, ShellScriptTimeoutError
from .task import TaskList


def check_instance(item, allowed_classes):
    if isinstance(item, allowed_classes):
        return

    raise ValueError('Expected instance of {}, got {}'.format(
        ', '.join([cls.__name__ for cls in allowed_classes]),
        item.__class__
    ))


class Actor(object):
    def __init__(self):
        self.shell = Shell()
        self.parser = None
        self.runner = None

    def _setup_parser(self, parser):
        self.parser = parser
        self.setup_parser(parser)

    def _set_runner(self, runner):
        self.runner = runner

    def setup_parser(self, parser):
        # There are not any options by default.
        return

    def message(self, message, *args, **kwargs):
        self.runner.message(message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        self.runner.error(message, *args, **kwargs)

    def call(self, command, *args, **kwargs):
        self.runner.call(command, *args, **kwargs)

    def tasklist(self, name=None, tasks=None):
        return TaskList(self.runner, name, tasks)

    def run(self):
        raise NotImplementedError("run() method is not implemented")


class Command(object):
    def __init__(self, name, help, handler, **kwargs):
        self.handler = handler() if inspect.isclass(handler) else handler
        self.name = name
        self.help = help
        self.kwargs = kwargs

    def setup_parser(self, parent_parser):
        check_instance(self.handler, (Actor, CommandParser))

        parser = parent_parser.add_parser(
            self.name, help=self.help,
            formatter_class=argparse.RawTextHelpFormatter,
            **self.kwargs
        )

        if isinstance(self.handler, Actor):
            parser.set_defaults(func=self.handler)
            self.handler._setup_parser(parser)
            return

        # CommandParser
        parser.set_defaults(func=parser)
        self.handler.setup_parser(parser)


class CommandParser(object):
    def __init__(self, items=None, title=None, metavar='COMMANDS', **kwargs):
        self.items = items if items is not None else []
        self.title = title
        self.metavar = metavar
        self.kwargs = kwargs

    def add(self, item):
        self.items.append(item)
        return self

    def add_list(self, items):
        self.items += items
        return self

    def setup_parser(self, parent_parser):
        subparser = parent_parser.add_subparsers(
            action=SubparsersAction,
            title=self.title,
            metavar=self.metavar,
            **self.kwargs
        )

        for item in self.items:
            check_instance(item, (Command, CommandList, CommandGroup))
            item.setup_parser(subparser)

        return subparser

    def __iter__(self):
        return self.items.__iter__()

    def __next__(self):
        return self.items.__next__()


class CommandGroup(CommandParser):
    def __init__(self, title, items=None, **kwargs):
        super().__init__(items, title=title, **kwargs)

    def setup_parser(self, parent_parser):
        group = parent_parser.add_parser_group(self.title)

        for item in self.items:
            check_instance(item, (Command, CommandList, CommandGroup))
            item.setup_parser(group)

        return group


class CommandList(CommandParser):
    def __init__(self, items=None):
        super().__init__(items)

    def setup_parser(self, parent_parser):
        for item in self.items:
            check_instance(item, (Command, CommandGroup))
            item.setup_parser(parent_parser)


class Runner:
    def __init__(self, name):
        self.name = name
        self._print_shell = False
        self._dry_run = False

    def execute(self, parser, argv):
        split_argv = []
        if '--' in argv:
            split_argv = argv[argv.index('--') + 1:]
            argv = argv[:argv.index('--')]

        parser.add_argument(
            '--print-shell', action='store_true', dest='_runner_print_shell',
            help='Print shell commands that are being executed.'
        )

        parser.add_argument(
            '--dry-run', action='store_true', dest='_runner_dry_run',
            help='Print commands that are being executed without '
                 'actually running them.'
        )

        args = parser.parse_args(argv)
        self._print_shell = args._runner_print_shell
        self._dry_run = args._runner_dry_run

        Shell.PrintCommand = self._print_shell or self._dry_run
        Shell.DryRun = self._dry_run

        if not hasattr(args, 'func'):
            parser.print_help()
            return 1

        try:
            self._run_handler(args.func, args, split_argv)
        except ShellScriptTimeoutError as e:
            self._handle_shell_timeout_error(e, *sys.exc_info())
            return 255
        except ShellScriptError as e:
            self._handle_shell_error(e, *sys.exc_info())
            return e.returncode
        except TimeoutError as e:
            self._handle_timeout_error(e, *sys.exc_info())
            return 255
        except Exception:
            self._handle_exception(*sys.exc_info())
            return 1

        return 0

    def call(self, command, args=None, argv=None, **kwargs):
        handler = command() if inspect.isclass(command) else command
        argv = argv if argv is not None else []

        args = copy.copy(args) if args is not None else argparse.Namespace()
        for name in kwargs:
            setattr(args, name, kwargs[name])

        setattr(args, '_runner_print_shell', self._print_shell)
        setattr(args, '_runner_dry_run', self._dry_run)
        setattr(args, 'func', handler)

        self._run_handler(handler, args, argv)

    def message(self, message, color=colorama.Fore.BLUE,
                style=colorama.Style.BRIGHT, file=sys.stdout, without_prefix=False):
        if without_prefix:
            print(textwrap.indent(
                textwrap.dedent(message).strip(),
                ' ' * len('[{runner}] '.format(runner=self.name))
            ), file=file, flush=True)
            return

        print(textwrap.indent(
            textwrap.dedent(message).strip().format(**format_colors()),
            '{s-r}{style}{color}[{runner}]{s-r} '.format(
                color=color,
                style=style,
                runner=self.name,
                **format_colors()
            )
        ), file=file, flush=True)

    def error(self, message, color=colorama.Fore.RED,
              style=colorama.Style.BRIGHT, file=sys.stderr, without_prefix=False):
        self.message(message, color, style, file, without_prefix)

    def _run_handler(self, handler, args, argv):
        check_instance(handler, (Actor, argparse.ArgumentParser))

        # Handler is ArgumentParser, print help.
        if isinstance(handler, argparse.ArgumentParser):
            handler.print_help()
            return

        # Handler is Actor, finalize it and execute.
        handler._set_runner(self)
        numargs = len(inspect.signature(handler.run).parameters)
        if numargs == 0:
            handler.run()
        elif numargs == 1:
            handler.run(args)
        elif numargs == 2:
            handler.run(args, argv)
        else:
            raise TypeError('Unexpected number of arguments for command handler.')

    def _handle_exception(self, type, value, tb):
        self.error('''
            {s-b}Exception {c-b}{type}{s-r}{s-b}: {value}{s-r}
            {s-b}Traceback (most recent call last):{s-r}
        '''.format(
            type=type.__name__,
            value=value,
            **format_colors()
        ))

        traceback.print_tb(tb)

    def _handle_shell_error(self, err, type, value, tb):
        env = '(empty)' if not err.env else err.flat_env()

        self.error('''
            {s-b}The following command exited with {code}:
            {s-b}Working directory: {s-r}{c-b}{cwd}{s-r}
            {s-b}Environment: {s-r}{c-b}{env}{s-r}
            {s-b}Command: {s-r}{cmd}
        '''.format(
            code=err.returncode,
            env=env,
            cwd=err.cwd,
            cmd=err.flat_cmd(),
            **format_colors()
        ))

        if err.script:
            self.error(err.script, without_prefix=True)

        if err.output:
            self.error('{s-b}Command standard output:{s-r}')
            self.error(err.output.decode('utf-8'), without_prefix=True)

        if err.stderr:
            self.error('{s-b}Command error output:{s-r}')
            self.error(err.stderr.decode('utf-8'), without_prefix=True)

    def _handle_shell_timeout_error(self, err, type, value, tb):
        env = '(empty)' if not err.env else err.flat_env()

        self.error('''
            {s-b}The following command did not finished in {timeout} seconds:
            {s-b}Working directory: {s-r}{c-b}{cwd}{s-r}
            {s-b}Environment: {s-r}{c-b}{env}{s-r}
            {s-b}Command: {s-r}{cmd}
        '''.format(
            timeout=err.timeout,
            env=env,
            cwd=err.cwd,
            cmd=err.flat_cmd(),
            **format_colors()
        ))

        if err.script:
            self.error(err.script, without_prefix=True)

        if err.output:
            self.error('{s-b}Command standard output:{s-r}')
            self.error(err.output.decode('utf-8'), without_prefix=True)

        if err.stderr:
            self.error('{s-b}Command error output:{s-r}')
            self.error(err.stderr.decode('utf-8'), without_prefix=True)

    def _handle_timeout_error(self, err, type, value, tb):
        self.error('''
            {s-b}Exception {c-b}{type}{s-r}{s-b}{s-r}
            {s-b}Operation did not finished in {timeout} seconds.
            {s-b}{message}{s-r}
        '''.format(
            type=type.__name__,
            timeout=err.timeout,
            message=str(err),
            **format_colors()
        ))
