import requests
from smtplib import SMTP
import os
from dotenv import load_dotenv


load_dotenv()

RECEIVER_EMAIL_ADD = os.getenv('RECEIVER_EMAIL_ADDRESS')
EMAIL_ADD = os.getenv('EMAIL_ADDRESS')
EMAIL_PWD = os.getenv('EMAIL_PASSWORD')

def send_notification(msg):
    with SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.ehlo()
        smtp.login(EMAIL_ADD, EMAIL_PWD)
        smtp.sendmail(EMAIL_ADD, RECEIVER_EMAIL_ADD, msg)

try:
    response = requests.get('http://172-104-136-35.ip.linodeusercontent.com:8080')

    # print(response.status_code)
    if response.status_code == 200:
        print("Application is running successfully!")
    else:
        print("Application is down, fix it!")
        # send email to me
        msg = "Subject: APPLICATION IS DOWN\nThe application returned status code {response.status_code}, fix ASAP!"
        send_notification(msg)
except Exception as ex:
    print(f"Connection error happened: {ex}")
    msg = "Subject: SITE IS DOWN\nThe application is not accessible at all, fix ASAP!"
    send_notification(msg)