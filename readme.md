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

* There are two shared folders between Linux guests and host machine:
  * `./shared-enrollment => /shared/enrollment/` -- enrollment data such
    as certificates and keytabs are stored in this directory.
  * `./shared-data => /shared/data/` -- custom data to share.
  
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

1. Install Ansible
```bash
# dnf install -y       \
    ansible            \
    libselinux-python  \
    python-dnf         \
    python2-winrm      \
    python3-winrm
```

2. Install latest Vagrant (at least 2.0 is needed) and required plugins
```bash
# dnf install -y           \
    qemu-kvm               \
    libvirt-daemon-kvm     \
    libvirt-devel          \
    ruby-devel             \
    rubygem-ruby-libvirt   \
    vagrant                \
    vagrant-sshfs          \
    vagrant-libvirt        \
```
3. Install winrm plugin for Vagrant
```bash
$ vagrant plugin install winrm
$ vagrant plugin install winrm-fs
$ vagrant plugin install winrm-elevated
```

### Preparing machines

For the first time setup run `./setup.sh` within the source directory. This script
will provision your host machine and bring up and provision the guests.

This is a list of changes to your host machine:

1. Install required packages
2. Configure `dnsmasq` via `NetworkManager` to resolve all machines through DNS names.
3. Install `polkit` rule for `libvirt` so it does not require `root` password each time `vagrant`
is used.

```bash
$ ./setup.sh
```

**Note:** The provisioning will take a long time (approximately one hour)
so be patient.

## Usage

Now you are ready to use Vagrant tool to operate on these machines. For example:

```bash
# SSH to IPA server
vagrant ssh ipa

#  RDP into AD server
vagrant rdp ad -- -g 1800x960

# Halt Windows machines to save resources
vagrant halt ad
vagrant halt ad-child

# Restore Windows machines when needed
vagrant up ad
vagrant up ad-child
```

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
    "sshfs": [
      {
        "host": "./shared-enrollment",
        "guest": "/shared/enrollment"
      }
    ],
    "rsync": [],
    "nfs": []
  }
}
```

### Create your own provisioned box

It is possible to create pre-provisioned boxes in order to speed up the first time setup.

1. Run `./setup.sh` without machines enrollment
```bash
vagrant destroy
./setup.sh --skip-tags "enroll-all"
```
2. Run `./create_boxes.sh` (see `./create_boxes.sh --help`)
```bash
./create_boxes.sh fedora28 http://sssd.ci /home/qemu
```
3. Modify `config.json` to use your new boxes
4. Establish trust between IPA and AD and enroll client to domains
```bash
./provision.sh ./provision/enroll.yml
```

### Re-use prepared vagrant boxes

We have prepared a [sssd-vagrant](https://app.vagrantup.com/sssd-vagrant) group on vagrant
cloud where we put already provisioned boxes that can be used directly on your machine.

The machines are not currently enrolled to each other so you need to run one of two
provisioning scripts:

1. `./up.sh && ./provision.sh ./provision/prepare-guests.yml` -- if you need to provision
one or more machines.
2. `./up.sh && ./provision.sh ./provision/enroll.yml` -- if all machines are provisioned
and you only need to establish trust between IPA and AD domains and enroll client into them.

