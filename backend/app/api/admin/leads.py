from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.schemas.leads import (
    LeadOperationalOverviewResponse,
    LeadResponse,
    LeadUpdateRequest,
)
from app.modules.leads.application.services import LeadManagementService
from app.modules.leads.infrastructure.repositories import SqlAlchemyLeadRepository

router = APIRouter(prefix="/admin/leads", tags=["Admin Leads"])


def _service(session: Session) -> LeadManagementService:
    return LeadManagementService(SqlAlchemyLeadRepository(session))


def _response(lead) -> LeadResponse:
    return LeadResponse(
        id=lead.id,
        application_id=lead.application_id,
        conversation_id=lead.conversation_id,
        name=lead.name,
        email=lead.email,
        phone=lead.phone,
        message=lead.message,
        status=lead.status,
        internal_note=lead.internal_note,
        consent_given=lead.consent_given,
        consent_text_version=lead.consent_text_version,
        consent_text=lead.consent_text,
        consented_at=lead.consented_at,
        first_contacted_at=lead.first_contacted_at,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


def _csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@router.get(
    "/application/{application_id}",
    response_model=list[LeadResponse],
)
def list_application_leads(
    application_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[LeadResponse]:
    leads = _service(session).list_leads(
        application_id=application_id,
        status=status_filter,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )
    return [_response(lead) for lead in leads]


@router.get(
    "/application/{application_id}/export/data",
    response_model=list[LeadResponse],
)
def export_application_lead_data(
    application_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    session: Session = Depends(get_session),
) -> list[LeadResponse]:
    leads = _service(session).export_leads(
        application_id=application_id,
        status=status_filter,
        created_from=created_from,
        created_to=created_to,
    )
    return [_response(lead) for lead in leads]


@router.get(
    "/application/{application_id}/overview",
    response_model=LeadOperationalOverviewResponse,
)
def get_application_lead_overview(
    application_id: str,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    session: Session = Depends(get_session),
) -> LeadOperationalOverviewResponse:
    overview = _service(session).lead_operational_overview(
        application_id=application_id,
        created_from=created_from,
        created_to=created_to,
    )
    return LeadOperationalOverviewResponse(
        total_count=overview.total_count,
        new_count=overview.new_count,
        contacted_count=overview.contacted_count,
        closed_count=overview.closed_count,
        average_first_contact_hours=overview.average_first_contact_hours,
        measured_first_contact_count=overview.measured_first_contact_count,
    )


@router.patch(
    "/application/{application_id}/{lead_id}",
    response_model=LeadResponse,
)
def update_application_lead(
    application_id: str,
    lead_id: str,
    payload: LeadUpdateRequest,
    session: Session = Depends(get_session),
) -> LeadResponse:
    lead = _service(session).update_lead(
        application_id=application_id,
        lead_id=lead_id,
        status=payload.status,
        internal_note=payload.internal_note,
    )
    return _response(lead)


@router.delete(
    "/application/{application_id}/{lead_id}",
    status_code=204,
)
def delete_application_lead(
    application_id: str,
    lead_id: str,
    session: Session = Depends(get_session),
) -> Response:
    _service(session).delete_lead(
        application_id=application_id,
        lead_id=lead_id,
    )
    return Response(status_code=204)


@router.get("/application/{application_id}/export")
def export_application_leads(
    application_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    session: Session = Depends(get_session),
) -> Response:
    leads = _service(session).export_leads(
        application_id=application_id,
        status=status_filter,
        created_from=created_from,
        created_to=created_to,
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "created_at",
            "status",
            "name",
            "email",
            "phone",
            "message",
            "internal_note",
            "conversation_id",
            "consented_at",
            "consent_text_version",
            "consent_text",
        ]
    )
    for lead in leads:
        writer.writerow(
            [
                _csv_cell(lead.id),
                _csv_cell(lead.created_at.isoformat()),
                _csv_cell(lead.status),
                _csv_cell(lead.name),
                _csv_cell(lead.email),
                _csv_cell(lead.phone),
                _csv_cell(lead.message),
                _csv_cell(lead.internal_note),
                _csv_cell(lead.conversation_id),
                _csv_cell(lead.consented_at.isoformat()),
                _csv_cell(lead.consent_text_version),
                _csv_cell(lead.consent_text),
            ]
        )
    filename = f"application-{application_id}-leads.csv"
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
