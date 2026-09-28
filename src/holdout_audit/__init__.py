"""holdout_audit: scientific audits for trading strategies (Holdout Labs).

Statistical findings about the fragility of past data only. Not investment advice.
"""

__version__ = "0.4.1"

from holdout_audit.audit import AuditConfig, AuditResult, run_audit  # noqa: E402

__all__ = ["AuditConfig", "AuditResult", "run_audit", "__version__"]
