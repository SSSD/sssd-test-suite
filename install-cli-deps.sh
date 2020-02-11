#!/bin/bash
#
# This will install cli dependencies on the computer.
# You can run it with -y parameter to install packages without confirmation.
#

# Detect Fedora version
version=$(cat /etc/os-release | grep "VERSION_ID" | cut -d"=" -f2)
echo "Fedora version detected: $version"

# General required packages
packages+=("python3-argcomplete")
packages+=("python3-colorama")
packages+=("python3-clint")
packages+=("python3-pyyaml")
packages+=("python3-requests")
packages+=("python3-requests-toolbelt")
packages+=("ansible")

echo "Packages to be installed: ${packages[@]}"

sudo dnf install $@ "${packages[@]}"

