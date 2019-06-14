#!/bin/python3
# -*- coding: utf-8 -*-

import argcomplete
import argparse
import sys
import textwrap

# Command Actors
import commands.box as box
import commands.provision as provision
import commands.vagrant as vagrant
import commands.cloud as cloud
import commands.tests as tests

from lib.command import CommandParser, CommandGroup, Runner


class Program:
    def setup_parser(self):
        commands = CommandParser([
            CommandGroup('Vagrant Commands', vagrant.Commands),
            CommandGroup('Automation', [
                tests.Commands,
                provision.Commands,
                box.Commands,
                cloud.Commands
            ])
        ])

        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter
        )
        parser.add_argument(
            '-c', '--config', action='store', type=str, dest='config',
            help='Path to SSSD Test Suite configuration file',
            default=None
        )

        commands.setup_parser(parser)

        parser.epilog = textwrap.dedent('''
        If --config option is not set the default configuration file is
        read from SSSD_TEST_SUITE_CONFIG environment variable. If this
        variable is not set it defaults to config.json in the
        sssd-test-suite root directory.

        All commands should use the same configuration file. It is highly
        recommended to run 'destroy' command before switching to another
        configuration file.
        ''')

        argcomplete.autocomplete(parser)

        return parser

    def main(self, argv):
        return Runner('sssd-test-suite').execute(self.setup_parser(), argv)


if __name__ == "__main__":
    program = Program()
    sys.exit(program.main(sys.argv[1:]))
