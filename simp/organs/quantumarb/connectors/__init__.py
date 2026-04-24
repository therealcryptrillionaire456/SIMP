#!/usr/bin/env python3.10
"""
Exchange Connectors Package.

Provides a factory for creating exchange connector instances with
jurisdiction-aware whitelisting for NY/NJ compliance.

Whitelisted exchanges (NY/NJ allowed):
    - coinbase  -> CoinbaseConnector
    - kraken    -> KrakenConnector
    - bitstamp  -> BitstampConnector
"""

from __future__ import annotations

import logging
from typing import Optional

# Import existing connectors from the quantumarb parent package
from ..coinbase_connector import CoinbaseConnector

# Import connectors from this same directory
try:
    from .kraken_connector import KrakenConnector  # type: ignore[import-untyped]  # noqa: F401
except ImportError:
    KrakenConnector = None  # type: ignore

try:
    from .bitstamp_connector import BitstampConnector  # type: ignore[import-untyped]  # noqa: F401
except ImportError:
    BitstampConnector = None  # type: ignore

LOG = logging.getLogger("exchange_connectors")

# NY/NJ Jurisdiction Compliance Whitelist
# Only these exchanges may be used in New York and New Jersey.
EXCHANGE_WHITELIST: set[str] = {"coinbase", "kraken", "bitstamp"}

# Mapping of whitelisted exchange names to their connector classes.
_CONNECTOR_MAP: dict[str, type] = {
    "coinbase": CoinbaseConnector,
}

if KrakenConnector is not None:
    _CONNECTOR_MAP["kraken"] = KrakenConnector
if BitstampConnector is not None:
    _CONNECTOR_MAP["bitstamp"] = BitstampConnector

__all__ = [
    "CoinbaseConnector",
    "EXCHANGE_WHITELIST",
    "create_exchange_connector",
]


def create_exchange_connector(
    exchange_name: str,
    sandbox: bool = True,
    api_key: str = "",
    api_secret: str = "",
    **kwargs,
) -> Optional[object]:
    """
    Factory: return a connector instance for the given exchange.

    Only exchanges on EXCHANGE_WHITELIST are permitted.  All others are
    rejected with a warning.

    Parameters
    ----------
    exchange_name : str
        Lowercase exchange identifier (e.g. "coinbase").
    sandbox : bool
        Whether to use the sandbox/test environment.  Default ``True``.
    api_key : str
        API key or credential string.
    api_secret : str
        API secret or credential string.

    Returns
    -------
    object or None
        A connector instance, or ``None`` when the exchange is unsupported.
    """
    exchange = exchange_name.strip().lower()

    if exchange not in EXCHANGE_WHITELIST:
        LOG.warning(
            "Exchange '%s' is NOT on the NY/NJ whitelist and will be rejected. "
            "Whitelisted: %s",
            exchange_name,
            sorted(EXCHANGE_WHITELIST),
        )
        return None

    connector_cls = _CONNECTOR_MAP.get(exchange)
    if connector_cls is None:
        LOG.warning(
            "Exchange '%s' is whitelisted but no connector class is available yet.",
            exchange,
        )
        return None

    LOG.info(
        "Creating %s connector (sandbox=%s) …",
        exchange,
        sandbox,
    )
    return connector_cls(
        api_key=api_key,
        api_secret=api_secret,
        sandbox=sandbox,
        **kwargs,
    )
