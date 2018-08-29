# Read box name from environment variable or if not specified,
# try to read it from a file. Otherwise default is used.
def GetBoxName(default, env_var, file)
  box_name = default
  if ENV.has_key?(env_var)
    box_name = ENV[env_var]
    open(file, 'w') do |f|
      f.puts box_name
    end
  elsif File.exist?(file)
    box_name = File.read(file)
  end

  return box_name
end

# Read environment variable to obtain list of synchronized folders.
# The format is: "hostpath:guestpath hostpath:guestpath ..."
def GetSyncFolders(env_var)
  folders = {}

  if ENV.has_key?(env_var)
    ENV[env_var].split(" ").each do |mount|
       host, guest = mount.split(":")
       folders[host] = guest
    end
  end

  return folders
end

# Create a generic guest machine
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

    sync_sshfs = GetSyncFolders('SSSD_TEST_SUITE_SSHFS')
    sync_rsync = GetSyncFolders('SSSD_TEST_SUITE_RSYNC')
    sync_nfs =   GetSyncFolders('SSSD_TEST_SUITE_NFS')

    sync_sshfs.merge!("./shared-data" => "/shared/data")
    sync_sshfs.merge!("./shared-enrollment" => "/shared/enrollment")

    sync_sshfs.each do |host, guest|
      this.vm.synced_folder "#{host}", "#{guest}", type: "sshfs", sshfs_opts_append: "-o cache=no"
    end

    sync_nfs.each do |host, guest|
      this.vm.synced_folder "#{host}", "#{guest}", type: "nfs", nfs_udp: false
    end

    sync_rsync.each do |host, guest|
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
