#!/bin/bash

if [[ $# -ne 3 ||  "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Create vagrant boxes of SSSD Test Suite machines"
    echo "./create_boxes.sh BOX-NAME URL LIBVIRT-POOL"
    echo "  BOX-NAME     Name of the resulting boxes."
    echo "  URL          URL where the resulting image will be stored."
    echo "  LIBVIRT-POOL Path to libvirt directory where disk images are stored."
    echo ""
    echo "Example:"
    echo "  ./create_boxes.sh /home/qemu fedora28"
    exit 1
fi

LINUX_GUESTS="ipa ldap client"
GUESTS="ad ad-child $LINUX_GUESTS"

NAME=$1
URL=$2
POOL=$3

BOX_LOCATION="./boxes/$NAME"
METADATA="$BOX_LOCATION/metadata.json"
VERSION=`date +%Y%m%d`.01

success_or_die() {
    if [ $1 -ne 0 ]; then
        echo $2
        exit 1
    fi
}

echo "1. Halt all guests"
vagrant halt
success_or_die $? "Unable halt all guests!"

# We need to zero out empty space for the boxes to be smaller. It is better
# to make it one by one due to performance reasons as it does a lot of
# disk operations.
echo "2. Zero out empty space"
for GUEST in $LINUX_GUESTS; do
    SSSD_TEST_SUITE_BOX="yes" vagrant up $GUEST
    success_or_die $? "Unable to bring up guest: $GUEST!"
    
    ./provision.sh provision/prepare-box.yml $GUEST
    success_or_die $? "Unable to prepare box: $GUEST!"
    
    vagrant halt $GUEST
    success_or_die $? "Unable to halt guest: $GUEST!"
done

echo "3. Make images smaller"
for GUEST in $LINUX_GUESTS; do
    IMG="$POOL/sssd-test-suite_$GUEST.img"
    OLD="$POOL/sssd-test-suite_$GUEST.img.bak"

    sudo mv $IMG $OLD
    sudo qemu-img convert -O qcow2 $OLD $IMG
    success_or_die $? "Unable to convert image: $OLD!"
    
    sudo rm -f $OLD
done

echo "4. Create boxes"
sudo chmod a+r $POOL/sssd-test-suite_*.img
for GUEST in $GUESTS; do
    mkdir -p $BOX_LOCATION &> /dev/null
    vagrant package $GUEST --output="sssd-$NAME-$GUEST-$VERSION.box"
    success_or_die $? "Unable to create box: $GUEST!"
    mv sssd-$NAME-$GUEST-$VERSION.box $BOX_LOCATION/sssd-$NAME-$GUEST-$VERSION.box
done

echo "5. Create metadata"
rm -f $METADATA
for GUEST in $GUESTS; do
    CHECKSUM=`sha256sum -b "$BOX_LOCATION/sssd-$NAME-$GUEST-$VERSION.box" | cut -d ' ' -f1`
    cat >> $METADATA <<EOF
{
    "name": "sssd-$NAME-$GUEST",
    "description": "SSSD Test Suite '$NAME' $GUEST",
    "versions": [
        {
            "version": "$VERSION",
            "status": "active",
            "providers": [
                {
                    "name": "libvirt",
                    "url": "$URL/$NAME/sssd-$NAME-$GUEST-$VERSION.box",
                    "checksum_type": "sha256",
                    "checksum": "$CHECKSUM"
                }
            ]
        }
    ]
},
EOF
done

sed -i '$ s/,$/\n/' $METADATA

exit 0
