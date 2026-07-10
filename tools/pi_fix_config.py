#!/usr/bin/env python3
"""Update Pi config for faster streaming."""
import paramiko, json, time

host = '10.40.167.245'
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username='jarvis', password='1234', timeout=10, banner_timeout=10)
print(f"Connected to {host}")

# Read config
sftp = client.open_sftp()
with sftp.open('/home/jarvis/Documents/Stasis/rover/rpi2b/config.json', 'r') as f:
    config = json.loads(f.read().decode())
print(f"Old camera: {config['camera']['width']}x{config['camera']['height']} quality={config['camera']['jpeg_quality']} interval={config['camera']['upload_interval_seconds']}")

# Optimize
config['camera']['width'] = 320
config['camera']['height'] = 240
config['camera']['jpeg_quality'] = 50
config['camera']['upload_interval_seconds'] = 0.15
config['camera']['fps'] = 15

with sftp.open('/home/jarvis/Documents/Stasis/rover/rpi2b/config.json', 'w') as f:
    f.write(json.dumps(config, indent=2))
sftp.close()
print(f"New camera: {config['camera']['width']}x{config['camera']['height']} quality={config['camera']['jpeg_quality']} interval={config['camera']['upload_interval_seconds']}")

# Kill old rover
client.exec_command('pkill -9 -f rover_client_object_detection')
time.sleep(2)

# Start new rover
cmd = 'cd ~/Documents/Stasis/rover/rpi2b && . .venv/bin/activate && exec python rover_client_object_detection.py --config config.json'
client.exec_command(f'nohup bash -c \'{cmd}\' > /tmp/rover_opt.log 2>&1 &')
time.sleep(5)

# Check
stdin, stdout, stderr = client.exec_command('tail -12 /tmp/rover_opt.log')
print(f"\nNew rover log:\n{stdout.read().decode()}")

client.close()
print("Done!")
