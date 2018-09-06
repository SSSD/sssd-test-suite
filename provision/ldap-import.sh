#!/bin/bash

LDAP_URI="ldap://192.168.100.20"
BASE_DN="dc=ldap,dc=vm"
BIND_DN="cn=Directory Manager"
BIND_PW="123456789"

FILE=`basename "$0"`
if [ $# -ne 1 ]; then
  echo "Import LDIF into sssd-test-suite LDAP instance."
  echo "Note: All existing object will be deleted."
  echo ""
  echo "Usage:"
  echo "  $FILE PATH-TO-LDIF"
fi

LDIF=$1

echo "Importing LDIF: $LDIF"
ldapadd -x -D "$BIND_DN" -w "$BIND_PW" -H "$LDAP_URI" -f $LDIF
