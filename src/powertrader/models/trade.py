"""Executed trade data model.

A :class:`Trade` is an immutable record of a single executed order — buy
or sell.  It is appended to ``trade_history.jsonl`` by the trader and
displayed in the Hub GUI.
"""

from __future__ import annotations

from dataclasses import dataclass

_VALID_SIDES = frozenset({"BUY", "SELL"})


@dataclass(frozen=True, slots=True)
class Trade:
    """Record of a single executed trade.

    Parameters
    ----------
    coin:
        Coin ticker, e.g. ``"BTC"``.
    side:
        ``"BUY"`` or ``"SELL"``.
    price:
        Execution / average fill price.
    quantity:
        Quantity in base asset units.
    value:
        Total quote value of the trade (``price * quantity``).
    reason:
        Why this trade was placed — e.g. ``"entry"``, ``"dca_stage_1"``,
        ``"dca_stage_3"``, ``"trailing_exit"``.
    timestamp:
        Unix epoch (seconds) when the order was filled.
    pnl_pct:
        Realised profit/loss percentage for sell trades.
        ``None`` for buy trades.
    fees_usd:
        Exchange fees paid in USD (if known).
    order_id:
        Exchange order ID string (if available).
    """

    coin: str
    side: str
    price: float
    quantity: float
    value: float
    reason: str
    timestamp: float
    pnl_pct: float | None = None
    fees_usd: float | None = None
    order_id: str | None = None

    # -- convenience ----------------------------------------------------------

    @property
    def is_buy(self) -> bool:
        """``True`` if this trade is a buy."""
        return self.side == "BUY"

    @property
    def is_sell(self) -> bool:
        """``True`` if this trade is a sell."""
        return self.side == "SELL"

    @property
    def is_dca(self) -> bool:
        """``True`` if the trade reason indicates a DCA buy."""
        return self.reason.startswith("dca_")

    # -- serialisation --------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        """Convert to a dictionary suitable for JSON-lines serialisation.

        Keys match the existing ``trade_history.jsonl`` schema used by
        the trader.
        """
        return {
            "ts": self.timestamp,
            "side": self.side.lower(),
            "tag": self.reason,
            "symbol": self.coin,
            "qty": self.quantity,
            "price": self.price,
            "pnl_pct": self.pnl_pct,
            "fees_usd": self.fees_usd,
            "order_id": self.order_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Trade:
        """Reconstruct a Trade from a ``trade_history.jsonl`` record.

        Handles both the new schema (``coin``, ``side`` upper) and the
        legacy schema (``symbol``, ``side`` lower, ``ts``, ``tag``).
        """
        side_raw = str(data.get("side", "BUY")).upper()
        coin = str(data.get("coin") or data.get("symbol") or "")

        def _get_float(key: str, *alt_keys: str, default: float = 0.0) -> float:
            for k in (key, *alt_keys):
                v = data.get(k)
                if v is not None:
                    try:
                        return float(str(v))
                    except (TypeError, ValueError):
                        continue
            return default

        return cls(
            coin=coin,
            side=side_raw,
            price=_get_float("price"),
            quantity=_get_float("qty", "quantity"),
            value=_get_float("value"),
            reason=str(data.get("reason") or data.get("tag") or ""),
            timestamp=_get_float("timestamp", "ts"),
            pnl_pct=_opt_float(data.get("pnl_pct")),
            fees_usd=_opt_float(data.get("fees_usd")),
            order_id=_opt_str(data.get("order_id")),
        )

    # -- validation -----------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty means valid)."""
        errors: list[str] = []
        if not self.coin:
            errors.append("coin must not be empty.")
        if self.side not in _VALID_SIDES:
            errors.append(f"side={self.side!r} must be 'BUY' or 'SELL'.")
        if self.price < 0:
            errors.append(f"price={self.price} must be >= 0.")
        if self.quantity < 0:
            errors.append(f"quantity={self.quantity} must be >= 0.")
        if self.value < 0:
            errors.append(f"value={self.value} must be >= 0.")
        if self.timestamp < 0:
            errors.append(f"timestamp={self.timestamp} must be >= 0.")
        return errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opt_float(val: object) -> float | None:
    if val is None:
        return None
    try:
        return float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _opt_str(val: object) -> str | None:
    if val is None:
        return None
    return str(val)
