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

import json
import requests
from clint.textui.progress import Bar as ProgressBar
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor


class VagrantCloud:
    class Box:
        def __init__(self, data):
            self.tag = data['tag']
            self.username = data['username']
            self.name = data['name']
            self.version = data['current_version']['version']

        def __lt__(self, other):
            return self.tag < other.tag

    def __init__(self, directory, token=None, username=None):
        self.cwd = directory
        self.token = token
        self.username = username
        self.loadConfiguration()

        self.api = {
            'search': 'https://app.vagrantup.com/api/v1/search',
            'box': {
                'get': 'https://app.vagrantup.com/api/v1/box/{username}/{boxname}',
                'update': 'https://app.vagrantup.com/api/v1/box/{username}/{boxname}',
                'create': 'https://app.vagrantup.com/api/v1/boxes'
            },
            'version': {
                'get': 'https://app.vagrantup.com/api/v1/box/{username}/{boxname}/version/{version}',
                'update': 'https://app.vagrantup.com/api/v1/box/{username}/{boxname}/version/{version}',
                'create': 'https://app.vagrantup.com/api/v1/box/{username}/{boxname}/versions',
                'release': 'https://app.vagrantup.com/api/v1/box/{username}/{boxname}/version/{version}/release'
            },
            'provider': {
                'get': 'https://app.vagrantup.com/api/v1/box/{username}/{boxname}/version/{version}/provider/{provider}',
                'update': 'https://app.vagrantup.com/api/v1/box/{username}/{boxname}/version/{version}/provider/{provider}',
                'create': 'https://app.vagrantup.com/api/v1/box/{username}/{boxname}/version/{version}/providers',
                'upload': 'https://app.vagrantup.com/api/v1/box/{username}/{boxname}/version/{version}/provider/{provider}/upload'
            }
        }

        self.authheader = {
            'Authorization': 'Bearer %s' % self.token
        }

    def loadConfiguration(self):
        try:
            with open('%s/vg-cloud.json' % self.cwd) as file:
                data = json.load(file)

            if self.token is None and 'token' in data:
                self.token = data['token']

            if self.username is None and 'username' in data:
                self.username = data['username']
        except FileNotFoundError:
            pass
        except:
            raise

        if self.token is None:
            raise ValueError('Vagrant cloud token is not set. Consider calling cloud-setup to remember this option.')

        if self.username is None:
            raise ValueError('Vagrant cloud username is not set. Consider calling cloud-setup to remember this option.')

    def apiError(self, response):
        if response.status_code == requests.codes.ok:
            return True

        print('Error %d on: %s' % (response.status_code, response.url))

        data = response.json()
        if 'errors' in data:
            for error in data['errors']:
                print('- %s' % error)

        response.raise_for_status()

    def apiGet(self, endpoint, args={}, params={}):
        r = requests.get(
            endpoint.format(**args),
            headers=self.authheader,
            params=params
        )

        self.apiError(r)
        return r

    def apiPost(self, endpoint, data, args={}, params={}, headers={}, isjson=True):
        (data, type) = self.processData(data, isjson)

        r = requests.post(
            endpoint.format(**args),
            params=params,
            headers={**self.authheader, **headers, **type},
            data=data
        )

        self.apiError(r)
        return r

    def apiPut(self, endpoint, data, args={}, params={}, headers={}, isjson=True):
        (data, type) = self.processData(data, isjson)

        r = requests.put(
            endpoint.format(**args),
            params=params,
            headers={**self.authheader, **headers, **type},
            data=data
        )

        self.apiError(r)
        return r

    def processData(self, data, isjson):
        if isjson:
            if data is None:
                return (None, {'Content-Type': 'application/json'})
            return (json.dumps(data), {'Content-Type': 'application/json'})

        return (data, {})

    def objectExists(self, endpoints, args={}):
        r = requests.get(
            endpoints['get'].format(**args),
            headers=self.authheader
        )

        if r.status_code == requests.codes.ok:
            return True

        if r.status_code == requests.codes.not_found:
            return False

        r.raise_for_status()

    def objectCreate(self, endpoints, data, args={}):
        if self.objectExists(endpoints, args=args):
            self.apiPut(endpoints['update'], data, args=args)
            return

        self.apiPost(endpoints['create'], data, args=args)

    def list(self):
        r = self.apiGet(self.api['search'], params={'q': self.username + '/'})

        boxes = []
        data = r.json()
        if 'boxes' in data:
            for box in data['boxes']:
                boxes.append(self.Box(box))

        boxes.sort()

        return boxes

    def boxCreate(self, name, summary=''):
        data = {
            'box': {
                'username': self.username,
                'name': name,
                'short_description': summary,
                'description': '',
                "is_private": False
            }
        }

        self.objectCreate(self.api['box'], data, args={
            'username': self.username,
            'boxname': name
        })

    def versionCreate(self, name, version, description=''):
        data = {
            'version': {
                'version': version,
                'description': description
            }
        }

        self.objectCreate(self.api['version'], data, args={
            'username': self.username,
            'boxname': name,
            'version': version
        })

    def versionRelease(self, name, version):
        self.apiPut(self.api['version']['release'], None, args={
            'username': self.username,
            'boxname': name,
            'version': version
        })

    def providerCreate(self, name, version, provider):
        data = {
            'provider': {
                'name': provider
            }
        }

        self.objectCreate(self.api['provider'], data, args={
            'username': self.username,
            'boxname': name,
            'version': version,
            'provider': provider
        })

    def providerUpload(self, name, version, provider, file):
        r = self.apiGet(self.api['provider']['upload'], args={
            'username': self.username,
            'boxname': name,
            'version': version,
            'provider': provider
        })

        data = r.json()

        encoder = MultipartEncoder({
            'file': (file, open(file, 'rb'), 'application/octet-stream')
        })
        bar = ProgressBar(expected_size=encoder.len, filled_char='=')

        def callback(monitor):
            bar.show(monitor.bytes_read)

        monitor = MultipartEncoderMonitor(encoder, callback)

        self.apiPut(data['upload_path'], monitor, isjson=False, headers={
            'Content-Type': monitor.content_type
        })
        print('')
