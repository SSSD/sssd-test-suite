require_relative './ruby/config.rb'
require_relative './ruby/machine.rb'
require_relative './ruby/guest.rb'

# Get configuration
project_dir = File.expand_path(File.dirname(__FILE__))
config_file = sprintf("%s/config.json", project_dir)
if ENV.has_key?("SSSD_TEST_SUITE_CONFIG")
  config_file = ENV["SSSD_TEST_SUITE_CONFIG"]
end

config = Config.new(config_file)

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

# Print information about environment
if ARGV[0] == "status"
  puts ""
  puts "Current configuration:"
  puts ""
  printf("  %-10s (%-15s, %-20s, %-7s) - %s\n",
         "NAME", "IP ADDRESS", "HOSTNAME", "MEMORY", "BOX NAME")
  machines.each do |m|
    hostname = m.hostname
    case hostname
    when "root-dc"
      hostname = "#{m.hostname}.ad.vm"
    when "child-dc"
      hostname = "#{m.hostname}.child.ad.vm"
    end
    
    box = m.box
    if box.nil? or box.empty?
      box = "(disabled)"
    end
    
    printf("  %-10s (%-15s, %-20s, %-4d MB) - %s\n",
           m.name, m.ip, hostname, m.memory, box)
  end
  puts ""
end

# Create SSSD environment
Vagrant.configure("2") do |vagrant_config|
  machines.each do |machine|
    Guest.Add(config, vagrant_config, machine)
  end
end
