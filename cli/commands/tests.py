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
import yaml

from commands.box import PruneBoxActor
from commands.vagrant import VagrantCommandActor, VagrantDestroyActor
from lib.command import CommandList, Command
from lib.task import Task
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
        This file can be specified with --suite parameter. If not set,
        $sssd/contrib/test-suite/test-suite.yml is used.
        ''')

    def run(self, args):
        suite = self.load_test_suite(args)
        self.prepare_environment(suite, args)
        self.run_test_suite(suite, args)

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
    def load_test_suite(self, args):
        config = args.test_config
        if config is None:
            config = '{}/contrib/test-suite/test-suite.yml'.format(args.sssd)

        with open(config) as f:
            return yaml.safe_load(f)

    def run_command_on_guest(self, config, guest, command_directory, working_directory, command, timeout=None):
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
            self.vagrant(config, 'ssh', [guest], ['/shared/commands/{}'.format(name)], timeout=timeout)

    def prepare_environment(self, suite, args):
        tasks = self.tasklist('Preparation')
        tasks.add('Creating artifacts directory', self.task_create_artifacts_dir, args.artifacts)
        if args.update:
            tasks.add('Updating boxes', self.task_update, suite, args.config)
        if args.prune:
            tasks.add('Removing outdated boxes', self.task_prune, args.config)
        tasks.run()

    def run_test_suite(self, suite, args):
        with tempfile.TemporaryDirectory() as command_directory:
            tasks = self.tasklist('Test Case')
            for case in suite:
                tasks.add(case['name'], self.task_test_case, args, command_directory, case)
            tasks.run()

    def task_test_case(self, task, args, command_directory, case):
        guests = case['machines']
        default_guest = 'client' if 'client' in guests else guests[0]
        timeout = case.get('timeout', None)

        tasks = self.tasklist('Test Case: {}'.format(case['name']))
        
        if args.destroy:
            tasks.add(
                'Destroying guests: {}'.format(guests), self.task_destroy,
                args.config, guests
            )
        else:
            # Guests needs to be restarted in order to mount directories.
            tasks.add(
                'Halting guests: {}'.format(guests), self.task_halt,
                args.config, guests,
                run_on_error=True
            )

        tasks.add(
            'Starting up guests: {}'.format(guests), self.task_up,
            args.config, guests, command_directory, args.sssd, args.artifacts
        )

        for step in case.get('tasks', []):
            tasks.add(
                step.get('name', ''), self.task_test_case_step,
                args.config, command_directory, step, default_guest
            )

        tasks.add(
            'Archive artifacts', self.task_archive_artifacts,
            args.config, default_guest, command_directory, '/shared/sssd', case.get('artifacts', []),
            run_on_error=True
        )

        tasks.add(
            'Halting guests: {}'.format(guests), self.task_halt,
            args.config, guests,
            run_on_error=True
        )

        tasks.run(timeout=timeout, timeout_message='Test case "{}" timed out'.format(case['name']))

    def task_test_case_step(self, task, config, command_directory, step, default_guest):
        working_directory = step.get('directory', '/shared/sssd')
        guest = step.get('run-on', default_guest)
        command = step.get('shell', 'exit 0')
        timeout = step.get('timeout', None)

        try:
            self.run_command_on_guest(config, guest, command_directory, working_directory, command, timeout)
        finally:
            self.task_archive_artifacts(
                None, config, guest, command_directory,
                working_directory, step.get('artifacts', [])
            )

    def task_archive_artifacts(self, task, config, guest, command_directory, working_directory, artifacts):
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
            self.run_command_on_guest(config, guest, command_directory, working_directory, '\n'.join(commands))

    def task_create_artifacts_dir(self, task, artifacts_dir):
        self.shell(['mkdir', '-p', artifacts_dir])

    def task_update(self, task, suite, config):
        machines = set()
        for case in suite:
            machines.update(case.get('machines', []))

        self.call(VagrantCommandActor('box update'), config=config, sequence=False, guests=list(machines))

    def task_prune(self, task, config):
        self.call(PruneBoxActor, config=config)

    def task_destroy(self, task, config, guests):
        self.call(VagrantDestroyActor, config=config, sequence=False, guests=guests)

    def task_up(self, task, config, guests, command_directory, sssd_directory, artifacts_directory):
        env = {
            'SSSD_TEST_SUITE_RSYNC': '{}:/shared/sssd'.format(sssd_directory),
            'SSSD_TEST_SUITE_SSHFS': '{}:/shared/artifacts {}:/shared/commands'.format(
                artifacts_directory, command_directory
            )
        }

        for guest in guests:
            self.vagrant(config, 'up', [guest], env=env, clear_env=True)

    def task_halt(self, task, config, guests):
        self.call(VagrantCommandActor('halt'), config=config, sequence=False, guests=guests)


Commands = CommandList([
    Command('run', 'Run SSSD tests', RunTestsActor),
])
