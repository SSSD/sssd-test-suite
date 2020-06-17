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

import nutcli
import yaml
from nutcli.commands import Command
from nutcli.tasks import Task, TaskList

from commands.vagrant import (VagrantDestroyActor, VagrantHaltActor,
                              VagrantPruneActor, VagrantSSHActor,
                              VagrantUpActor, VagrantUpdateActor)
from util.actor import TestSuiteActor


class TestCase(object):
    def __init__(
        self, actor, sssd_dir, artifacts_dir, case_dir, destroy_guests,
        name, guests, tasks, artifacts, timeout
    ):
        self.actor = actor
        self.sssd_dir = sssd_dir
        self.artifacts_dir = artifacts_dir
        self.destroy_guests = destroy_guests
        self.case_dir = case_dir

        self.name = name
        self.guests = guests if guests else ['client']
        self.tasks = tasks
        self.artifacts = artifacts
        self.timeout = timeout

    def get_tasks(self):
        case_tasks = []
        for task in self.tasks:
            artifacts = TestArtifacts(
                self.actor,
                self.case_dir,
                task.get('run-on', self.guests[0]),
                task.get('artifacts', [])
            )

            case_tasks.append(Task(
                name=task.get('name', None)
            )(
                TestCaseTask(
                    self.actor,
                    self.case_dir,
                    task.get('run-on', self.guests[0]),
                    task.get('shell', 'exit 0'),
                    artifacts,
                    task.get('directory', '/shared/sssd'),
                    task.get('timeout', None)
                ).execute
            ))

        return case_tasks

    def get_tasklist(self):
        artifacts = TestArtifacts(
            self.actor,
            self.case_dir,
            self.guests[0],
            self.artifacts
        )

        upshell = nutcli.shell.Shell(env={
            'SSSD_TEST_SUITE_RSYNC': f'{self.sssd_dir}:/shared/sssd',
            'SSSD_TEST_SUITE_SSHFS':
                f'{self.artifacts_dir}:/shared/artifacts'
                + f' {self.case_dir}:/shared/commands'
        })

        return TaskList(
            name=self.name,
            logger=self.actor.logger,
            timeout=self.timeout
        )([
            Task(
                name=f'Destroying guests: {self.guests}',
                enabled=self.destroy_guests
            )(
                VagrantDestroyActor(parent=self.actor), self.guests
            ),
            Task(
                name=f'Halting guests: {self.guests}',
                enabled=not self.destroy_guests
            )(
                VagrantHaltActor(parent=self.actor), self.guests
            ),
            Task(
                name=f'Starting guests: {self.guests}'
            )(
                VagrantUpActor(parent=self.actor, shell=upshell), self.guests
            ),
            *self.get_tasks(),
            Task(
                name=f'Archive artifacts'
            )(
                artifacts.archive
            ),
            Task(
                name=f'Halting guests: {self.guests}',
                always=True
            )(
                VagrantHaltActor(parent=self.actor), self.guests
            ),
        ])


class TestCommand(object):
    def __init__(self, actor, case_dir, cwd=None, timeout=None):
        self.actor = actor
        self.case_dir = case_dir
        self.cwd = cwd
        self.timeout = timeout

    def run_command(self, guest, command):
        with tempfile.NamedTemporaryFile(dir=self.case_dir) as f:
            if self.cwd is not None:
                self._change_directory(f, self.cwd)

            f.write(command.encode('utf-8'))
            f.flush()
            os.fchmod(f.fileno(), 0o755)

            @nutcli.decorators.Timeout(timeout=self.timeout)
            def run():
                VagrantSSHActor(parent=self.actor)(
                    guest=guest,
                    argv=[f'/shared/commands/{os.path.basename(f.name)}']
                )

            run()

    def _change_directory(self, f, dest):
        f.write(textwrap.dedent(f'''
        cd {dest} || (echo "Unable to change to directory {dest}"; exit 255)

        ''').encode('utf-8'))


class TestCaseTask(TestCommand):
    def __init__(
        self, actor, case_dir,
        guest, command, artifacts=None, cwd=None, timeout=None
    ):
        super().__init__(actor, case_dir, cwd, timeout)

        self.guest = guest
        self.command = command
        self.artifacts = artifacts

    def execute(self):
        try:
            self.run_command(self.guest, self.command)
        finally:
            self.artifacts.archive()


class TestArtifacts(TestCommand):
    def __init__(self, actor, case_dir, default_guest, artifacts, cwd=None):
        super().__init__(actor, case_dir, cwd, timeout=None)

        self.default_guest = default_guest
        self.artifacts = artifacts

        '''
        artifacts: (optional)
        - list of paths (guest is client or machines[0])
        - from: guest
          files:
          - list of files
        '''

    def get_files_map(self):
        def get_guest_list(d, guest):
            if guest not in d:
                d[guest] = []

            return d[guest]

        files_map = {}
        for item in self.artifacts:
            if type(item) == dict:  # {'from': guest, 'files': [files]}
                files_list = get_guest_list(
                    files_map, item.get('from', self.default_guest)
                )
                files_list.extend(item)
            else:  # [files]
                files_list = get_guest_list(files_map, self.default_guest)
                files_list.append(item)

        return files_map

    def archive(self):
        for guest, files in self.get_files_map().items():
            copy = [
                f'cp -fr {f} /shared/artifacts/ &> /dev/null'
                + f'|| echo "> Unable to archive {f}"'
                for f in files
            ]

            self.run_command(guest, '\n'.join(copy))


class RunTestsActor(TestSuiteActor):
    """
    Test Suite YAML Format:

    - name: Test Case Name
      machines:
      - list of machines to start
      tasks:
      - name: Task Name (optional)
        run-on: guest (optional, defaults to client or machines[0])
        directory: working directory (optional, default to /shared/sssd)
        shell: pwd
        timeout: timeout (optional
        artifacts: (optional)
        - list of paths (guest is client or machines[0])
        - from: guest
          files:
          - list of files
      timeout: timeout (optional)
      artifacts: (optional)
      - list of paths (guest is client or machines[0])
      - from: guest
        files:
        - list of files
    """

    def setup_parser(self, parser):
        parser.add_argument(
            '-s', '--sssd', action='store', type=str, dest='sssd_dir',
            help='Path to SSSD source directory.',
            required=True
        )

        parser.add_argument(
            '-a', '--artifacts', action='store', type=str, dest='artifacts_dir',
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
            '-t', '--test-config', action='store', type=str, dest='suite',
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

    def __call__(self, sssd_dir, artifacts_dir, update, prune, suite, destroy):
        suite = self.load_test_suite(suite, sssd_dir)

        required_guests = set()
        for case in suite:
            required_guests.update(case.get('machines', []))
        required_guests = list(required_guests)

        tasks = TaskList('tesẗ́-suite', logger=self.logger)([
            TaskList(
                tag='preparation',
                name='Preparation',
                logger=self.logger
            )([
                Task('Creating artifacts directory')(
                    lambda: self.shell(['mkdir', '-p', artifacts_dir])
                ),
                Task('Updating boxes', enabled=update)(
                    VagrantUpdateActor(parent=self), guests=required_guests
                ),
                Task('Removing outdated boxes', enabled=prune)(
                    VagrantPruneActor(parent=self), force=True
                )
            ])
        ])

        with tempfile.TemporaryDirectory() as case_dir:
            for case in suite:
                test_case = TestCase(
                    actor=self,
                    sssd_dir=sssd_dir,
                    artifacts_dir=artifacts_dir,
                    case_dir=case_dir,
                    destroy_guests=destroy,
                    name=case.get('name', None),
                    guests=case.get('machines', ['client']),
                    tasks=case.get('tasks', []),
                    artifacts=case.get('artifacts', []),
                    timeout=case.get('timeout', None)
                )

                tasks.append(test_case.get_tasklist())

            tasks.execute()

        return 0

    def load_test_suite(self, config, sssd):
        if config is None:
            config = f'{sssd}/contrib/test-suite/test-suite.yml'

        with open(config) as f:
            return yaml.safe_load(f)


Commands = [
    Command('run', 'Run SSSD tests', RunTestsActor())
]
