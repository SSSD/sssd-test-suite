# Environment variables

`sssd-test-suite` reads multiple environment variables that you can use
(for example in your bash rc files).

## Shared folders

You can share your folders by defining one or more of these variables:

* `SSSD_TEST_SUITE_SSHFS` - mount folders with sshfs (recommended)
* `SSSD_TEST_SUITE_NFS` - mount folders with nfs
* `SSSD_TEST_SUITE_RSYNC` - mount folders with rsync

Each variable takes the following format:
* `host_path:guest_path host_path:guest_path ...`
* For example:
```
export SSSD_TEST_SUITE_SSHFS=""
SSSD_TEST_SUITE_SSHFS+=" $MY_WORKSPACE:/shared/workspace"
SSSD_TEST_SUITE_SSHFS+=" $MY_USER_HOME/packages:/shared/packages"
```

## .bashrc

`SSSD_TEST_SUITE_BASHRC` points to a script that should be sourced in `.bashrc`.
For example:

```
export SSSD_TEST_SUITE_BASHRC="/shared/workspace/my-scripts/vagrant-bashrc.sh"
```

## Non-default configuration files

You can set path to a non-default configuration file with `SSSD_TEST_SUITE_CONFIG`.
For example:

```
export SSSD_TEST_SUITE_CONFIG="$MY_WORKSPACE/my-config.json"
```
