from datetime import datetime, timedelta
from functools import lru_cache
import os
from typing import List
from typing import Optional
import uuid

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    DateTime,
    func,
    String
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    Session,
)

load_dotenv()


class Base(DeclarativeBase):
    pass


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    log: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")  # "open" or "resolved"
    notified: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=False, server_default=func.now())
    # created_by: Mapped[Optional[str]] = mapped_column(String(255))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


@lru_cache()
def get_engine(connection_url: str = None) -> Engine:
    if connection_url is None:
        connection_url = os.getenv("DATABASE_URL", "sqlite:///./incidents.db")
    return create_engine(connection_url)


def get_session(engine: Engine = get_engine()) -> Session:
    return Session(engine)


def create_all_tables(engine: Engine = get_engine()) -> None:
    Base.metadata.create_all(engine)


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
