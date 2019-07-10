# Configuration file

The guest machines are defined by a configuration file. The default configuration
file location is `./config.json` in the `sssd-test-suite` source directory. The
location can be changed when running the cli with `-c` parameter
(e.g. `./sssd-test-suite -c path-to-config-json up`) or with an environment
variable `SSSD_TEST_SUITE_CONFIG`. Please, be sure to use the same configuration
file for all operations until you destroy the guest machines.

## Format

```
{
  "boxes": {
    "$guest-name": {
      "name": "$box-name",
      "url": "$url-to-metadata",
      "memory": $memory
    },
    ...
  },
  "folders": {
    "sshfs": [
      {"host": "$host-path", "guest": "$guest-path"},
      ...
    ],
    "rsync": [
      {"host": "$host-path", "guest": "$guest-path"},
      ...
    ],
    "nfs": [
      {"host": "$host-path", "guest": "$guest-path"},
      ...
    ]
  }
}
```

### Box options:
* `$guest-name` is one of `ad`, `ad-child`, `ipa`, `ldap`, `client`
* `$box-name` is the name of vagrant box
  * it may be name of the box in vagrant cloud
  * it may be name of a remote box that is accessible via http,
    in this case the field url must point to the box's metadata
  * it may be name of a local box
* `$url-to-metadata` points to a box metadata file, it is required only for
  remote box that is in other location then vagrant cloud
* `$memory` is amount of operating memory that the box should use

### Shared folders

You can specify shared folders in the configuration file by providing the
dictionary of host and guests paths. You can shared the folders with `sshfs`
(recommended), `rsync` or `nfs`.

## Examples

Example configuration files can be found at `./configs` directory.
