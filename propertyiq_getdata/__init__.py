"""Collection-only ETL for NSW property data sources.

Public API — the stable entrypoints most callers need:

    from propertyiq_getdata import update_nswgov, update_rentboard, audit_outputs

Source-specific internals live under :mod:`propertyiq_getdata.sources`, and the
reusable pipeline mechanics (paths, manifests, atomic IO) under
:mod:`propertyiq_getdata.core`.
"""

from .audit import audit_outputs, print_audit
from .sinks.databricks import publish_databricks
from .sources.abs import update_abs
from .sources.abs_ts import update_abs_ts
from .sources.nswgov import update_nswgov
from .sources.rba import update_rba
from .sources.rentboard import update_rentboard

__all__ = [
    "__version__",
    "audit_outputs",
    "print_audit",
    "publish_databricks",
    "update_abs",
    "update_abs_ts",
    "update_nswgov",
    "update_rba",
    "update_rentboard",
]

__version__ = "0.1.0"
