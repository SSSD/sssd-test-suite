BOX_LINUX = "fedora/27-cloud-base"
BOX_AD    = "peru/windows-server-2016-standard-x64-eval"

def Guest(guest, box, hostname, ip, memory)
  guest.vm.box = box
  guest.vm.hostname = hostname
  guest.vm.network "private_network", ip: ip

  guest.vm.provider :libvirt do |libvirt|
    libvirt.memory = memory
  end
end

# Create a Linux guest.
# Hostname should be fully qualified domain name.
def LinuxGuest(box, config, name, hostname, ip, memory)
  config.vm.define name do |this|
    Guest(this, box, hostname, ip, memory)

    this.vm.synced_folder ".", "/vagrant", disabled: true

    rsync = {}
    sync = {
      "./shared-data" => "/shared/data",
      "./shared-enrollment" => "/shared/enrollment"
    }

    # "hostpath:guestpath hostpath:guestpath ..."
    if ENV.has_key?('SSSD_TEST_SUITE_MOUNT')
      ENV['SSSD_TEST_SUITE_MOUNT'].split(" ").each do |mount|
         host, guest = mount.split(":")
         sync[host] = guest
      end
    end

    sync.each do |host, guest|
      this.vm.synced_folder "#{host}", "#{guest}", type: "nfs", nfs_udp: false
    end

    # "hostpath:guestpath hostpath:guestpath ..."
    if ENV.has_key?('SSSD_TEST_SUITE_RSYNC')
      ENV['SSSD_TEST_SUITE_RSYNC'].split(" ").each do |mount|
         host, guest = mount.split(":")
         rsync[host] = guest
      end
    end

    rsync.each do |host, guest|
      this.vm.synced_folder "#{host}", "#{guest}", type: "rsync"
    end

    if ENV.has_key?('SSSD_TEST_SUITE_BASHRC')
      this.ssh.forward_env = ["SSSD_TEST_SUITE_BASHRC"]
    end
  end
end

# Create a windows guest.
# Hostname must be a short machine name not a fully qualified domain name.
def WindowsGuest(box, config, name, hostname, ip, memory)
  config.vm.define name do |this|
    Guest(this, box, hostname, ip, memory)

    this.vm.guest = :windows
    this.vm.communicator = "winrm"
    this.winrm.username = ".\\Administrator"
  end
end

# Currently each windows machine must be created with different box
# so it has different SID. Otherwise we fail to create a domain controller.
Vagrant.configure("2") do |config|
  LinuxGuest(  "#{BOX_LINUX}", config, "ipa",      "master.ipa.vm",    "192.168.100.10",  1792)
  LinuxGuest(  "#{BOX_LINUX}", config, "ldap",     "master.ldap.vm",   "192.168.100.20",  512)
  LinuxGuest(  "#{BOX_LINUX}", config, "client",   "master.client.vm", "192.168.100.30",  1024)
  WindowsGuest("#{BOX_AD}",    config, "ad",       "root",             "192.168.100.110", 1024)
  WindowsGuest("#{BOX_AD}",    config, "ad-child", "child",            "192.168.100.120", 1024)
end
