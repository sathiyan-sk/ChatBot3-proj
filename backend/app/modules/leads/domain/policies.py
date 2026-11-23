from __future__ import annotations

import re

from app.core.exceptions import ApplicationError

LEAD_CONSENT_TEXT_VERSION = "lead-consent-v1"
LEAD_CONSENT_TEXT = (
    "I agree to share these contact details and my enquiry with the business "
    "so its team can follow up with me."
)

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_PATTERN = re.compile(r"^[+()\d.\-\s]+$")
_CONTACT_INTENT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bcontact me\b",
        r"\bcall me\b",
        r"\bemail me\b",
        r"\bget in touch with me\b",
        r"\bspeak (?:to|with) (?:a person|someone|somebody|your team|(?:your )?sales team|sales)\b",
        r"\btalk (?:to|with) (?:a person|someone|somebody|your team|(?:your )?sales team|sales)\b",
        r"\b(?:sales|business) team (?:contact|call|email|reach)\b",
        r"\bcan (?:someone|somebody|your team) (?:contact|call|email|reach) me\b",
    )
)


def has_contact_intent(message: str) -> bool:
    if re.search(
        r"\b(?:do not|don't|never)\s+(?:call|contact|email)\s+me\b", message, re.I
    ):
        return False
    return any(pattern.search(message) for pattern in _CONTACT_INTENT_PATTERNS)


def normalize_lead_contact(
    *,
    name: str,
    email: str | None,
    phone: str | None,
    message: str | None,
) -> tuple[str, str | None, str | None, str | None]:
    normalized_name = name.strip()
    normalized_email = email.strip().lower() if email and email.strip() else None
    normalized_phone = phone.strip() if phone and phone.strip() else None
    normalized_message = message.strip() if message and message.strip() else None

    if not normalized_name or len(normalized_name) > 120:
        raise ApplicationError(
            message="Name is required and must be at most 120 characters.",
            code="lead_name_invalid",
            status_code=422,
        )
    if not normalized_email and not normalized_phone:
        raise ApplicationError(
            message="Provide an email address or phone number.",
            code="lead_contact_required",
            status_code=422,
        )
    if normalized_email and (
        len(normalized_email) > 254 or not _EMAIL_PATTERN.fullmatch(normalized_email)
    ):
        raise ApplicationError(
            message="Email address is invalid.",
            code="lead_email_invalid",
            status_code=422,
        )
    if normalized_phone and (
        len(normalized_phone) > 32
        or not _PHONE_PATTERN.fullmatch(normalized_phone)
        or not 7 <= sum(character.isdigit() for character in normalized_phone) <= 15
    ):
        raise ApplicationError(
            message="Phone number is invalid.",
            code="lead_phone_invalid",
            status_code=422,
        )
    if normalized_message and len(normalized_message) > 2000:
        raise ApplicationError(
            message="Enquiry message must be at most 2000 characters.",
            code="lead_message_too_long",
            status_code=422,
        )
    return (
        normalized_name,
        normalized_email,
        normalized_phone,
        normalized_message,
    )
