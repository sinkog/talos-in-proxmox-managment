import yaml
import json
import paramiko
import time
import re
import subprocess

# Load the contents of the settings.yaml file
with open('settings.yaml', 'r') as file:
    data = yaml.safe_load(file)

def check_pool(ssh_client, cluster):
    vm_command = f"pvesh ls /pools|grep {cluster['name']}"
    stdin, stdout, stderr = ssh_client.exec_command(vm_command)
    output = stdout.read().decode().strip()
    return output
def create_pool(ssh_client, cluster):
    vm_command = f"pvesh create /pools --poolid '{cluster['name']}' --comment 'managed by ansible'"
    stdin, stdout, stderr = ssh_client.exec_command(vm_command)
    output = stdout.read().decode().strip()
    return output
def delete_pool(ssh_client, cluster):
    vm_command = f"pvesh delete /pools/{cluster['name']}"
    stdin, stdout, stderr = ssh_client.exec_command(vm_command)
    output = stdout.read().decode().strip()
    return output
def check_vm(ssh_client, vm):
    vm_command = f"qm status {vm['vm_id']}"
    stdin, stdout, stderr = ssh_client.exec_command(vm_command)
    output = stdout.read().decode().strip()
    if "status: running" in output:
        check_vm_ip(ssh_client, vm)
        return "running"
    elif "status: stopped" in output:
        return "stopped"
    else:
        return 'absent'

def check_vm_ip(ssh_client, vm):
    command = f"grep -Po '(?<=net[0-9]: e1000=)([[:xdigit:]]\\{1,2\\}:)\\{5\\}[[:xdigit:]]\\{1,2\\}' /etc/pve/qemu-server/{vm['vm_id']}.conf"
    stdin, stdout, stderr = ssh_client.exec_command(command)
    mac_address = stdout.read().decode().strip()
    
    while True:
        count = 0
        curl_command = f"curl -k -u ansible:ansible http://10.10.10.1/rest/dhcp-server/lease?mac-address={mac_address}"
        output = subprocess.check_output(curl_command, shell=True).decode().strip()
        response = json.loads(output)
        ip_address = ""
        if "active-address" in response:
            vm['ip_address'] = response["acrive-address"]
            break

        # Wait for 5 seconds before checking again
        time.sleep(5)
        count += 1
        if count > 30:
            break
    if vm['ip_address']:
        return True
    else
        return False

# Use curl to query the MikroTik router's REST API for the IP address
    curl_command = f"curl -k -u ansible:ansible http://10.10.10.1/rest/dhcp-server/lease?mac-address={mac_address}"
    result = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
    output = result.stdout.strip()

    # Parse the output to extract the IP address
    ip_address = ""
    if "active-address" in output:
        ip_address = output.split("active-address")[1].split(":")[1].strip().strip('"')

    # Update the IP address in the controlplane object
    controlplane['ip_address'] = ip_address
    return True

def create_vm(ssh_client, vm):
    qt_create_command = f"""
    mkdir -p /var/lib/vz2/images/{vm['vm_id']}
    qemu-img create - qcow2 /var/lib/vz2/images/{vm['vm_id']}/{vm['vm_id']}.qcow2 {vm['storage']}
    qm create {vm['vm_id']} \
      --name {vm['name']} \
      --onboot 1 \
      --net0 e1000,bridge=vmbr0,firewall=1 \
      --cdrom vm-store:iso/metal-amd64.iso,media=cdrom \
      --sata0 vm-store:/var/lib/vz2/images/{vm['vm_id']}/{vm['vm_id']}.qcow2 \
      --ostype l26 \
      --onboot yes \
      --start true \
      --memory {vm['memory']} \
      --socket {vm['cpu']} \
      --cores {vm['core']} &&
    while true; do \
     VM_STATUS=\$(pvesh get /nodes/$VM_NODE/qemu/{vm['vm_id']}/status/current); \
       if [ "\$VM_STATUS" = "running" ]; then \
         break; \
         else \
           sleep 10; \
         fi; \
     done
    """

    stdin, stdout, stderr = ssh_client.exec_command(qt_create_command)
    output = stdout.read().decode().strip()
    return output

def delete_vm(ssh_client, vm):
    qt_create_command = f"""
        qt stop {vm['vm_id']}
        qm status {vm['vm_id']}
        qt destroy {vm['vm_id']} --destroy-unreferenced-disks true --purge true
        """
    stdin, stdout, stderr = ssh_client.exec_command(qt_create_command)
    output = stdout.read().decode().strip()
    return output

def recreate_vm(ssh_client, vm):
    vm_command = "..."pvesh create /nodes/$VM_NODE/qemu -vmid $VM_ID -name 'MyVMName' -ostype l26 -sockets 2 -cores 2 -memory 2048 -start 1 && \
   while true; do \
     VM_STATUS=\$(pvesh get /nodes/$VM_NODE/qemu/$VM_ID/status/current); \
     if [ \"\$VM_STATUS\" = \"running\" ]; then \
       echo 'A virtuális gép fut.'; \
       break; \
     else \
       echo 'A virtuális gép még nem fut. Várakozás...'; \
       sleep 10; \
     fi; \
   done""
    stdin, stdout, stderr = ssh_client.exec_command(vm_command)
    output = stdout.read().decode().strip()
    return output

def connect_pve(pve):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    private_key= paramiko.RSAKey.from_private_key_file(pve['private_key_path'])
    ssh.connect(pve['ip_address'], pve['username'], pkey= private_key)
    return ssh

def machine_control(data, cluster, node):
    for pve in data['virtualization_servers']:
        if pve['name'] == node['name']:
            node['ssh_client']= pve['ssh_client']
    if not cluster['configured']:
        pool_state = check_pool(node.ssh_client, cluster)
        if cluster['state'] == 'present' and pool_state == '':
            create_pool(node.ssh_client, cluster)
        elif cluster['state'] == 'absent':
            delete_pool(node.ssh, cluster)
        cluster['configured'] = True
    node_state = check_vm(node['ssh_client'], node)
    if node_state == '':
        if node['state'] == 'present':
            create_vm(node['ssh_client'], node)
    else:
        if node['state'] == 'recreate':
            delete_vm(node['ssh_client'], node)
        elif node['state'] == 'absent':
            delete_vm(node['ssh_client'], node)

def cluster_managment(cluster, data):
    if cluster['state'] == 'present':
        for controlplane in cluster['controlplanes']:
            machine_control(data, cluster, controlplane)
        for worker in cluster['workers']:
            machine_control(data, cluster, worker)
    elif cluster['state'] == 'absent':
        cluster['force'] = True
        for node in cluster['controlplanes']:
            node['state'] = cluster['state']
            machine_control(data, cluster, node)
        for node in cluster['workers']:
            node['state'] = cluster['state']
            machine_control(data, cluster, node)
    elif cluster['state'] == 'recreate':
        cluster['force'] = True
        for node in cluster['controlplanes']:
            state = node['state']
            node['state'] = 'absent'
            machine_control(data, cluster, node)
            node['state'] = state
        for node in cluster['workers']:
            state = node['state']
            node['state'] = cluster['state']
            machine_control(data, cluster, node)
            node['state'] = state
        cluster['configured'] = False
        for node in cluster['controlplanes']:
            machine_control(data, cluster, node)
        for node in cluster['workers']:
            machine_control(data, cluster, node)
    


for pve in data['virtualization_servers']:
    pve['ssh_client'] = connect_pve(pve)

# proxmox settings
for cluster in data['clusters']:
    cluster_managment(cluster, data)



for pve in data['virtualization_servers']:
    pve['ssh_client'].close()


