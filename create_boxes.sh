#!/bin/bash

if [[ $# -ne 4 ||  "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Create vagrant boxes of SSSD Test Suite machines"
    echo "./create_boxes.sh BOX-NAME URL LIBVIRT-POOL"
    echo "  LINUX-OS     Name of the resulting boxes."
    echo "  WINDOWS-OS   Name of the resulting boxes."
    echo "  URL          URL where the resulting image will be stored."
    echo "  LIBVIRT-POOL Path to libvirt directory where disk images are stored."
    echo ""
    echo "Example:"
    echo "  ./create_boxes.sh /home/qemu fedora28"
    exit 1
fi

LINUX_GUESTS="ipa ldap client"
WINDOWS_GUESTS="ad ad-child"
GUESTS="$WINDOWS_GUESTS $LINUX_GUESTS"

LINUX=$1
WINDOWS=$2
URL=$3
POOL=$4

BOX_LOCATION="./boxes"
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

for name in $LINUX $WINDOWS; do
    if [ $name == $LINUX ]; then
        guests=$LINUX_GUESTS
        vagrantfile="$BOX_LOCATION/vagrant-files/linux.vagrantfile"
    else
        guests=$WINDOWS_GUESTS
        vagrantfile="$BOX_LOCATION/vagrant-files/windows.vagrantfile"
    fi

    for guest in $guests; do
        boxname="sssd-$name-$guest-$VERSION.box"
        vagrant package $guest                                            \
            --vagrantfile="$vagrantfile"                                  \
            --output="$boxname"
        success_or_die $? "Unable to create box: $guest!"
        mv $boxname $BOX_LOCATION/$boxname

        sum=`sha256sum -b "$BOX_LOCATION/$boxname" | cut -d ' ' -f1`
        cat >> "$BOX_LOCATION/sssd-$name-$guest-$VERSION.json" <<EOF
{
    "name": "sssd-$name-$guest",
    "description": "SSSD Test Suite '$name' $guest",
    "versions": [
        {
            "version": "$VERSION",
            "status": "active",
            "providers": [
                {
                    "name": "libvirt",
                    "url": "$URL/sssd-$name-$guest-$VERSION.box",
                    "checksum_type": "sha256",
                    "checksum": "$sum"
                }
            ]
        }
    ]
}
EOF
    done
done

exit 0
