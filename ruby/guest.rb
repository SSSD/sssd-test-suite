require_relative './config.rb'
require_relative './machine.rb'

class Guest
  def self.Add(config, vagrant_config, machine)
    vagrant_config.vm.define machine.name do |this|
      this.vm.box = machine.box
      this.vm.box_url = machine.url
      this.vm.hostname = machine.hostname
      this.vm.network "private_network", ip: machine.ip

      this.vm.provider :libvirt do |libvirt|
        libvirt.memory = machine.memory
        libvirt.storage_pool_name = "sssd-test-suite"

        # Creating new private networks requires system connection.
        if defined?(libvirt.qemu_use_session)
          libvirt.qemu_use_session = false
        end
      end

      case machine.type
      when Machine::LINUX
        SetLinux(this, config)
      when Machine::WINDOWS
        SetWindows(this, config)
      end
    end
  end

  def self.SetLinux(this, config)
    this.vm.synced_folder ".", "/vagrant", disabled: true

    config.getFolders("sshfs", "SSSD_TEST_SUITE_SSHFS").each do |host, guest|
      this.vm.synced_folder "#{host}", "#{guest}", type: "sshfs", sshfs_opts_append: "-o cache=no"
    end

    config.getFolders("nfs", "SSSD_TEST_SUITE_NFS").each do |host, guest|
      this.vm.synced_folder "#{host}", "#{guest}", type: "nfs", nfs_udp: false
    end

    config.getFolders("rsync", "SSSD_TEST_SUITE_RSYNC").each do |host, guest|
      this.vm.synced_folder "#{host}", "#{guest}", type: "rsync"
    end

    if ENV.has_key?('SSSD_TEST_SUITE_BASHRC')
      this.ssh.forward_env = ["SSSD_TEST_SUITE_BASHRC"]
    end
  end

  def self.SetWindows(this, config)
    this.vm.guest = :windows
    this.vm.communicator = "winrm"

    # Dot means that we will join into default (or empty) domain.
    this.winrm.username = ".\\Administrator"

    # Avoid timeouting issues for initial WinRM connection.
    this.winrm.retry_limit = 50
    this.winrm.retry_delay = 10
  end

  private_class_method :SetLinux, :SetWindows
end
