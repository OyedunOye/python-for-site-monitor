import requests
from smtplib import SMTP
import os
from dotenv import load_dotenv
import paramiko
import linode_api4
import time
import schedule


load_dotenv(override=True)

RECEIVER_EMAIL_ADD = os.getenv('RECEIVER_EMAIL_ADDRESS')
EMAIL_ADD = os.getenv('EMAIL_ADDRESS')
EMAIL_PWD = os.getenv('EMAIL_PASSWORD')
LINODE_TOKEN = os.getenv('LINODE_TOKEN')
LINODE_LABEL = os.getenv('LINODE_LABEL')
CONTAINER_NAME = os.getenv('CONTAINER_NAME')
APP_PORT = os.getenv('APP_PORT')
SSH_USER = os.getenv('SSH_USER')
SSH_KEY_PATH = os.getenv('SSH_KEY_PATH')

linode_client = linode_api4.LinodeClient(LINODE_TOKEN)


def get_server():
    print(linode_client.linode.instances(linode_api4.Instance.label == LINODE_LABEL)[0])
    return linode_client.linode.instances(linode_api4.Instance.label == LINODE_LABEL)[0]

def send_notification(msg):
    with SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.ehlo()
        smtp.login(EMAIL_ADD, EMAIL_PWD)
        smtp.sendmail(EMAIL_ADD, RECEIVER_EMAIL_ADD, msg)


def restart_container(server_ip, attempts=12):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for _ in range(attempts):
        try:
            ssh.connect(hostname=server_ip, username=SSH_USER, key_filename=SSH_KEY_PATH, timeout=10)
            break
        except (OSError, paramiko.SSHException) as ex:
            print(f"SSH not ready yet ({ex}), retrying in 10s...")
            time.sleep(10)
    else:
        raise RuntimeError(f"Could not SSH into {server_ip} after {attempts} attempts")

    # the Docker daemon can come up a few seconds after SSH on boot, so retry until docker start succeeds
    for _ in range(attempts):
        stdin, stdout, stderr = ssh.exec_command(f'docker start {CONTAINER_NAME}')
        if stdout.channel.recv_exit_status() == 0:
            print(f"Container {CONTAINER_NAME} started")
            break
        print(f"docker start failed ({stderr.read().decode().strip()}), retrying in 10s...")
        time.sleep(10)
    else:
        ssh.close()
        raise RuntimeError(f"Could not start container {CONTAINER_NAME} on {server_ip} after {attempts} attempts")

    ssh.close()


def restart_server_and_container():
    print("Rebooting the server...")
    server = get_server()
    server.reboot()

    # true while the server is preparing to shut down, turns false once running switches to rebooting
    while linode_client.load(linode_api4.Instance, server.id).status == 'running':
        time.sleep(2)
    print("Server is rebooting...")

    # true while the server has moved to the rebooting status
    while linode_client.load(linode_api4.Instance, server.id).status != 'running':
        time.sleep(5)
    print("Server is back up, restarting the application...")

    restart_container(server.ipv4[0])
    print("Application has been restarted")


def monitor_application():
    server_ip = get_server().ipv4[0]
    try:
        response = requests.get(f'http://{server_ip}:{APP_PORT}')

        if response.status_code == 200:
            print("Application is running successfully!")
        else:
            print("Application is down, fix it!")
            
            # send email to me
            msg = "Subject: APPLICATION IS DOWN\nThe application returned status code {response.status_code}, fix ASAP!"
            print("Sending email notification...")
            send_notification(msg)
            
            print("Restarting the app's container...")
            restart_container(server_ip)
            print("Application restarted")
            
    except Exception as ex:
        print(f"Connection error happened: {ex}")
        msg = "Subject: SITE IS DOWN\nThe application is not accessible at all, fix ASAP!"
        
        print("Sending email notification...")
        send_notification(msg)

        # restart linode server
        restart_server_and_container()
        
# schedule.every(2).day.at("00:00", "Europe/Warsaw").do(monitor_application)
schedule.every(2).minutes.do(monitor_application)

while True:
    schedule.run_pending()