"""Domain errors. Callers distinguish bad input from bad state."""


class SupplyChainError(Exception):
    """Base class for all domain errors."""


class UnknownNodeError(SupplyChainError):
    """A lane or query referenced a node that is not in the graph."""


class NoPathError(SupplyChainError):
    """No route exists between two nodes (possibly after disruption)."""


class InvalidAlertTransitionError(SupplyChainError, ValueError):
    """An alert lifecycle transition is not allowed.

    Also a ValueError so HTTP handlers can map it to a 409 with one
    except clause, without importing domain errors into the service.
    """
