#!/bin/bash

success_or_die() {
    if [ $1 -ne 0 ]; then
        echo $2
        exit 1
    fi
}

echo "1. Preparing host..."
ansible-playbook -i "localhost," -c local "./provision/prepare-host.yml"
success_or_die $? "Unable to provision host machine!"

# It is better to bring machines up one by one to avoid timeout issues
echo "2. Bringing up guests one by one..."
for HOST in ad ad-child ipa ldap client; do
    vagrant up $HOST
    success_or_die $? "Unable to bring up host: $HOST!"
done

echo "3. Provisioning guests..."
./provision.sh
success_or_die $? "Unable to provision guests!"

echo "Guest machines are ready."
echo "Use 'vagrant ssh client' to ssh into client machine."

exit 0
