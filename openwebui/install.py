import shutil
import os
import subprocess
import getpass

# Prompt the user for the server IP address
server_ip = input("Enter the IP address of your server: ")

# Prompt the user for their sudo password
sudo_password = getpass.getpass("Enter your sudo password: ")

# Define source and destination paths
current_directory = os.getcwd()
nginx_src = os.path.join(current_directory, 'nginx')
searxng_src = os.path.join(current_directory, 'searxng')
compose_file_src = os.path.join(current_directory, 'docker-compose.yaml')
destination_directory = os.path.expanduser('~/openwebui')
nginx_dest = os.path.join(destination_directory, 'nginx')
searxng_dest = os.path.join(destination_directory, 'searxng')
ssl_directory = os.path.join(nginx_dest, 'self-signed')
crt_path = os.path.join(ssl_directory, 'self-signed.crt')
key_path = os.path.join(ssl_directory, 'self-signed.key')
nginx_conf_path = os.path.join(nginx_dest, 'nginx.conf')

# Ensure the destination directory exists
os.makedirs(destination_directory, exist_ok=True)

# Function to run commands with sudo
def run_sudo_command(command, password):
    process = subprocess.run(['sudo', '-S'] + command, input=password.encode(), check=True)
    return process

# Ensure the Docker group exists and add the current user to it
current_user = os.getlogin()
try:
    run_sudo_command(['getent', 'group', 'docker'], sudo_password)
    print("Docker group already exists.")
except subprocess.CalledProcessError:
    print("Docker group does not exist. Creating Docker group...")
    run_sudo_command(['groupadd', 'docker'], sudo_password)

try:
    run_sudo_command(['usermod', '-aG', 'docker', current_user], sudo_password)
    print(f"Added {current_user} to the docker group. You may need to log out and log back in for the changes to take effect.")
    # Apply the group change immediately for the current session
    docker_group_id = int(subprocess.run(['getent', 'group', 'docker'], capture_output=True, text=True).stdout.split(':')[2])
    os.setgroups(os.getgroups() + [docker_group_id])
except subprocess.CalledProcessError as e:
    print(f"Failed to add {current_user} to the docker group: {e}")

# Check if all files exist in the target locations
if (os.path.exists(nginx_dest) and os.path.exists(searxng_dest) and
        os.path.exists(os.path.join(destination_directory, 'docker-compose.yaml')) and
        os.path.exists(crt_path) and os.path.exists(key_path)):

    # Take down Docker containers
    try:
        subprocess.run(['docker-compose', 'down'], cwd=destination_directory, check=True)
        print("Docker containers have been taken down.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to take down Docker containers: {e}")

    # Delete Docker images (but not the volumes)
    try:
        subprocess.run(['docker-compose', 'rm', '--force'], cwd=destination_directory, check=True)
        print("Docker images have been removed.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to remove Docker images: {e}")

else:
    # Copy the directories and file
    def copy_tree(src, dst):
        if not os.path.exists(dst):
            shutil.copytree(src, dst)
        else:
            for item in os.listdir(src):
                s = os.path.join(src, item)
                d = os.path.join(dst, item)
                if os.path.isdir(s):
                    copy_tree(s, d)
                elif not os.path.exists(d):
                    shutil.copy2(s, d)

    try:
        copy_tree(nginx_src, nginx_dest)
        print(f"Copied {nginx_src} to {nginx_dest}")
    except FileNotFoundError:
        print(f"Directory not found: {nginx_src}")
    except PermissionError:
        print(f"Permission denied when copying {nginx_src}")

    try:
        copy_tree(searxng_src, searxng_dest)
        print(f"Copied {searxng_src} to {searxng_dest}")
    except FileNotFoundError:
        print(f"Directory not found: {searxng_src}")
    except PermissionError:
        print(f"Permission denied when copying {searxng_src}")

    try:
        compose_file_dest = os.path.join(destination_directory, os.path.basename(compose_file_src))
        if not os.path.exists(compose_file_dest):
            shutil.copy2(compose_file_src, destination_directory)
            print(f"Copied {compose_file_src} to {destination_directory}")
        else:
            print(f"File {compose_file_src} already exists at destination.")
    except FileNotFoundError:
        print(f"File not found: {compose_file_src}")
    except PermissionError:
        print(f"Permission denied when copying {compose_file_src}")

    # Generate self-signed certificate and key
    os.makedirs(ssl_directory, exist_ok=True)

    try:
        if not os.path.exists(crt_path) or not os.path.exists(key_path):
            subprocess.run([
                'openssl', 'req', '-x509', '-nodes', '-days', '365',
                '-newkey', 'rsa:2048', '-keyout', key_path, '-out', crt_path,
                '-subj', '/CN=localhost'
            ], check=True)
            print(f"Generated self-signed certificate at {crt_path} and key at {key_path}")
        else:
            print(f"Self-signed certificate and key already exist at {crt_path} and {key_path}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to generate self-signed certificate: {e}")

    # Update nginx.conf with the provided IP address
    try:
        if os.path.exists(nginx_conf_path):
            with open(nginx_conf_path, 'r') as file:
                nginx_conf = file.read()

            nginx_conf = nginx_conf.replace('ENTER IP ADDR HERE', server_ip)

            with open(nginx_conf_path, 'w') as file:
                file.write(nginx_conf)

            print(f"Updated {nginx_conf_path} with the IP address {server_ip}")
        else:
            print(f"File not found: {nginx_conf_path}")
    except PermissionError:
        print(f"Permission denied when updating {nginx_conf_path}")

# Run docker-compose up -d
try:
    subprocess.run(['docker-compose', 'up', '-d'], cwd=destination_directory, check=True)
    print("Docker containers are up and running.")
except subprocess.CalledProcessError as e:
    print(f"Failed to start Docker containers: {e}")

# Prevent the system from suspending, sleeping, or hibernating when the laptop lid is closed
try:
    with open('/etc/systemd/logind.conf', 'r') as file:
        logind_conf = file.read()

    logind_conf = logind_conf.replace('#HandleLidSwitch=suspend', 'HandleLidSwitch=ignore')
    logind_conf = logind_conf.replace('#HandleLidSwitchDocked=suspend', 'HandleLidSwitchDocked=ignore')
    logind_conf = logind_conf.replace('#HandleLidSwitchExternalPower=suspend', 'HandleLidSwitchExternalPower=ignore')

    with open('/tmp/logind.conf', 'w') as file:
        file.write(logind_conf)

    run_sudo_command(['mv', '/tmp/logind.conf', '/etc/systemd/logind.conf'], sudo_password)

    # Restart systemd-logind service to apply changes
    run_sudo_command(['systemctl', 'restart', 'systemd-logind'], sudo_password)
    print("Configured the system to ignore lid close actions and restarted systemd-logind service.")
except FileNotFoundError:
    print("File not found: /etc/systemd/logind.conf")
except PermissionError:
    print("Permission denied when modifying /etc/systemd/logind.conf")
except subprocess.CalledProcessError as e:
    print(f"Failed to restart systemd-logind service: {e}")

# Install Ollama
try:
    subprocess.run(['sh', '-c', 'curl -fsSL https://ollama.com/install.sh | sh'], check=True)
    print("Ollama has been installed successfully.")
except subprocess.CalledProcessError as e:
    print(f"Failed to install Ollama: {e}")

# Check if stable-diffusion-webui exists before attempting to install it
stable_diffusion_dir = os.path.expanduser('~/stable-diffusion-webui')
if not os.path.exists(stable_diffusion_dir):
    try:
        subprocess.run(['git', 'clone', 'https://github.com/AUTOMATIC1111/stable-diffusion-webui.git', stable_diffusion_dir], check=True)
        print(f"Cloned stable-diffusion-webui into {stable_diffusion_dir}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to clone stable-diffusion-webui: {e}")

    # Create systemd service for stable-diffusion-webui
    service_content = f"""[Unit]
Description=Stable Diffusion Web UI
After=network.target

[Service]
Type=simple
ExecStart={stable_diffusion_dir}/webui.sh --api --listen
WorkingDirectory={stable_diffusion_dir}
User={os.getlogin()}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    service_path = '/etc/systemd/system/stable-diffusion-webui.service'
    try:
        with open('/tmp/stable-diffusion-webui.service', 'w') as file:
            file.write(service_content)

        run_sudo_command(['mv', '/tmp/stable-diffusion-webui.service', service_path], sudo_password)

        # Enable and start the service
        run_sudo_command(['systemctl', 'enable', 'stable-diffusion-webui'], sudo_password)
        run_sudo_command(['systemctl', 'start', 'stable-diffusion-webui'], sudo_password)
        print("Enabled and started the stable-diffusion-webui service.")
    except PermissionError:
        print(f"Permission denied when creating or enabling {service_path}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to enable or start stable-diffusion-webui service: {e}")
else:
    print(f"stable-diffusion-webui already exists at {stable_diffusion_dir}, skipping installation and service creation.")
