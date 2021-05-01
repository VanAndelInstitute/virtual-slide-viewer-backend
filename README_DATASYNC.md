Each AWS account will need its own DataSync agent deployed to the ScanScope workstation. You can remote into a Hyper-V server via Hyper-V Manager, but you’ll need to enable CredSSP on the remote client:
- In PowerShell run `Enable-WSManCredSSP`. You may need to run `Set-WSManQuickConfig` first.

---
### [Deploy your DataSync agent on Hyper-V](https://docs.aws.amazon.com/datasync/latest/userguide/deploy-agents.html#create-hyper-v-agent)
- Download the vhdx from the AWS DataSync console
- [Set up a NAT network](https://docs.microsoft.com/en-us/virtualization/hyper-v-on-windows/user-guide/setup-nat-network) if it doesn’t already exist. Otherwise use the `Get-NetAdapter`, `Get-NetIPAddress` and `Get-NetNat` PowerShell commands to determine the network mask and default gateway address, and use the DNS addresses of the ScanScope computer.
- Create a new Virtual Machine
    - [Generation 1 VM](https://docs.aws.amazon.com/datasync/latest/userguide/agent-requirements.html#hosts-requirements)
    - 16384 MB startup memory, use dynamic memory
    - Choose the NAT network adapter created above
    - Use the vhdx downloaded from the AWS DataSync console
- Once the VM is created, change the number of virtual processors to 4 in the VM settings
- Connect to the VM, start it, and [Log in to the AWS DataSync local console](https://docs.aws.amazon.com/datasync/latest/userguide/local-console-vm.html#local-console-login)
- [Configure your agent network settings](https://docs.aws.amazon.com/datasync/latest/userguide/local-console-vm.html#network-configration)
    - Configure a static IP address
    - Edit your agent’s DNS configuration
    - Test network connectivity
- [Obtain an activation key using the local console](https://docs.aws.amazon.com/datasync/latest/userguide/local-console-vm.html#get-activation-key)
- Create an agent. Choose “Manually enter your agent’s activation key”
- Create a location of type SMB for the ScanScope workstation file location
---
You are now ready to deploy the CloudFormation stack for VSV, including the remaining DataSync resources.
