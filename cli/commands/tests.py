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
import tempfile
import textwrap
import types
import yaml
import nutcli

from nutcli.commands import Command
from nutcli.tasks import Task, TaskList

from commands.vagrant import VagrantUpActor, VagrantHaltActor, VagrantDestroyActor, VagrantUpdateActor, VagrantPruneActor, VagrantSSHActor
from util.actor import TestSuiteActor


class RunTestsActor(TestSuiteActor):
    def setup_parser(self, parser):
        parser.add_argument(
            '-s', '--sssd', action='store', type=str, dest='sssd',
            help='Path to SSSD source directory.',
            required=True
        )

        parser.add_argument(
            '-a', '--artifacts', action='store', type=str, dest='artifacts',
            help='Path to directory where tests artifacts will be stored.',
            required=True,
        )

        parser.add_argument(
            '-u', '--update', action='store_true', dest='update',
            help='Update current boxes before running the tests.'
        )

        parser.add_argument(
            '-p', '--prune', action='store_true', dest='prune',
            help='Remove outdated boxes after update.'
        )

        parser.add_argument(
            '-t', '--test-config', action='store', type=str, dest='test_config',
            help='Path to test suite yaml configuration.'
        )

        parser.add_argument(
            '--do-not-destroy', action='store_false', dest='destroy',
            help='Do not destroy existing machines.'
        )

        parser.epilog = textwrap.dedent('''
        This command will execute tests described in yaml configuration file.
        This file can be specified with --test-config parameter. If not set,
        $sssd/contrib/test-suite/test-suite.yml is used.
        ''')

    def __call__(self, **kwargs):
        suite = self.load_test_suite(kwargs['test_config'], kwargs['sssd'])
        self.prepare_environment(suite, kwargs['update'], kwargs['prune'], kwargs['artifacts'])
        self.run_test_suite(suite, kwargs)

    """
    - name: Test Case Name
      machines:
      - list of machines to start
      tasks:
      - name: Task Name (optional)
        run-on: guest (optional, defaults to client or machines[0])
        directory: working directory (optional, default to /shared/sssd)
        shell: pwd
        artifacts: (optional)
        - list of paths (guest is client or machines[0])
        - from: guest
          files:
          - list of files
      artifacts: (optional)
      - list of paths (guest is client or machines[0])
      - from: guest
        files:
        - list of files
    """
    def load_test_suite(self, config, sssd):
        if config is None:
            config = f'{sssd}/contrib/test-suite/test-suite.yml'

        with open(config) as f:
            return yaml.safe_load(f)

    def prepare_environment(self, suite, update, prune, artifacts_dir):
        required_guests = set()
        for case in suite:
            required_guests.update(case.get('machines', []))
        guests = list(required_guests)

        TaskList('Preparation', logger=self.logger)([
            Task('Creating artifacts directory', taskarg=False)(
                lambda: self.shell(['mkdir', '-p', artifacts_dir])
            ),
            Task('Updating boxes', enabled=update, taskarg=False)(
                VagrantUpdateActor(parent=self), guests=guests
            ),
            Task('Removing outdated boxes', enabled=prune, taskarg=False)(
                VagrantPruneActor(parent=self), force=True
            )
        ]).execute()

    def run_command_on_guest(self, guest, command_directory, working_directory, command, timeout=None):
        if not command:
            return

        with tempfile.NamedTemporaryFile(dir=command_directory) as f:
            if working_directory:
                f.write(
                    'cd {dir} || (echo "Unable to change to directory {dir}"; exit 255)\n\n'.format(
                        dir=working_directory
                    ).encode('utf-8')
                )

            f.write(command.encode('utf-8'))
            f.flush()

            name = os.path.basename(f.name)
            self.shell('chmod a+rx {}'.format(f.name))

            @nutcli.decorators.Timeout(timeout=timeout)
            def run():
                VagrantSSHActor(parent=self)(
                    guest=guest,
                    argv=['/shared/commands/{}'.format(name)]
                )

            run()

    def run_test_suite(self, suite, kwargs):
        with tempfile.TemporaryDirectory() as command_directory:
            TaskList('Test Case', logger=self.logger)([
                Task(case['name'])(self.task_test_case, kwargs, command_directory, case) for case in suite
            ]).execute()

    def task_test_case(self, task, kwargs, command_directory, case):
        args = types.SimpleNamespace(**kwargs)
        guests = case['machines']
        default_guest = 'client' if 'client' in guests else guests[0]
        timeout = case.get('timeout', None)

        tasks = TaskList(
            f'Test Case: {case["name"]}',
            logger=self.logger,
            duration=True
        )

        if args.destroy:
            tasks.append(
                Task(f'Destroying guests: {guests}', taskarg=False)(
                    VagrantDestroyActor(parent=self), guests
                )
            )
        else:
            # Guests needs to be restarted in order to mount directories.
            tasks.append(
                Task(f'Halting guests: {guests}', taskarg=False)(
                    VagrantHaltActor(parent=self), guests
                )
            )

        env = {
            'SSSD_TEST_SUITE_RSYNC': '{}:/shared/sssd'.format(kwargs['sssd']),
            'SSSD_TEST_SUITE_SSHFS': '{}:/shared/artifacts {}:/shared/commands'.format(
                kwargs['artifacts'], command_directory
            )
        }
        upshell = nutcli.shell.Shell(env=env)
        tasks.append(
            Task(f'Starting up guests: {guests}', taskarg=False)(
                VagrantUpActor(parent=self, shell=upshell), guests
            )
        )

        for step in case.get('tasks', []):
            tasks.append(
                Task(step.get('name', None))(
                    self.task_test_case_step, command_directory, step, default_guest
                )
            )

        tasks.append(
            Task('Archive artifacts', always=True, taskarg=False)(
                self.task_archive_artifacts, default_guest, command_directory, '/shared/sssd', case.get('artifacts', [])
            )
        )

        tasks.append(
            Task(f'Halting guests: {guests}', always=True, taskarg=False)(
                VagrantHaltActor(parent=self), guests
            )
        )

        tasks.execute(timeout=timeout)

    def task_test_case_step(self, task, command_directory, step, default_guest):
        working_directory = step.get('directory', '/shared/sssd')
        guest = step.get('run-on', default_guest)
        command = step.get('shell', 'exit 0')
        timeout = step.get('timeout', None)

        try:
            self.run_command_on_guest(guest, command_directory, working_directory, command, timeout)
        finally:
            self.task_archive_artifacts(
                guest, command_directory,
                working_directory, step.get('artifacts', [])
            )

    def task_archive_artifacts(self, guest, command_directory, working_directory, artifacts):
        def get_list(d, key):
            if key not in d:
                d[key] = []
            return d[key]

        paths = {}
        for item in artifacts:
            if type(item) == dict:
                files = get_list(paths, item.get('from', guest))
                for path in item.get('files', []):
                    files.append(path)
                continue

            files = get_list(paths, guest)
            files.append(item)

        for guest, paths in paths.items():
            commands = [
                'cp -f {path} /shared/artifacts &> /dev/null || echo "> Unable to archive {path}"'.format(path=path)
                for path in paths
            ]
            commands.append('exit 0')
            self.run_command_on_guest(guest, command_directory, working_directory, '\n'.join(commands))

    def task_up(self, task, config, guests, command_directory, sssd_directory, artifacts_directory):
        env = {
            'SSSD_TEST_SUITE_RSYNC': '{}:/shared/sssd'.format(sssd_directory),
            'SSSD_TEST_SUITE_SSHFS': '{}:/shared/artifacts {}:/shared/commands'.format(
                artifacts_directory, command_directory
            )
        }

        for guest in guests:
            self.vagrant(config, 'up', [guest], env=env, clear_env=True)


Commands = [
    Command('run', 'Run SSSD tests', RunTestsActor())
]
