"""Collection-only ETL for NSW property sales and rental-bond data.

Public API — the stable entrypoints most callers need:

    from propertyiq_getdata import update_nswgov, update_rentboard, audit_outputs

Source-specific internals live under :mod:`propertyiq_getdata.sources`, and the
reusable pipeline mechanics (paths, manifests, atomic IO) under
:mod:`propertyiq_getdata.core`.
"""

from .audit import audit_outputs, print_audit
from .sources.nswgov import update_nswgov
from .sources.rentboard import update_rentboard

__all__ = [
    "__version__",
    "audit_outputs",
    "print_audit",
    "update_nswgov",
    "update_rentboard",
]

__version__ = "0.1.0"
