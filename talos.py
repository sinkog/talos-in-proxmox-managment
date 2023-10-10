import subprocess
import os



def talos_nc_check(client_ip):
    while True:
        try:
            nc_process = subprocess.Popen(['nc', client_ip, "50000"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, sterr=subprocess.PIPE)
            nc_process.stdin.write(b"exit\n")
            nc_process.stdin.flush()
            nc_process.communicate()
            if nc_process.returncode == 0:
                break
        except Exception as e:
            pass

def main(data):
    base_dir = os.getcwd()
    for cluster in data['clusters']:
        print('hihi')

    cluster_config_dir=f'''{base_dir}/{cluster['name']}'''
    if os.path.exists(f'{cluster_config_dir}'):
        os.chdir(f'{cluster_config_dir}')
    os.mkdir(f'{cluster_config_dir}')


import subprocess
import tempfile
import os
import urllib.request
import hashlib

TALOS_VERSION = "1.0.4"
KUBECTL_VERSION = "1.24.0"
CONTROL_PLANE_IP = "10.10.110.10"

# Talos telepítése
with tempfile.TemporaryDirectory() as tempdir:
    os.chdir(tempdir)

    talosctl_url = f"https://github.com/siderolabs/talos/releases/download/v{TALOS_VERSION}/talosctl-linux-amd64"
    urllib.request.urlretrieve(talosctl_url, "talosctl")
    subprocess.run(["sudo", "install", "-o", "root", "-g", "root", "-m", "0755", "talosctl", "/usr/local/bin/talosctl"])

# kubectl telepítése
with tempfile.TemporaryDirectory() as tempdir:
    os.chdir(tempdir)

    kubectl_url = f"https://dl.k8s.io/release/v{KUBECTL_VERSION}/bin/linux/amd64/kubectl"
    kubectl_sha256_url = f"https://dl.k8s.io/v{KUBECTL_VERSION}/bin/linux/amd64/kubectl.sha256"

    urllib.request.urlretrieve(kubectl_url, "kubectl")
    urllib.request.urlretrieve(kubectl_sha256_url, "kubectl.sha256")

    # Ellenőrizzük a letöltött fájl SHA-256 összegét
    expected_hash = "94d686bb6772f6fb59e3a32beff908ab406b79acdfb2427abdc4ac3ce1bb98d7"
    with open("kubectl.sha256", "r") as sha_file:
        actual_hash = hashlib.sha256(open("kubectl", "rb").read()).hexdigest()
        if actual_hash != expected_hash:
            raise Exception("A letöltött fájl SHA-256 összege nem megfelelő")

    subprocess.run(["sudo", "install", "-o", "root", "-g", "root", "-m", "0755", "kubectl", "/usr/local/bin/kubectl"])

# Egyéb műveletek ...

# Talos konfiguráció alkalmazása
TALOS = [
    "10.10.110.11,_out/controlplane.yaml",
    "10.10.110.12,_out/controlplane.yaml",
    "10.10.110.13,_out/controlplane.yaml",
    "10.10.110.21,_out/worker.yaml",
    "10.10.110.22,_out/worker.yaml",
    "10.10.110.23,_out/worker.yaml",
]

for word in TALOS:
    MYARRAY = word.split(',')
    while True:
        try:
            nc_process = subprocess.Popen(["nc", MYARRAY[0], "50000"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)
            nc_process.stdin.write(b"exit\n")
            nc_process.stdin.flush()
            nc_process.communicate()
            if nc_process.returncode == 0:
                break
        except Exception as e:
            pass

    subprocess.run(
        [
            "talosctl",
            "apply-config",
            "--insecure",
            "--nodes",
            MYARRAY[0],
            "--file",
            f"{WORKDIR}/{MYARRAY[1]}",
        ]
    )

# Egyéb műveletek ...

# Példa: Talos bootstrap
while True:
    try:
        nc_process = subprocess.Popen(["nc", CONTROL_PLANE_IP, "50000"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        nc_process.stdin.write(b"exit\n")
        nc_process.stdin.flush()
        nc_process.communicate()
        if nc_process.returncode == 0:
            break
    except Exception as e:
        pass

subprocess.run(["talosctl", "config", "endpoint", CONTROL_PLANE_IP])
subprocess.run(["talosctl", "config", "node", CONTROL_PLANE_IP])

while True:
    try:
        nc_process = subprocess.Popen(["nc", CONTROL_PLANE_IP, "50000"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        nc_process.stdin.write(b"exit\n")
        nc_process.stdin.flush()
        nc_process.communicate()
        if nc_process.returncode == 0:
            break
    except Exception as e:
        pass

subprocess.run(["talosctl", "--talosconfig", f"{WORKDIR}/_out/talosconfig", "bootstrap"])

# Példa: kubeconfig beállítása
CONTROL_PLANE_IP = "10.10.110.11"
while True:
    try:
        nc_process = subprocess.Popen(["nc", CONTROL_PLANE_IP, "50000"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        nc_process.stdin.write(b"exit\n")
        nc_process.stdin.flush()
        nc_process.communicate()
        if nc_process.returncode == 0:
            break
    except Exception as e:
        pass

subprocess.run(["talosctl", "config", "endpoint", CONTROL_PLANE_IP])
subprocess.run(["talosctl", "--talosconfig", f"{WORKDIR}/_out/talosconfig", "kubeconfig", WORKDIR])
subprocess.run(["cp", f"{WORKDIR}/kubeconfig", "~/.kube/config"])

while True:
    try:
        talosctl_process = subprocess.Popen(
            ["talosctl", "health", "--talosconfig", f"{WORKDIR}/_out/talosconfig", "--wait-timeout", "10s"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        talosctl_process.communicate()
        if talosctl_process.returncode == 0:
            break
    except Exception as e:
        pass
