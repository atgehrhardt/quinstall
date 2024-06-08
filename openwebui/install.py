import shutil
import os
import subprocess
import getpass

# Prompt the user for the server IP address
server_ip = input("Enter the IP address of your server: ")

# Prompt the user for their sudo password
sudo_password = getpass.getpass("Enter your sudo password: ")

# Install Ollama
try:
    subprocess.run(['curl', '-fsSL', 'https://ollama.com/install.sh', '|', 'sh'], input=sudo_password.encode(), check=True, shell=True)
    print("Ollama has been installed successfully.")
except subprocess.CalledProcessError as e:
    print(f"Failed to install Ollama: {e}")

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
    # Move the directories and file
    try:
        shutil.move(nginx_src, destination_directory)
        print(f"Moved {nginx_src} to {destination_directory}")
    except FileNotFoundError:
        print(f"Directory not found: {nginx_src}")
    except PermissionError:
        print(f"Permission denied when moving {nginx_src}")

    try:
        shutil.move(searxng_src, destination_directory)
        print(f"Moved {searxng_src} to {destination_directory}")
    except FileNotFoundError:
        print(f"Directory not found: {searxng_src}")
    except PermissionError:
        print(f"Permission denied when moving {searxng_src}")

    try:
        shutil.move(compose_file_src, destination_directory)
        print(f"Moved {compose_file_src} to {destination_directory}")
    except FileNotFoundError:
        print(f"File not found: {compose_file_src}")
    except PermissionError:
        print(f"Permission denied when moving {compose_file_src}")

    # Generate self-signed certificate and key
    os.makedirs(ssl_directory, exist_ok=True)

    try:
        subprocess.run([
            'openssl', 'req', '-x509', '-nodes', '-days', '365',
            '-newkey', 'rsa:2048', '-keyout', key_path, '-out', crt_path,
            '-subj', '/CN=localhost'
        ], check=True)
        print(f"Generated self-signed certificate at {crt_path} and key at {key_path}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to generate self-signed certificate: {e}")

    # Update nginx.conf with the provided IP address
    try:
        with open(nginx_conf_path, 'r') as file:
            nginx_conf = file.read()

        nginx_conf = nginx_conf.replace('ENTER IP ADDR HERE', server_ip)

        with open(nginx_conf_path, 'w') as file:
            file.write(nginx_conf)

        print(f"Updated {nginx_conf_path} with the IP address {server_ip}")
    except FileNotFoundError:
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

    with open('/etc/systemd/logind.conf', 'w') as file:
        file.write(logind_conf)

    # Restart systemd-logind service to apply changes
    subprocess.run(['sudo', '-S', 'systemctl', 'restart', 'systemd-logind'], input=sudo_password.encode(), check=True)
    print("Configured the system to ignore lid close actions and restarted systemd-logind service.")
except FileNotFoundError:
    print("File not found: /etc/systemd/logind.conf")
except PermissionError:
    print("Permission denied when modifying /etc/systemd/logind.conf")
except subprocess.CalledProcessError as e:
    print(f"Failed to restart systemd-logind service: {e}")

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
        with open(service_path, 'w') as file:
            file.write(service_content)
        print(f"Created systemd service file at {service_path}")

        # Enable and start the service
        subprocess.run(['sudo', '-S', 'systemctl', 'enable', 'stable-diffusion-webui'], input=sudo_password.encode(), check=True)
        subprocess.run(['sudo', '-S', 'systemctl', 'start', 'stable-diffusion-webui'], input=sudo_password.encode(), check=True)
        print("Enabled and started the stable-diffusion-webui service.")
    except PermissionError:
        print(f"Permission denied when creating or enabling {service_path}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to enable or start stable-diffusion-webui service: {e}")
else:
    print(f"stable-diffusion-webui already exists at {stable_diffusion_dir}, skipping installation and service creation.")