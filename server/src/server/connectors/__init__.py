"""Ingestion connectors — plug-in architecture for multi-source data loading."""

from server.connectors.base import BaseConnector, SourceRecord
from server.connectors.crm_mock import CRMConnector
from server.connectors.document import DocumentConnector
from server.connectors.email_mock import EmailConnector
from server.connectors.hr_mock import HRConnector
from server.connectors.itsm_mock import ITSMConnector

REGISTRY: dict[str, type[BaseConnector]] = {
    "email": EmailConnector,
    "crm": CRMConnector,
    "hr": HRConnector,
    "itsm": ITSMConnector,
    "document": DocumentConnector,
}

__all__ = [
    "BaseConnector",
    "SourceRecord",
    "EmailConnector",
    "CRMConnector",
    "HRConnector",
    "ITSMConnector",
    "DocumentConnector",
    "REGISTRY",
]
