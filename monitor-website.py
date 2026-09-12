import requests
from smtplib import SMTP
import os
from dotenv import load_dotenv
import paramiko
import linode_api4
import time
import schedule


load_dotenv()

RECEIVER_EMAIL_ADD = os.getenv('RECEIVER_EMAIL_ADDRESS')
EMAIL_ADD = os.getenv('EMAIL_ADDRESS')
EMAIL_PWD = os.getenv('EMAIL_PASSWORD')
LINODE_TOKEN = os.getenv('LINODE_TOKEN')

def send_notification(msg):
    with SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.ehlo()
        smtp.login(EMAIL_ADD, EMAIL_PWD)
        smtp.sendmail(EMAIL_ADD, RECEIVER_EMAIL_ADD, msg)


def restart_container():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname='172.104.132.102', username='root', key_filename='/home/oluwasade/.ssh/secureops_key')
    
    # come back to figure out how to dynamically get container id for the docker start command.
    # stdin, stdout, stderr = ssh.exec_command('docker ps')
    stdin, stdout, stderr = ssh.exec_command('docker start 6949cbbc8694')
    print(stdout.readlines())
    ssh.close()


def restart_server_and_container():
    print("Rebooting the server...")
    client = linode_api4.LinodeClient(LINODE_TOKEN)
    nginx_server = client.load(linode_api4.Instance, 105038890)
    nginx_server.reboot()
    
    print('Server has been rebooted')
    
    # restart the application
    while True:
        nginx_server = client.load(linode_api4.Instance, 105038890)
        if nginx_server.status == 'running':
            time.sleep(8)
            print("Restarting the application...")
            
            restart_container()
            
            print("Application has been restarted")
            break
        
def monitor_application():
    try:
        response = requests.get('http://172-104-132-102.ip.linodeusercontent.com:8080')

        if response.status_code == 200:
            print("Application is running successfully!")
        else:
            print("Application is down, fix it!")
            
            # send email to me
            msg = "Subject: APPLICATION IS DOWN\nThe application returned status code {response.status_code}, fix ASAP!"
            print("Sending email notification...")
            send_notification(msg)
            
            print("Restarting the app's container...")
            restart_container()     
            print("Application restarted")
            
    except Exception as ex:
        print(f"Connection error happened: {ex}")
        msg = "Subject: SITE IS DOWN\nThe application is not accessible at all, fix ASAP!"
        
        print("Sending email notification...")
        send_notification(msg)
        
        # restart linode server
        restart_server_and_container()
        
schedule.every(2).day.at("00:00", "Europe/Warsaw").do(monitor_application)

while True:
    schedule.run_pending()