"""Open position data model.

A :class:`Position` tracks the current state of a coin holding —
cost basis, DCA history, and trailing profit-margin state.

Unlike the other models this is *mutable* because the trader updates
position state in-place as prices change and DCA buys occur.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Position:
    """Tracks a single open coin position.

    Parameters
    ----------
    coin:
        Coin ticker, e.g. ``"BTC"``.
    entry_price:
        Price at which the initial buy was executed.
    quantity:
        Total quantity held (base asset units).
    cost_basis_usd:
        Total USD spent to acquire the current quantity
        (sum of all buys including DCA).
    dca_count:
        Number of DCA buys executed for this position.
    dca_timestamps:
        Unix epoch (seconds) of each DCA buy, used for the rolling
        24-hour rate limit window.
    trailing_active:
        ``True`` when the price has reached the profit-margin start
        line and trailing tracking is engaged.
    trailing_peak:
        Highest price observed since trailing became active.
    trailing_line:
        Current trailing exit line (peak minus trailing gap).
    """

    coin: str
    entry_price: float
    quantity: float
    cost_basis_usd: float = 0.0
    dca_count: int = 0
    dca_timestamps: list[float] = field(default_factory=list)
    trailing_active: bool = False
    trailing_peak: float = 0.0
    trailing_line: float = 0.0

    # -- derived properties ---------------------------------------------------

    @property
    def avg_price(self) -> float:
        """Average cost per unit: ``cost_basis_usd / quantity``.

        Returns ``0.0`` if *quantity* is zero.
        """
        if self.quantity == 0.0:
            return 0.0
        return self.cost_basis_usd / self.quantity

    @property
    def has_dca(self) -> bool:
        """``True`` if at least one DCA buy has been executed."""
        return self.dca_count > 0

    def pnl_pct(self, current_price: float) -> float:
        """Unrealised PnL percentage at *current_price*.

        Returns ``0.0`` if *avg_price* is zero.
        """
        avg = self.avg_price
        if avg == 0.0:
            return 0.0
        return (current_price - avg) / avg * 100.0

    def market_value(self, current_price: float) -> float:
        """Current market value of the position in quote currency."""
        return self.quantity * current_price

    # -- validation -----------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty means valid)."""
        errors: list[str] = []
        if not self.coin:
            errors.append("coin must not be empty.")
        if self.entry_price < 0:
            errors.append(f"entry_price={self.entry_price} must be >= 0.")
        if self.quantity < 0:
            errors.append(f"quantity={self.quantity} must be >= 0.")
        if self.cost_basis_usd < 0:
            errors.append(f"cost_basis_usd={self.cost_basis_usd} must be >= 0.")
        if self.dca_count < 0:
            errors.append(f"dca_count={self.dca_count} must be >= 0.")
        if self.trailing_peak < 0:
            errors.append(f"trailing_peak={self.trailing_peak} must be >= 0.")
        if self.trailing_line < 0:
            errors.append(f"trailing_line={self.trailing_line} must be >= 0.")
        return errors
