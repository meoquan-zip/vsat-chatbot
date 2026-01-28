from datetime import datetime, timedelta
from typing import List
from typing import Optional

from sqlalchemy.orm import Session

from utils.db_orm import (
    get_session,
    Incident,
)

# =========================Incident=========================

def list_incidents(session: Session = get_session()) -> List[Incident]:
    return session.query(Incident).all()


def get_incident_by_id(incident_id: str,
                       session: Session = get_session()) -> Optional[Incident]:
    return session.query(Incident).filter(Incident.id == incident_id).one_or_none()


def create_incident(name: str,
                    description: str,
                    email: str,
                    log: Optional[str] = None,
                    session: Session = get_session()) -> Incident:
    incident = Incident(
        name=name,
        description=description,
        email=email,
        log=log,
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident


def resolve_incident(incident_id: str,
                     session: Session = get_session()) -> Optional[Incident]:
    incident = get_incident_by_id(incident_id, session)
    if incident is None:
        return None
    incident.status = "resolved"
    session.commit()
    session.refresh(incident)
    return incident


def delete_incident(incident_id: str,
                    session: Session = get_session()) -> bool:
    incident = get_incident_by_id(incident_id, session)
    if incident is None:
        return False
    session.delete(incident)
    session.commit()
    return True


def get_overdue_incidents(sla_time: timedelta = timedelta(minutes=1),
                          session: Session = get_session()) -> List[Incident]:
    now = datetime.now()
    t = now - sla_time

    incidents = session.query(Incident).filter(
        Incident.status == "open",
        Incident.notified == False,
        Incident.created_at <= t
    ).all()
    return incidents


def mark_incident_notified(incident_id: str,
                           session: Session = get_session()) -> Optional[Incident]:
    incident = get_incident_by_id(incident_id, session)
    if incident is None:
        return None
    incident.notified = True
    session.commit()
    session.refresh(incident)
    return incident
