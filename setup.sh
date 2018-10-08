#!/bin/bash

success_or_die() {
    if [ $1 -ne 0 ]; then
        echo $2
        exit 1
    fi
}

echo "1. Preparing host..."
./provision.sh ./provision/prepare-host.yml localhost $@
success_or_die $? "Unable to provision host machine!"

# It is better to bring machines up one by one to avoid timeout issues
echo "2. Bringing up guests one by one..."
./up.sh
success_or_die $? "Unable to bring up guests!"

echo "3. Provisioning guests..."
./provision.sh ./provision/prepare-guests.yml all $@
success_or_die $? "Unable to provision guests!"

echo "Guest machines are ready."
echo "Use 'vagrant ssh client' to ssh into client machine."

exit 0
