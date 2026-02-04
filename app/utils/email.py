import os
import smtplib
import threading
import time
from datetime import timedelta
from email.mime.text import MIMEText

from dotenv import load_dotenv
from jinja2 import Template

from .db_crud import (
    get_incident_by_id,
    is_incident_overdue,
    mark_incident_notified,
)
from .db_orm import Incident

load_dotenv()


def render_incident_email(incident: Incident) -> str:
    template_str = os.getenv(
        "INCIDENT_EMAIL_TEMPLATE",
        "{{ incident.name }} \n\n {{ incident.description }}"
    )
    template = Template(template_str)
    return template.render(incident=incident)


def send_incident_email_delay(incident_id: str,
                              subject: str = "Overdue Incident Notification"):
    incident = get_incident_by_id(incident_id)
    if incident is None:
        return

    delay_time = incident.sla_no_of_hours * 60  # leave as minutes for testing purposes
    time.sleep(delay_time)

    incident = get_incident_by_id(incident_id)
    if incident is None or not is_incident_overdue(incident.id):
        return

    smtp_server = os.getenv("SMTP_SERVER", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", 1025))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("FROM_EMAIL", "noreply@example.com")

    body = render_incident_email(incident)
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = incident.email

    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.sendmail(from_email, [incident.email], msg.as_string())
    
    mark_incident_notified(incident_id)


def init_incident_notifier(incident_id: str):    
    thread = threading.Thread(
        target=send_incident_email_delay,
        args=(incident_id,),
        daemon=True
    )
    thread.start()
    # thread.join()
