#!/bin/bash

# It is better to bring machines up one by one to avoid timeout issues
for HOST in ad ad-child ipa ldap client; do
    vagrant up $HOST
    if [ $? -ne 0 ]; then
        echo "Unable to bring up host: $HOST!"
        exit 1
    fi
done

exit 0
