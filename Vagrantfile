require './utils.rb'

# Default boxes
box_linux = "fedora/28-cloud-base"
box_ad    = "peru/windows-server-2016-standard-x64-eval"

# Overwrite default boxes if requested
box_linux = GetBoxName(box_linux, "SSSD_TEST_SUITE_LINUX_BOX", ".linux_box")
box_ad =    GetBoxName(box_ad, "SSSD_TEST_SUITE_WINDOWS_BOX", ".windows_box")

puts "Using Linux box:   #{box_linux}"
puts "Using Windows box: #{box_ad}"
puts ""

# Create SSSD environment
Vagrant.configure("2") do |config|
  LinuxGuest(  box_linux, config, "ipa",      "master.ipa.vm",    "192.168.100.10",  1792)
  LinuxGuest(  box_linux, config, "ldap",     "master.ldap.vm",   "192.168.100.20",  512)
  LinuxGuest(  box_linux, config, "client",   "master.client.vm", "192.168.100.30",  1024)
  WindowsGuest(box_ad,    config, "ad",       "root",             "192.168.100.110", 1024)
  WindowsGuest(box_ad,    config, "ad-child", "child",            "192.168.100.120", 1024)
end
