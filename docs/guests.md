# SSSD Test Suite Guests

The `sssd-test-suite` creates the following guests machines:

| Vagrant name |        IP         |        FQDN        |   Description                                                   |
|--------------|-------------------|--------------------|-----------------------------------------------------------------|
| ipa          | `192.168.100.10`  | `master.ipa.vm`    | IPA server                                                      |
| ldap         | `192.168.100.20`  | `master.ldap.vm`   | TLS ready 389 Directory Server                                  |
| client       | `192.168.100.30`  | `master.client.vm` | Client machine with configured SSSD                             |
| ad           | `192.168.100.110` | `root.ad.vm`       | Active Directory Forest root domain                             |
| ad-child     | `192.168.100.120` | `child.sub.ad.vm`  | Active Directory child domain                                   |

The machines needs to be provisioned and properly enrolled into the domains.
See [Basic Usage](basic-usage.md) for more information.

## User Accounts

| Machine           |        Username           |   Password   |   Description     |
|-------------------|---------------------------|--------------|-------------------|
| Any Linux machine | vagrant                   | vagrant      | Local user        |
| ad                | Administrator@ad.vm       | vagrant      | Domain user       |
| ad-child          | Administrator@child.ad.vm | vagrant      | Domain user       |
| ipa               | admin                     | 123456789    | IPA administrator |

## Enrollment data

Enrollment data are stored in `./shared-enrollment` folder on the host machine.
This folder contains keytabs and certificates that are created when the machines
are enrolled into domains.

## Required resources

Required resources depend on your configuration but to run all guests together
with one of the example configuration you can expect the following requirements:

* Approximately `9 GiB` of available operating memory
* Approximately `50 GiB` of disk space

However AD boxes can operate with a lower amout of operating memory (1 GiB) so
the memory requirements can be reduced to approximately 7 GiB.
