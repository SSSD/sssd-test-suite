#!/bin/bash
#
# Clear all existing objects.
#

LDAP_URI="ldap://192.168.100.20"
BASE_DN="dc=ldap,dc=vm"
BIND_DN="cn=Directory Manager"
BIND_PW="123456789"

FILTER="(&(objectClass=*)(!(cn=Directory Administrators)))"
SEARCH=`ldapsearch -x -D "$BIND_DN" -w "$BIND_PW" -H "$LDAP_URI" -b "$BASE_DN" -s one "$FILTER"`
OBJECTS=`echo "$SEARCH" | grep dn | sed "s/dn: \(.*\)/'\1'/" | paste -sd " "`

echo "$SEARCH" | grep numEntries &> /dev/null
if [ $? -ne 0 ]; then
    echo "LDAP server is already clear. Nothing to do."
    exit 0
fi

echo "Removing existing objects."
eval "ldapdelete -r -x -D '$BIND_DN' -w '$BIND_PW' -H '$LDAP_URI' $OBJECTS"
