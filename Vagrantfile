require_relative './ruby/config.rb'
require_relative './ruby/machine.rb'
require_relative './ruby/guest.rb'

# Default boxes
box_linux = "fedora/28-cloud-base"
box_ad    = "peru/windows-server-2016-standard-x64-eval"

config = Config.new("config.json", box_linux, box_ad)

machines = [
  Machine.new(
    name: "ipa",
    type: Machine::LINUX,
    hostname: "master.ipa.vm",
    ip: "192.168.100.10",
    config: config
  ),
  Machine.new(
    name: "ldap",
    type: Machine::LINUX,
    hostname: "master.ldap.vm",
    ip: "192.168.100.20",
    config: config
  ),
  Machine.new(
    name: "client",
    type: Machine::LINUX,
    hostname: "master.client.vm",
    ip: "192.168.100.30",
    config: config
  ),
  Machine.new(
    name: "ad",
    type: Machine::WINDOWS,
    hostname: "root-dc",
    ip: "192.168.100.110",
    config: config
  ),
  Machine.new(
    name: "ad-child",
    type: Machine::WINDOWS,
    hostname: "child-dc",
    ip: "192.168.100.120",
    config: config
  )
]

# Create SSSD environment
Vagrant.configure("2") do |vagrant_config|
  machines.each do |machine|
    Guest.Add(config, vagrant_config, machine)
  end
end
