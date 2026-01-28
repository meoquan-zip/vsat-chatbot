from datetime import timedelta
from email.mime.text import MIMEText
import os
import smtplib
import threading
import time

from dotenv import load_dotenv
from jinja2 import Template

from utils.db_crud import (
    get_overdue_incidents,
    mark_incident_notified,
)

load_dotenv()


def render_incident_email(incident):
	template_str = """
	Incident Notification\n\n
	ID: {{ incident.id }}\n
	Name: {{ incident.name }}\n
	Description: {{ incident.description }}\n
	Log: {{ incident.log or 'N/A' }}\n
	Created At: {{ incident.created_at }}\n
	"""
	template = Template(template_str)
	return template.render(incident=incident)


def send_email(to_email, subject, body):
	smtp_server = os.getenv("SMTP_SERVER", "localhost")
	smtp_port = int(os.getenv("SMTP_PORT", 1025))
	smtp_user = os.getenv("SMTP_USER", "")
	smtp_password = os.getenv("SMTP_PASSWORD", "")
	from_email = os.getenv("FROM_EMAIL", "noreply@example.com")

	msg = MIMEText(body)
	msg["Subject"] = subject
	msg["From"] = from_email
	msg["To"] = to_email

	with smtplib.SMTP(smtp_server, smtp_port) as server:
		if smtp_user and smtp_password:
			server.starttls()
			server.login(smtp_user, smtp_password)
		server.sendmail(from_email, [to_email], msg.as_string())


def notify_overdue_incidents(sla_time: timedelta = timedelta(minutes=1)):
    overdue = get_overdue_incidents(sla_time)
    for incident in overdue:
        try:
            body = render_incident_email(incident)
            send_email(incident.email, "Incident Notification", body)
            mark_incident_notified(incident.id)
        except Exception as e:
            print(f"Failed to notify incident {incident.id}: {e}")


def start_periodic_notifier(interval_seconds: int = 20):
    def run_notifier():
        while True:
            notify_overdue_incidents()
            time.sleep(interval_seconds)
    thread = threading.Thread(target=run_notifier, daemon=True)
    thread.start()
