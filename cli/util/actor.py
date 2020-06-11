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
import nutcli


class TestSuiteActor(nutcli.commands.Actor):
    LinuxGuests = ['ipa', 'ldap', 'client']
    WindowsGuests = ['ad', 'ad-child']
    AllGuests = WindowsGuests + LinuxGuests

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.project_dir = os.path.abspath(
            os.path.dirname(os.path.realpath(__file__)) + '/../..'
        )

        self.ansible_dir = os.path.abspath(
            os.path.dirname(os.path.realpath(__file__)) + '/../../provision'
        )

        self.vagrant_dir = self.project_dir
