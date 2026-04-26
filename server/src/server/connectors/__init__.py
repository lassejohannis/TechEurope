from __future__ import annotations

from typing import TypeVar, Dict, Type

from .base import BaseConnector


CONNECTOR_REGISTRY: Dict[str, Type[BaseConnector]] = {}


T = TypeVar("T", bound=Type[BaseConnector])


def register(connector_cls: T) -> T:
    source_type = getattr(connector_cls, "source_type", None)
    if not source_type:
        raise ValueError("Connector classes must define a source_type class attribute")
    CONNECTOR_REGISTRY[source_type] = connector_cls
    return connector_cls


def get_connector(name: str) -> Type[BaseConnector]:
    if name == "all":
        raise ValueError("'all' is not a single connector; iterate registry instead")
    if name in CONNECTOR_REGISTRY:
        return CONNECTOR_REGISTRY[name]
    # allow by class key as well
    for key, cls in CONNECTOR_REGISTRY.items():
        if cls.__name__.lower() == name.replace("-", "_"):
            return cls
    raise KeyError(f"Unknown connector: {name}. Known: {sorted(CONNECTOR_REGISTRY.keys())}")

# Eagerly import known connectors to populate registry
try:
    from .email import EmailConnector  # noqa: F401
    CONNECTOR_REGISTRY[getattr(EmailConnector, "source_type")] = EmailConnector
except Exception:
    pass
try:
    from .crm import CRMConnector  # noqa: F401
    CONNECTOR_REGISTRY[getattr(CRMConnector, "source_type")] = CRMConnector
except Exception:
    pass
try:
    from .hr import HRConnector  # noqa: F401
    CONNECTOR_REGISTRY[getattr(HRConnector, "source_type")] = HRConnector
except Exception:
    pass
try:
    from .pdf import InvoicePDFConnector  # noqa: F401
    CONNECTOR_REGISTRY[getattr(InvoicePDFConnector, "source_type")] = InvoicePDFConnector
except Exception:
    pass
try:
    from .itsm import ITSMConnector  # noqa: F401
    CONNECTOR_REGISTRY[getattr(ITSMConnector, "source_type")] = ITSMConnector
except Exception:
    pass
try:
    from .document import DocumentConnector  # noqa: F401
    CONNECTOR_REGISTRY[getattr(DocumentConnector, "source_type")] = DocumentConnector
except Exception:
    pass
try:
    from .collaboration import CollaborationConnector  # noqa: F401
    CONNECTOR_REGISTRY[getattr(CollaborationConnector, "source_type")] = CollaborationConnector
except Exception:
    pass
try:
    from .tavily import TavilySearchConnector  # noqa: F401
    CONNECTOR_REGISTRY[getattr(TavilySearchConnector, "source_type")] = TavilySearchConnector
except Exception:
    pass
