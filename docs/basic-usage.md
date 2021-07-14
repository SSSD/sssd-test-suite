# Basic usage

## Preparing host machine

The following command will install necessary requirements for the
`sssd-test-suite` command line interface and will prepare the host
machine so it is able to run and access the virtual machines.

```bash
$ ./sssd-test-suite provision host --pool $path-to-pool-directory
```

The command will:
* Install ansible, libvirt, vagrant and other packages required by `sssd-test-suite`.
* Install required vagrant plugins.
* Configure NetworkManager's dnsmasq so all machines are resolvable through their DNS names.
* Install `polkit` rule for `libvirt` that will allow anyone to use `libvirt` without root password.
* Create libvirt's `sssd-test-suite` directory storage pool at `$path-to-pool-directory`

## Preparing guests machines

First, you need to create configuration file at `./config.json`. You can choose
from one of the example configurations located at `./configs`. For example:

```bash
$ cp ./configs/sssd-f30.json ./config.json
```

Then you need to start, provision and enroll the guests.

```bash
$ ./sssd-test-suite up -s
$ ./sssd-test-suite provision guest all
$ ./sssd-test-suite provision enroll all
```

Now you are ready to use the guests.

You may need to change the `domains` section in sssd.conf to be `ipa.vm` or
`ad.vm` etc.

```bash
$ grep 'domains' /etc/sssd/sssd.conf
domains = ldap.vm
```

## Accessing the guest machines

The `sssd-test-suite` command line interface provides a wrapper around several
vagrant commands. See `./sssd-test-suite --help` for the list of all commands.

### Starting, halting and destroying guests

* To start all machines use `./sssd-test-suite up -s`. The `-s` parameter is
  optional and means that the machines will be started one by one instead of
  starting them all at once. This may reduce the load on the host machine if
  needed.
* To start only a subset of guests (e.g. client and ipa server) use
  `./sssd-test-suite up client ipa`.
* To halt the machines use `./sssd-test-suite halt`, you can start them again
  by running `up` command.
* To destroy (delete) the machines use `./sssd-test-suite destroy`.

### Logging into the machines

* Linux machines provide standard SSH access. To ssh to the machine (e.g. client)
run `./sssd-test-suite ssh client`.
* Windows machines provide access through RDP. You can use
  `./sssd-test-suite rdp ad -- -g 90%` to open remote desktop of `ad` guest.
  The parameter `-g 90%` opens a window sized to 90% of your screen resolution.

### Helpful commands

* Check guests status: `./sssd-test-suite status`
* Bring up guests: `./sssd-test-suite up -s`
* Destroy guests: `./sssd-test-suite destroy`
* Update boxes: `./sssd-test-suite update`
* Remove outdated boxes: `./sssd-test-suite prune`
* SSH to client: `./sssd-test-suite ssh client`
* RDP to ad: `./sssd-test-suite rdp ad -- -g 90%`
* Renew AD License: `./sssd-test-suite provision rearm`

See `./sssd-test-suite --help` for more commands.
