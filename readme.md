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
| ipa          | `192.168.100.10`  | `master.ipa.vm`    | IPA and main DNS server for zones 'vm' and network reverse zone |
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

* There are several shared folders between Linux guests and host machine:
  * `./shared-enrollment => /shared/enrollment/` -- enrollment data such
    as certificates and keytabs are stored in this directory.
  * `./shared-data => /shared/data/` -- custom data to share.
  * If `SSSD_SOURCE` environment variable is defined it will mount this
    directory at `/shared/sssd`
  * If `INCLUDE_DIR` environment variable is defined it will mount this
    directory at `/shared/scripts` and all scripts in this directory
    are automatically sourced by `.bashrc`. You can use it for example
    to source
    [SSSD Development Scripts](https://github.com/pbrezina/sssd-dev-utils).
    
* If you choose to use `INCLUDE_DIR` to source your scripts, you can expect
  that `VAGRANT=yes` is defined when a script is executed in the virtual
  environment.
  
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
* Approximately `5.5 GiB` of operating memory
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

2. Install latest Vagrant (at least 2.0 is needed)
```bash
# dnf remove vagrant
# dnf install -y https://releases.hashicorp.com/vagrant/2.0.0/vagrant_2.0.0_x86_64.rpm
```

3. Install packages needed for Vagrant's libvirt plugin
```bash
# dnf install -y         \
    qemu-kvm               \
    libvirt-daemon-kvm     \
    libvirt-devel          \
    ruby-devel             \
    rubygem-ruby-libvirt
```

4. Install libvirt plugin for Vagrant
```bash
$ vagrant plugin install vagrant-libvirt
```

### Preparing machines

Since Vagrant ansible plugin is not yet well suited for a multi-machine
provisioning, it needs to be done by a custom shell script instead of
vagrant native provisioning tools.

Simply call `./setup.sh` and it will prepare your host machine to use internal
DNS server (only for zones managed by the server). It will also include `polkit`
rule for `libvirt` so it does not require `root` password each time `vagrant`
is used. And at last, it will setup your firewall to allow required services
for NFS.

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
