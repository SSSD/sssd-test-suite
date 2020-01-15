# Issues we met

This document collects issues that we had with sssd-test-suite and their
solution.

## AD machine sudden shutdown
Probably license expired. Run

    ./sssd-test-suite up -s ad ad-child && ./sssd-test-suite provision rearm


## TASK [host : Install required vagrant plugins] failed due to vagrant dependencies

This can happens when there is mix of vagrant plugins installed through gems
distribution with plugins packaged with rpm. Remove the rpm packages
and rerun host provisioning.


## Various errors on older Fedora
sssd-test-suite is under active development and it needs new ansibles,
Please check for ansible upgrade.


## ./sssd-test-suite rdp ad -- -g 90% ends immediatelly without any error message 

This documentation presumes that rdesktop client is installed and used. However
vagrant detects installed RDP client and it tries to use it.

It might be the case that you have another RDP client installed and suggested
command line options are not accepted by it. Solution is to use proper options
for your RDP client. For example if you use xfreerdp, the command should be

    ./sssd-test-suite rdp ad -- /cert-ignore /size:90%
