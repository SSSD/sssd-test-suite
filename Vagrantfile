require './ruby/config.rb'
require './ruby/machine.rb'
require './ruby/guest.rb'

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
    memory: 1792,
    config: config
  ),
  Machine.new(
    name: "ldap",
    type: Machine::LINUX,
    hostname: "master.ldap.vm",
    ip: "192.168.100.20",
    memory: 1024,
    config: config
  ),
  Machine.new(
    name: "client",
    type: Machine::LINUX,
    hostname: "master.client.vm",
    ip: "192.168.100.30",
    memory: 1536,
    config: config
  ),
  Machine.new(
    name: "ad", 
    type: Machine::WINDOWS,
    hostname: "root-dc",
    ip: "192.168.100.110",
    memory: 1024,
    config: config
  ),
  Machine.new(
    name: "ad-child",
    type: Machine::WINDOWS,
    hostname: "child-dc",
    ip: "192.168.100.120",
    memory: 1024,
    config: config
  ),  
]

# Create SSSD environment
Vagrant.configure("2") do |vagrant_config|
  machines.each do |machine|
    Guest.Add(config, vagrant_config, machine)
  end
end
