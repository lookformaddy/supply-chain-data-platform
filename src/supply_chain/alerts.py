"""Alert store: dedup plus lifecycle.

Dedup key is (kind, sku, location). A repeat of an already-open (or
acked) alert bumps its occurrence count and keeps the higher score —
one row per live problem, not one row per detection run. Lifecycle is
open -> acked -> resolved, with open -> resolved allowed; resolved is
terminal. Anything else raises InvalidAlertTransitionError.
"""

from __future__ import annotations

from supply_chain.errors import InvalidAlertTransitionError
from supply_chain.models import Alert

_ALLOWED = {
    "open": {"acked", "resolved"},
    "acked": {"resolved"},
    "resolved": set(),
}


class AlertStore:
    def __init__(self) -> None:
        self._alerts: dict[tuple[str, str, str], Alert] = {}

    def ingest(self, alert: Alert) -> Alert:
        """Insert, or dedup against a live alert with the same fingerprint."""
        existing = self._alerts.get(alert.fingerprint)
        if existing is not None and existing.status != "resolved":
            existing.occurrences += 1
            if alert.score > existing.score:
                existing.score = alert.score
                existing.severity = alert.severity
                existing.message = alert.message
            return existing
        self._alerts[alert.fingerprint] = alert
        return alert

    def transition(self, fingerprint: tuple[str, str, str],
                   new_status: str) -> Alert:
        alert = self._alerts.get(fingerprint)
        if alert is None:
            raise KeyError(f"unknown alert {fingerprint}")
        if new_status not in _ALLOWED[alert.status]:
            raise InvalidAlertTransitionError(
                f"cannot move alert {fingerprint} "
                f"{alert.status} -> {new_status}"
            )
        alert.status = new_status
        return alert

    def ack(self, fingerprint: tuple[str, str, str]) -> Alert:
        return self.transition(fingerprint, "acked")

    def resolve(self, fingerprint: tuple[str, str, str]) -> Alert:
        return self.transition(fingerprint, "resolved")

    def open_alerts(self) -> list[Alert]:
        return [a for a in self._alerts.values() if a.status == "open"]

    def by_status(self, status: str) -> list[Alert]:
        return [a for a in self._alerts.values() if a.status == status]

    def all(self) -> list[Alert]:
        return list(self._alerts.values())
