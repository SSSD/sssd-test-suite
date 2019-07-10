# Tips and Tricks

## Using NFS for shared folders

It is possible to setup NFS shared folders by exporting `SSSD_TEST_SUITE_NFS`
variable or setting a shared folder in the configuration file. However you need
to make sure that NFS is installed and firewall is setup correctly on your machine.

```
# dnf install -y firewalld
# firewall-cmd --permanent --add-service=nfs
# firewall-cmd --permanent --add-service=mountd
# firewall-cmd --permanent --add-service=rpc-bind
# systemctl reload firewalld.service
```

## Importing LDIF to the LDAP server

You can provision the LDAP server with a custom LDIF file with:

```bash
./sssd-test-suite provision ldap --clear path-to-ldif-file
```

There are some prepared LDIF files at `./provision/ldif`.

### Re-use prepared vagrant boxes

We have prepared a [sssd-vagrant](https://app.vagrantup.com/sssd-vagrant) group
on vagrant cloud where we put already provisioned boxes that can be used
directly on your machine. The guests are provisioned and require only enrolling
to domains with `./sssd-test-suite provision enroll`.

Unfortunately, the Windows licence prohibits us from distributed prepared
Windows machines so these still needs to be created from scratch.

To setup all machines, run:

```bash
$ ./sssd-test-suite up -s
$ ./sssd-test-suite provision guest all
$ ./sssd-test-suite provision enroll all
```

If you need only the Linux machines, you can use:

```bash
$ ./sssd-test-suite up ipa ldap client -s
$ ./sssd-test-suite provision enroll ipa ldap client
```
