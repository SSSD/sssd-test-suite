#!/bin/python3
# -*- coding: utf-8 -*-

import argparse
import sys
import textwrap

import argcomplete
import nutcli.commands
import nutcli.runner

import commands.box
import commands.cloud
import commands.provision
import commands.tests
import commands.vagrant


class Program:
    def setup_parser(self):
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter
        )

        parser.add_argument(
            '-c', '--config', action='store', type=str, dest='config',
            help='Path to SSSD Test Suite configuration file',
            default=None
        )

        parser.epilog = textwrap.dedent('''
        If --config option is not set the default configuration file is
        read from SSSD_TEST_SUITE_CONFIG environment variable. If this
        variable is not set it defaults to config.json file in the
        sssd-test-suite root directory.

        All commands should use the same configuration file. It is highly
        recommended to run 'destroy' command before switching to another
        configuration file.
        ''')

        nutcli.commands.CommandParser()([
            nutcli.commands.CommandGroup('Vagrant Commands')([
                commands.vagrant.Commands,
            ]),
            nutcli.commands.CommandGroup('Automation')([
                commands.tests.Commands,
                commands.provision.Commands,
                commands.box.Commands,
                commands.cloud.Commands
            ])
        ]).setup_parser(parser)
        argcomplete.autocomplete(parser)

        return parser

    def main(self, argv):
        parser = self.setup_parser()
        runner = nutcli.runner.Runner('sssd-test-suite', parser).setup_parser()

        args = runner.parse_args(argv)
        runner.default_logger()
        return runner.execute(args)


if __name__ == "__main__":
    program = Program()
    sys.exit(program.main(sys.argv[1:]))
