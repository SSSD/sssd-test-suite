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

    def __init__(self, username, token):
        self.check_credentials(username, token)
        self.username = username
        self.token = token
        self.url = 'https://app.vagrantup.com/api/v1'
        self.api = {
            'search': '{url}/search',
            'box': {
                'get': '{url}/box/{username}/{boxname}',
                'update': '{url}/box/{username}/{boxname}',
                'create': '{url}/boxes'
            },
            'version': {
                'get': '{url}/box/{username}/{boxname}/version/{version}',
                'update': '{url}/box/{username}/{boxname}/version/{version}',
                'create': '{url}/box/{username}/{boxname}/versions',
                'release': '{url}/box/{username}/{boxname}/version/{version}/release',
                'delete': '{url}/box/{username}/{boxname}/version/{version}'
            },
            'provider': {
                'get': '{url}/box/{username}/{boxname}/version/{version}/provider/{provider}',
                'update': '{url}/box/{username}/{boxname}/version/{version}/provider/{provider}',
                'create': '{url}/box/{username}/{boxname}/version/{version}/providers',
                'upload': '{url}/box/{username}/{boxname}/version/{version}/provider/{provider}/upload'
            }
        }

        self.authheader = {
            'Authorization': 'Bearer %s' % self.token
        }

    def check_credentials(self, username, token):
        if not username:
            raise ValueError('Vagrant cloud username is not set.')

        if not token:
            raise ValueError('Vagrant cloud token is not set.')

    def api_error(self, response):
        if response.status_code == requests.codes.ok:
            return True

        print('Error %d on: %s' % (response.status_code, response.url))

        data = response.json()
        if 'errors' in data:
            for error in data['errors']:
                print('- %s' % error)

        response.raise_for_status()

    def api_get(self, endpoint, args=None, params=None):
        args = args if args is not None else {}
        params = params if params is not None else {}

        r = requests.get(
            endpoint.format(**args, url=self.url),
            headers=self.authheader,
            params=params
        )

        self.api_error(r)
        return r

    def api_post(self, endpoint, data, args=None, params=None, headers=None, isjson=True):
        args = args if args is not None else {}
        params = params if params is not None else {}
        headers = headers if headers is not None else {}

        (data, type) = self.process_data(data, isjson)

        r = requests.post(
            endpoint.format(**args, url=self.url),
            params=params,
            headers={**self.authheader, **headers, **type},
            data=data
        )

        self.api_error(r)
        return r

    def api_put(self, endpoint, data, args=None, params=None, headers=None, isjson=True):
        args = args if args is not None else {}
        params = params if params is not None else {}
        headers = headers if headers is not None else {}

        (data, type) = self.process_data(data, isjson)

        r = requests.put(
            endpoint.format(**args, url=self.url),
            params=params,
            headers={**self.authheader, **headers, **type},
            data=data
        )

        self.api_error(r)
        return r

    def api_delete(self, endpoint, args=None, params=None):
        args = args if args is not None else {}
        params = params if params is not None else {}

        r = requests.delete(
            endpoint.format(**args, url=self.url),
            headers=self.authheader,
            params=params
        )

        self.api_error(r)
        return r

    def process_data(self, data, isjson):
        if isjson:
            if data is None:
                return (None, {'Content-Type': 'application/json'})
            return (json.dumps(data), {'Content-Type': 'application/json'})

        return (data, {})

    def object_exists(self, endpoints, args=None):
        args = args if args is not None else {}

        r = requests.get(
            endpoints['get'].format(**args, url=self.url),
            headers=self.authheader
        )

        if r.status_code == requests.codes.ok:
            return True

        if r.status_code == requests.codes.not_found:
            return False

        r.raise_for_status()

    def object_create(self, endpoints, data, args=None):
        args = args if args is not None else {}

        if self.object_exists(endpoints, args=args):
            self.api_put(endpoints['update'], data, args=args)
            return

        self.api_post(endpoints['create'], data, args=args)

    def list_boxes(self):
        r = self.api_get(self.api['search'], params={
            'q': self.username + '/',
            'limit': 100
        })

        boxes = []
        data = r.json()
        if 'boxes' in data:
            for box in data['boxes']:
                boxes.append(self.Box(box))

        boxes.sort()

        return boxes

    def list_versions(self, boxname):
        r = self.api_get(self.api['box']['get'], args={
            'username': self.username,
            'boxname': boxname
        })

        versions = []
        data = r.json()
        if 'versions' in data:
            for version in data['versions']:
                versions.append(version['version'])

        versions.sort()

        return versions

    def box_create(self, name, summary=''):
        data = {
            'box': {
                'username': self.username,
                'name': name,
                'short_description': summary,
                'description': '',
                "is_private": False
            }
        }

        self.object_create(self.api['box'], data, args={
            'username': self.username,
            'boxname': name
        })

    def version_create(self, name, version, description=''):
        data = {
            'version': {
                'version': version,
                'description': description
            }
        }

        self.object_create(self.api['version'], data, args={
            'username': self.username,
            'boxname': name,
            'version': version
        })

    def version_release(self, name, version):
        self.api_put(self.api['version']['release'], None, args={
            'username': self.username,
            'boxname': name,
            'version': version
        })

    def version_delete(self, name, version):
        self.api_delete(self.api['version']['delete'], args={
            'username': self.username,
            'boxname': name,
            'version': version
        })

    def provider_create(self, name, version, provider):
        data = {
            'provider': {
                'name': provider
            }
        }

        self.object_create(self.api['provider'], data, args={
            'username': self.username,
            'boxname': name,
            'version': version,
            'provider': provider
        })

    def provider_upload(self, name, version, provider, file):
        r = self.api_get(self.api['provider']['upload'], args={
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

        self.api_put(data['upload_path'], monitor, isjson=False, headers={
            'Content-Type': monitor.content_type
        })
        print('')
