# Running Tests

You can run all available SSSD tests with the following command:

```bash
$ ./sssd-test-suite run --sssd $path-to-sssd-source --artifacts $path-to-artifacts-directory
```

The artifacts directory will be created if it does not exist and tests artifacts
and logs will be stored there when the testing is finished.

The command will read `test-suite-yml` file from
`$path-to-sssd-source/contrib/test-suite/test-suite.yml`. This file contains
description of the tests that will be run. You can also specify different file
with `--test-config` option.

## test-suite.yml format

```yml
- name: Test Case Name
  machines:
  - list of machines to start
  tasks:
  - list of tasks
  artifacts: (optional)
  - list of artifacts
  timeout: timeout value (optional)
```

### machines: list of machines to start

Record `machines` contains list of `sssd-test-suite` guests to start. It is
a subset of [`ad`, `ad-child`, `ipa`, `ldap`, `client`]. For example:

```yaml
- machines:
  - client
  - ipa
  - ad
```

### tasks: list of tasks

This record defines tasks that should be executed on the guest machines. It is
a list of the following dictionary:

```yaml
- name: Task Name (optional, default to empty name)
  run-on: guest (optional, defaults to client or machines[0])
  directory: working directory (optional, default to /shared/sssd)
  shell: script-to-run
  artifacts: (optional)
  - list of artifacts
  timeout: timeout value (optional)
```

* `name`: name of the task
* `run-on`: name of the guest on which the shell script should be executed
* `directory`: working directory for the script
  * each guest has two shared directories:
    * `/shared/sssd`: SSSD source code (changes are not synchronized with host folder)
    * `/shared/artifacts`: Directory where test artifacts are stored (changes are synchronized)
* `shell`: a shell script to run, it can be a one liner or a multiline script:
```yml
shell: one-liner

shell: |
  multi
  line
  script

```
* `artifacts`: artifacts to automatically fetch after the task finished, see bellow
* `timeout`: maximum execution time of the task, see bellow

### artifacts: list of artifacts

This may be list of files or a dictionaries specifying list of files and guest
from which they are taken. For example:

```yml
  artifacts:
  - ci-*.log
  - ci-build-debug/ci-*.log
  - ci-build-debug/test-suite.log
  
  artifacts:
  - from: client
    files:
    - ci-*.log
    - ci-build-debug/ci-*.log
    - ci-build-debug/test-suite.log

  artifacts:
  - from: client
    files:
    - ci-*.log
    - ci-build-debug/ci-*.log
    - ci-build-debug/test-suite.log
  - from: ipa
    files:
    - /var/log/httpd/errors.log
  - /var/log/sssd/*.log
```

If the artifact is only a file without guest specification, the default guest
is used. The default guest is `client` or the first guest in `machines` record.
If the artifacts are fetched after a test task, the default guest is the guest
that the task was run on.

### timeout: timeout value

Maximum execution time of the task or the whole testcase.

```yml
  # Syntax
  timeout: [N hour(s)] [N minute(s)] [N second(s)]

  # 60 seconds
  timeout: 60

  # Other possible values
  timeout: 6 hours
  timeout: 1.5 hour
  timeout: 3 hours 30 minutes
  timeout: 1 hour 30 minutes 15 seconds
```

### Example

```yaml
- name: Integration Tests
  machines:
  - client
  tasks:
  - name: Running ./contrib/ci/run
    shell: ./contrib/ci/run --moderate --no-deps
  artifacts:
  - ci-*.log
  - ci-build-debug/ci-*.log
  - ci-build-debug/test-suite.log
  timeout: 6 hours
```

