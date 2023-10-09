import yaml
import json
import paramiko
import time
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
    command = "grep -Po '(?<=net[0-9]: e1000=)([[:xdigit:]]{1,2}:){5}[[:xdigit:]]{1,2}'" \
              f" /etc/pve/qemu-server/{vm['vm_id']}.conf"
    stdin, stdout, stderr = ssh_client.exec_command(command)
    mac_address = stdout.read().decode().strip()

    while True:
        count = 0
        curl_command = "curl -k -u ansible:ansible" \
            f" http://10.162.253.1/rest/ip/dhcp-server/lease?mac-address={mac_address}"
        output = subprocess.check_output(curl_command, shell=True).decode().strip()
        response = json.loads(output)
        ip_address = ""
        if response:
            if "active-address" in response[0]:
                vm['ip_address'] = response[0]["active-address"]
                break

        # Wait for 5 seconds before checking again
        time.sleep(5)
        count += 1
        if count > 30:
            break
    if vm['ip_address']:
        return True
    else:
        return False


def create_vm(ssh_client, vm):
    qt_create_command = f"""
    rm -rf /tmp/{vm['vm_id']}.qcow2 
    qemu-img create -f qcow2 /tmp/{vm['vm_id']}.qcow2 {vm['storage']}
    qm create {vm['vm_id']} \
      --name {vm['name']} \
      --onboot 1 \
      --net0 e1000,bridge=vmbr0,firewall=1 \
      --cdrom vm-store:iso/metal-amd64.iso,media=cdrom \
      --sata0 vm-store:0,import-from=/tmp/{vm['vm_id']}.qcow2,format=qcow2 \
      --ostype l26 \
      --onboot yes \
      --kvm 0 \
      --cpu EPYC-v3 \
      --memory {vm['memory']} \
      --sockets {vm['cpu']} \
      --cores {vm['core']} 
    """
    stdin, stdout, stderr = ssh_client.exec_command(qt_create_command)
    output = stdout.read().decode().strip()
    return output


def delete_vm(ssh_client, vm):
    qt_create_command = f"""
        qm stop {vm['vm_id']}
        qm status {vm['vm_id']}
        qm destroy {vm['vm_id']} --destroy-unreferenced-disks true --purge true
        """
    stdin, stdout, stderr = ssh_client.exec_command(qt_create_command)
    output = stdout.read().decode().strip()
    return output


def stop_vm(ssh_client, vm):
    qt_create_command = f"""
        qm stop {vm['vm_id']}
        """
    stdin, stdout, stderr = ssh_client.exec_command(qt_create_command)
    output = stdout.read().decode().strip()
    return output


def start_vm(ssh_client, vm):
    qt_create_command = f"""
    qm start {vm['vm_id']}
    while true; do \
      VM_STATUS=$(qm status {vm['vm_id']}); \
        if [[ "$VM_STATUS" == *"running"* ]]; then \
          break; \
        else \
          sleep 10; \
        fi; \
    done
    """
    stdin, stdout, stderr = ssh_client.exec_command(qt_create_command)
    output = stdout.read().decode().strip()
    return output


def connect_pve(pve):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    private_key = paramiko.RSAKey.from_private_key_file(pve['private_key_path'])
    ssh.connect(pve['ip_address'], username=pve['username'], pkey=private_key)
    return ssh


def machine_pre_control(data, cluster, node):
    for pve in data['virtualization_servers']:
        if pve['name'] == node['server']:
            node['ssh_client'] = pve['ssh_client']
    if not cluster['configured']:
        pool_state = check_pool(node['ssh_client'], cluster)
        if cluster['state'] == 'present' and pool_state == '':
            create_pool(node['ssh_client'], cluster)
        elif cluster['state'] == 'absent':
            delete_pool(node['ssh_client'], cluster)
        cluster['configured'] = True
    node['actual_state'] = check_vm(node['ssh_client'], node)
    return

def machine_control(data, cluster, node):
    if node['actual_state'] == 'absent':
        if node['state'] == 'present':
            create_vm(node['ssh_client'], node)
            start_vm(node['ssh_client'], node)
        if node['state'] == 'stopped':
            create_vm(node['ssh_client'], node)
    if node['actual_state'] == 'stopped':
        if node['state'] == 'present':
            start_vm(node['ssh_client'], node)
        elif node['state'] == 'absent':
            delete_vm(node['ssh_client'], node)
    if node['actual_state'] == 'running':
        if node['state'] == 'absent':
            stop_vm(node['ssh_client'], node)
            delete_vm(node['ssh_client'], node)
        if node['state'] == 'stopped':
            stop_vm(node['ssh_client'], node)
    return
def machine_post_control(data, cluster, node):
    if node['state'] == 'present':
        check_vm(node['ssh_client'], node)


def cluster_managment(cluster, data):
    cluster['configured'] = False
#VM pre work
    for controlplane in cluster['controlplanes']:
        machine_pre_control(data, cluster, controlplane)
    for worker in cluster['workers']:
        machine_pre_control(data, cluster, worker)
#VM work
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
            node['actual_state'] = 'absent'
            node['state'] = state
        for node in cluster['workers']:
            state = node['state']
            node['state'] = cluster['state']
            machine_control(data, cluster, node)
            node['actual_state'] = 'absent'
            node['state'] = state
        cluster['configured'] = False
        for node in cluster['controlplanes']:
            machine_control(data, cluster, node)
        for node in cluster['workers']:
            machine_control(data, cluster, node)
    elif cluster['state'] == 'stopped':
        cluster['force'] = True
        for node in cluster['controlplanes']:
            node['state'] = cluster['state']
            machine_control(data, cluster, node)
        for node in cluster['workers']:
            node['state'] = cluster['state']
            machine_control(data, cluster, node)
    #VM work post
    if cluster['state'] == 'present' or cluster['state'] == 'recreate':
        for controlplane in cluster['controlplanes']:
            machine_post_control(data, cluster, controlplane)
        for worker in cluster['workers']:
            machine_post_control(data, cluster, worker)


for pve in data['virtualization_servers']:
    pve['ssh_client'] = connect_pve(pve)

# proxmox settings
for cluster in data['clusters']:
    cluster_managment(cluster, data)

for pve in data['virtualization_servers']:
    pve['ssh_client'].close()

#import talos
## talos config
##for cluster in data['clusters']:
#    talos.talos_managment(cluster, data)
