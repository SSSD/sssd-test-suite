#!/bin/bash

# Install packages directly through dnf than Ansible since
# it seems to be faster and it can be run in parallel.

HOST=${1-"UNKNOWN"}

echo "Installing packages on host $HOST"

echo "Updating installed packages"
dnf upgrade -y > /dev/null

# Install packages required for Ansible operation and other common packages
echo "Installing common packages"
dnf install -y              \
    bash-completion         \
    dnsmasq                 \
    gdb                     \
    git                     \
    ldb-tools               \
    libselinux-python       \
    NetworkManager          \
    openldap-clients        \
    python                  \
    python-dnf              \
    python-ldap             \
    tig                     \
    vim                     \
    wget                    \
  > /dev/null

echo "Installing host specific packages"

if [ $HOST == "ipa" ]; then
    dnf install -y                  \
        freeipa-server              \
        freeipa-server-dns          \
        freeipa-server-trust-ad     \
      > /dev/null
fi

if [ $HOST == "ldap" ]; then
    dnf install -y                  \
        389-ds-base                 \
      > /dev/null
fi

if [ $HOST == "client" ]; then
    dnf install -y                  \
        adcli                       \
        augeas-devel                \
        autoconf                    \
        automake                    \
        bind-utils                  \
        c-ares-devel                \
        check                       \
        check-devel                 \
        cifs-utils-devel            \
        dbus-devel                  \
        dbus-libs                   \
        diffstat                    \
        docbook-style-xsl           \
        doxygen                     \
        freeipa-client              \
        gettext                     \
        gettext-devel               \
        glib2-devel                 \
        http-parser-devel           \
        jansson-devel               \
        keyutils-libs-devel         \
        krb5-devel                  \
        libcmocka                   \
        libcmocka-devel             \
        libcollection-devel         \
        libcurl-devel               \
        libdhash-devel              \
        libini_config-devel         \
        libldb                      \
        libldb-devel                \
        libnfsidmap-devel           \
        libnl3-devel                \
        libpath_utils-devel         \
        libref_array-devel          \
        libselinux-devel            \
        libsemanage-devel           \
        libsmbclient-devel          \
        libtalloc                   \
        libtalloc-devel             \
        libtdb                      \
        libtdb-devel                \
        libtevent                   \
        libtevent-devel             \
        libtool                     \
        libuuid-devel               \
        libxml2                     \
        libxslt                     \
        m4                          \
        nspr-devel                  \
        nss-devel                   \
        nss-util-devel              \
        nss_wrapper                 \
        oddjob                      \
        oddjob-mkhomedir            \
        openldap-devel              \
        pam-devel                   \
        pam_wrapper                 \
        pcre-devel                  \
        pkgconfig                   \
        po4a                        \
        popt-devel                  \
        python-devel                \
        python3-devel               \
        realmd                      \
        resolv_wrapper              \
        samba-common-tools          \
        samba-devel                 \
        samba4-devel                \
        selinux-policy-targeted     \
        socket_wrapper              \
        sssd                        \
        sssd-*                      \
        systemd-devel               \
        systemtap-sdt-devel         \
        uid_wrapper                 \
      > /dev/null
        
    dnf debuginfo-install -y        \
        dbus-devel                  \
        libcmocka                   \
        libcollection-devel         \
        libdhash                    \
        libini_config               \
        libldb                      \
        libtalloc                   \
        libtevent                   \
      > /dev/null
fi
