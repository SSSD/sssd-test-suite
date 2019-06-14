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

from collections import OrderedDict


# Based on patch from https://bugs.python.org/issue9341
class SubparsersAction(argparse._SubParsersAction):
    class _PseudoGroup(argparse.Action):
        def __init__(self, container, title):
            super().__init__(option_strings=[], dest=title)
            self.container = container
            self._choices_actions = []

        def add_parser(self, name, **kwargs):
            # add the parser to the main Action, but move the pseudo action
            # in the group's own list
            parser = self.container.add_parser(name, **kwargs)
            choice_action = self.container._choices_actions.pop()
            self._choices_actions.append(choice_action)
            return parser

        def _get_subactions(self):
            return self._choices_actions

        def add_parser_group(self, title):
            # the formatter can handle recursive subgroups
            grp = SubparsersAction._PseudoGroup(self, title)
            self._choices_actions.append(grp)
            return grp

    def add_parser_group(self, title):
        grp = self._PseudoGroup(self, title)
        self._choices_actions.append(grp)
        return grp


class UniqueAppendAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        values = self._values_to_list(self._get_values(values))
        if not hasattr(namespace, self.dest):
            setattr(namespace, self.dest, values)

        current = getattr(namespace, self.dest)

        # Default value is set automatically, we must unset it.
        if current == self.default:
            current = None

        current = self._values_to_list(current)
        if current is None:
            current = []

        values = list(OrderedDict.fromkeys(current + values))
        setattr(namespace, self.dest, values)

    def _get_values(self, values):
        return values

    def _values_to_list(self, values):
        if values is None:
            return []

        if type(values) == list:
            return values

        return [values]


class UniqueAppendConstAction(UniqueAppendAction):
    def __init__(self, *args, **kwargs):
        kwargs['nargs'] = 0
        super().__init__(*args, **kwargs)

    def _get_values(self, values):
        return self.const
