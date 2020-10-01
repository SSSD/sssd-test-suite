# Virtual Test Suite for SSSD

Virtual Test Suite for SSSD is a set of Vagrant and Ansible scripts that
will automatically setup and provision several virtual machines that you
can use to test SSSD.

It creates an out of the box working virtual environment with 389 Directory
Server, IPA and Active Directory servers. It also creates an SSSD client
machine enrolled to those servers, ready to build and debug your code.

## Table Of Contents

1. [Basic usage](./docs/basic-usage.md)
2. [Guest description](./docs/guests.md)
3. [Configuration file](./docs/configuration.md)
4. [Environment variables](./docs/environment-variables.md)
5. [Tips and Tricks](./docs/tips.md)
6. [Running SSSD tests](./docs/running-tests.md)
7. [Creating new boxes](./docs/new-boxes.md)

## Quick Setup

The following examples uses the `POOL_DIR` variable. Set this variable to
a directory that will hold the `sssd-test-suite` libvirt's pool. The directory
should be on a large file system to hold all virtual machines. The directory
must not be a existing pool.

### Cloning repository and installing CLI dependencies

This project depends on multiple Python dependencies listed in
[`requirements.txt`](./requirements.txt) and
[`Ansible`](https://www.ansible.com).

You can use these commands to install the dependencies on Fedora:

```console
$ git clone https://github.com/SSSD/sssd-test-suite.git
$ sudo dnf install ansible
$ sudo pip3 install -r ./requirements.txt
```

There are number of other dependencies that are installed automatically using
`sssd-test-suite provision host` command. You can see these dependencies
[here](./provision/roles/host/tasks/Fedora.yml).

### I want to try SSSD with FreeIPA

```console
$ POOL_DIR=/path/to/sssd/test/suite/pool
$ git clone https://github.com/SSSD/sssd-test-suite.git
$ cd sssd-test-suite
$ sudo dnf install ansible
$ sudo pip3 install -r ./requirements.txt
$ ./sssd-test-suite provision host --pool "$POOL_DIR"
$ cp ./configs/sssd-f30.json config.json
$ ./sssd-test-suite provision enroll client ipa
```

Now you can:
* ssh to the client machine with `./sssd-test-suite ssh client`
* ssh to the ipa machine with `./sssd-test-suite ssh ipa`
* open ipa web interface at `https://master.ipa.vm`

### I want to try SSSD with native LDAP

```console
$ POOL_DIR=/path/to/sssd/test/suite/pool
$ git clone https://github.com/SSSD/sssd-test-suite.git
$ cd sssd-test-suite
$ sudo dnf install ansible
$ sudo pip3 install -r ./requirements.txt
$ ./sssd-test-suite provision host --pool "$POOL_DIR"
$ cp ./configs/sssd-f30.json config.json
$ ./sssd-test-suite provision enroll client ldap
```

Now you can:
* ssh to the client machine with `./sssd-test-suite ssh client`
* ssh to the ldap machine with `./sssd-test-suite ssh ldap`
* access LDAP server at `ldap://master.ldap.vm`
* load example data to the server with `./sssd-test-suite provision ldap --clear ./provision/ldif/basic.ldif`

### I want to try SSSD with Active Directory

```console
$ POOL_DIR=/path/to/sssd/test/suite/pool
$ git clone https://github.com/SSSD/sssd-test-suite.git
$ cd sssd-test-suite
$ sudo dnf install ansible
$ sudo pip3 install -r ./requirements.txt
$ ./sssd-test-suite provision host --pool "$POOL_DIR"
$ cp ./configs/sssd-f30.json config.json
$ ./sssd-test-suite provision enroll client ad
```

Now you can:
* ssh to the client machine with `./sssd-test-suite ssh client`
* open remote desktop of ad machine with `./sssd-test-suite rdp ad -- -g 90%`

### I want to try SSSD with FreeIPA, LDAP and Active Directory (including child domain)

```console
$ POOL_DIR=/path/to/sssd/test/suite/pool
$ git clone https://github.com/SSSD/sssd-test-suite.git
$ cd sssd-test-suite
$ sudo dnf install ansible
$ sudo pip3 install -r ./requirements.txt
$ ./sssd-test-suite provision host --pool "$POOL_DIR"
$ cp ./configs/sssd-f30.json config.json
$ ./sssd-test-suite provision enroll all
```

Now you can:
* ssh to the client machine with `./sssd-test-suite ssh client`
* ssh to the ldap machine with `./sssd-test-suite ssh ldap`
* ssh to the ipa machine with `./sssd-test-suite ssh ipa`
* open remote desktop of ad machine with `./sssd-test-suite rdp ad -- -g 90%`
* open remote desktop of ad-child machine with `./sssd-test-suite rdp ad-child -- -g 90%`
* open ipa web interface at `https://master.ipa.vm`
* access LDAP server at `ldap://master.ldap.vm`
* load example data to the server with `./sssd-test-suite provision ldap --clear ./provision/ldif/basic.ldif`
