#!/bin/bash
#
# This will install cli dependencies on the computer.
# You can run it with -y parameter to install packages without confirmation.
#

read -r -d '' packages <<- EOM
    python3-argcomplete
    python3-colorama
    python3-clint
    python3-pyyaml
    python3-requests
    python3-requests-toolbelt
EOM

deps=""
for package in $packages; do
    deps+="$package "
done

sudo dnf install $@ $deps
    