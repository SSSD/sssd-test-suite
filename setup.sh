#!/bin/bash

echo "1. Preparing host..."
ansible-playbook -i "localhost," -c local "./provision/prepare-host.yml"

if [ $? -ne 0 ]; then
    echo "Unable to provision host machine!"
    exit 1
fi

echo "2. Bringing up guests..."
# Windows machines sometimes timeout when starting up in parallel
# so we start them first in sequence.

vagrant up ad

if [ $? -ne 0 ]; then
    echo "Unable to bring ad up!"
    exit 1
fi

vagrant up ad-child

if [ $? -ne 0 ]; then
    echo "Unable to bring ad-child up!"
    exit 1
fi

vagrant up

if [ $? -ne 0 ]; then
    echo "Unable to bring guests up!"
    exit 1
fi

echo "3. Remove old enrollment data"
rm -fr ./shared-enrollment/ad ./shared-enrollment/ldap ./shared-enrollment/ipa

if [ $? -ne 0 ]; then
    echo "Unable to remove old enrollment data!"
    exit 1
fi

echo "4. Provisioning guests..."
./provision.sh

if [ $? -ne 0 ]; then
    echo "Unable to provision guests!"
    exit 1
fi

echo "Guest machines are ready."
echo "Use 'vagrant ssh client' to ssh into client machine."

exit 0