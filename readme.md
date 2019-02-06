# Virtual Test Suite for SSSD

Virtual Test Suite for SSSD is a set of Vagrant and Ansible scripts that
will automatically setup and provision several virtual machines that you
can use to test SSSD.

It creates an out of the box working virtual environment with 389 Directory
Server, IPA and Active Directory servers. It also creates an SSSD client
machine enrolled to those servers, ready to build and debug your code.

## Virtual Environment

| Vagrant name |        IP         |        FQDN        |   Description                                                   |
|--------------|-------------------|--------------------|-----------------------------------------------------------------|
| ipa          | `192.168.100.10`  | `master.ipa.vm`    | IPA server                                                      |
| ldap         | `192.168.100.20`  | `master.ldap.vm`   | TLS ready 389 Directory Server                                  |
| client       | `192.168.100.30`  | `master.client.vm` | Client machine with configured SSSD                             |
| ad           | `192.168.100.110` | `root.ad.vm`       | Active Directory Forest root domain                             |
| ad-child     | `192.168.100.120` | `child.sub.ad.vm`  | Active Directory child domain                                   |

### Notes on the environment

* IPA machine also include a DNS server which is used by the client and AD
  machines, therefore it should be always up.
* The DNS server is also reachable from your host machine so you can access
  IPA web-ui directly from your browser at `master.ipa.vm`. You can import
  CA certificate from `shared-enrollment/ipa/ca.crt`
* Client machine has also some debug-info installed so you can debug SSSD better.
* AD servers must run two different types of Windows Server since available
  boxes use fixed machine SID and Active Directory requires different SID
  for each domain controller.

* There is one shared folder between Linux guests and host machine:
  * `./shared-enrollment => /shared/enrollment/` -- enrollment data such
    as certificates and keytabs are stored in this directory.

* Additionally, you can mount more folders by defining one or more of these variables:
  * `SSSD_TEST_SUITE_SSHFS` - mount folders with sshfs (recommended)
  * `SSSD_TEST_SUITE_NFS` - mount folders with nfs
  * `SSSD_TEST_SUITE_RSYNC` - mount folders with rsync
* Each variable takes the following format:
  * `host_path:guest_path host_path:guest_path ...`
  * For example:

```
export SSSD_TEST_SUITE_SSHFS=""

SSSD_TEST_SUITE_SSHFS+=" $MY_WORKSPACE:/shared/workspace"
SSSD_TEST_SUITE_SSHFS+=" $MY_USER_HOME/packages:/shared/packages"
```

* You can also define `SSSD_TEST_SUITE_BASHRC`. If this variable is set
  the file that it points to is automatically sourced from guest `.bashrc`.
  For example:

```
export SSSD_TEST_SUITE_BASHRC="/shared/workspace/my-scripts/vagrant-bashrc.sh"
```

### User Accounts

| Machine           |        Username         |   Password   |   Description    |
|-------------------|-------------------------|--------------|------------------|
| Any Linux machine | vagrant                 | vagrant      | Local user       |
| ad                | Administrator@ad.vm     | vagrant      | Domain user      |
| ad-child          | Administrator@sub.ad.vm | vagrant      | Domain user      |
| client            | user-1                  | 123456789    | LDAP domain user |
| client or ipa     | admin                   | 123456789    | IPA domain user  |

## Installation

### Prerequisites

This guide is written for Fedora systems. It may require different packages or
package tool on other Linux distributions.

**Needed resources:**
* Approximately `7 GiB` of operating memory
* Approximately `47 GiB` of disk space

### Running SSSD Test Suite

#### Quick start

You can use this one-liner as a quick start for the guest machines. It is further explained step
by step in the following sections.

```bash
./sssd-test-suite provision-host --pool $pool && ./sssd-test-suite up -s && ./sssd-test-suite provision -e
```

#### 1. Provision host machine

```bash
$ ./sssd-test-suite provision-host --pool $pool
```

This command will perform the following changes on your machine:
* Install ansible, libvirt, vagrant and other packages required by `sssd-test-suite`.
* Install required vagrant plugins.
* Configure NetworkManager's dnsmasq so all machines are resolvable through their DNS names.
* Install `polkit` rule for `libvirt` that will allow anyone to use `libvirt` without root password.
* Create libvirt directory pool called `sssd-test-suite` at `$pool`. Make sure there is plenty of disk space left.

#### 2. Provision guest machines

Now it is time to start up the guest machines. It is recommended to use `-s` parameter to start the guests one by one
due to timeout issues with Windows servers.

```bash
$ ./sssd-test-suite up -s
```

#### 3. Provision guest machines

Run the following command to provision guests machines. This step may take a long time (more than one hour) depending
on you system.

```bash
$ ./sssd-test-suite provision
```

#### 4. Enroll client to all domains

When the machines are provisioned you can enroll the client to LDAP, IPA and AD domains.

```bash
$ ./sssd-test-suite enroll
```

#### 5. Start working with guests

Finally, you can ssh to Linux machines and run remote desktop on Windows guests.

```bash
$ ./sssd-test-suite ssh client
$ ./sssd-test-suite rdp ad -- -g 90%
```

### Helpful commands

* Check guests status: `./sssd-test-suite status`
* Bring up guests: `./sssd-test-suite up -s`
* Destroy guests: `./sssd-test-suite destroy`
* Update boxes: `./sssd-test-suite update`
* Remove outdated boxes: `./sssd-test-suite prune`

See `./sssd-test-suite --help` for more commands.

## Tips

### Using NFS for shared folders

It is possible to setup NFS shared folders by exporting `SSSD_TEST_SUITE_NFS` variable.
However you need to make sure that NFS is installed and firewall is setup correctly
on your machine.

```
# dnf install -y firewalld
# firewall-cmd --permanent --add-service=nfs
# firewall-cmd --permanent --add-service=mountd
# firewall-cmd --permanent --add-service=rpc-bind
# systemctl reload firewalld.service
```

### Importing LDIF to the LDAP server

There are two scripts that you can use with provisioned LDAP server:
* `./provision/ldap-clear.sh` - this will remove all existing object from the server
* `./provision/ldap-import.sh LDIF-FILE` - this will import content of `LDIF-FILE` to the server

There are some prepared LDIF's at `./provision/ldif`.

### Switch vagrant boxes

There is a configuration file `config.json` where you can set different boxes
for different machines. You can also set `sshfs`, `rsync` and `nfs` shared folders
here in addition to those set by environment variables.

Example configuration files can be found at `./configs` directory.

Example:
```json
{
  "boxes": {
    "ad": {
      "name": "peru/windows-server-2016-standard-x64-eval",
      "url": "",
      "memory": 1024
    },
    "ad-child": {
      "name": "peru/windows-server-2016-standard-x64-eval",
      "url": "",
      "memory": 1024
    },
    "ipa": {
      "name": "fedora/28-cloud-base",
      "url": "",
      "memory": 2048
    },
    "ldap": {
      "name": "fedora/28-cloud-base",
      "url": "",
      "memory": 1024
    },
    "client": {
      "name": "fedora/28-cloud-base",
      "url": "",
      "memory": 2048
    }
  },
  "folders": {
    "sshfs": [],
    "rsync": [],
    "nfs": []
  }
}
```

### Re-use prepared vagrant boxes

We have prepared a [sssd-vagrant](https://app.vagrantup.com/sssd-vagrant) group on vagrant
cloud where we put already provisioned boxes that can be used directly on your machine.

The machines are not currently enrolled to each other so you need to run
`./sssd-test-suite up -s && ./sssd-test-suite provision -e`

