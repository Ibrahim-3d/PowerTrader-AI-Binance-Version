#!/usr/bin/env python3
"""
Performance Attribution Engine for PowerTrader
Analyze sources of portfolio returns through factor decomposition and attribution analysis.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class AttributionType(Enum):
    """Types of performance attribution analysis."""

    SECTOR = "sector"
    FACTOR = "factor"
    STYLE = "style"
    SECURITY = "security"


class AttributionMethod(Enum):
    """Methods for attribution calculation."""

    BRINSON_HOOD_BEEBOWER = "bhb"
    BRINSON_FACHLER = "bf"
    ARITHMETIC = "arithmetic"
    GEOMETRIC = "geometric"


@dataclass
class AttributionResult:
    """Results of performance attribution analysis."""

    total_attribution: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    attribution_breakdown: Dict[str, float]
    period_start: datetime
    period_end: datetime
    attribution_type: AttributionType
    method: AttributionMethod


@dataclass
class FactorExposure:
    """Factor exposure data for a security or portfolio."""

    security: str
    exposures: Dict[str, float]  # factor_name -> exposure
    date: datetime


@dataclass
class Holding:
    """Portfolio holding information."""

    security: str
    weight: float
    return_period: float
    sector: Optional[str] = None
    market_cap: Optional[float] = None
    style_scores: Optional[Dict[str, float]] = None


class PerformanceAttributionEngine:
    """
    Advanced performance attribution engine for portfolio analysis.

    Provides multiple attribution methods including:
    - Brinson-Hood-Beebower attribution
    - Factor-based attribution
    - Sector attribution
    - Style attribution
    - Security selection analysis
    """

    def __init__(self):
        """Initialize the Performance Attribution Engine."""
        self.factor_models = {}
        self.benchmark_data = {}
        self.sector_classifications = {}
        self.style_factors = [
            "value",
            "growth",
            "momentum",
            "quality",
            "volatility",
            "size",
        ]

        # Common equity factors (Fama-French style)
        self.equity_factors = [
            "market",
            "size",
            "value",
            "momentum",
            "profitability",
            "investment",
        ]

        # Initialize with sample factor returns if available
        self._initialize_sample_factors()

    def _initialize_sample_factors(self):
        """Initialize with sample factor data for demonstration."""
        # Sample factor returns (annualized)
        self.sample_factor_returns = {
            "market": 0.08,
            "size": 0.02,
            "value": 0.03,
            "momentum": 0.01,
            "profitability": 0.025,
            "investment": -0.015,
            "quality": 0.02,
            "volatility": -0.01,
        }

        # Sample sector classifications
        self.sector_classifications = {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "GOOGL": "Technology",
            "AMZN": "Consumer Discretionary",
            "TSLA": "Consumer Discretionary",
            "JPM": "Financials",
            "BAC": "Financials",
            "XOM": "Energy",
            "CVX": "Energy",
            "JNJ": "Healthcare",
            "PFE": "Healthcare",
            "BTC": "Cryptocurrency",
            "ETH": "Cryptocurrency",
            "BNB": "Cryptocurrency",
        }

    def brinson_attribution(
        self,
        portfolio_holdings: List[Holding],
        benchmark_holdings: List[Holding],
        method: AttributionMethod = AttributionMethod.BRINSON_HOOD_BEEBOWER,
    ) -> AttributionResult:
        """
        Perform Brinson attribution analysis.

        Args:
            portfolio_holdings: List of portfolio holdings
            benchmark_holdings: List of benchmark holdings
            method: Attribution method to use

        Returns:
            AttributionResult with breakdown of allocation, selection, and interaction effects
        """
        # Convert holdings to DataFrames for easier manipulation
        portfolio_df = self._holdings_to_dataframe(portfolio_holdings)
        benchmark_df = self._holdings_to_dataframe(benchmark_holdings)

        # Ensure we have sector classifications
        portfolio_df["sector"] = portfolio_df["security"].map(
            lambda x: (
                x.sector
                if hasattr(x, "sector") and x.sector
                else self.sector_classifications.get(str(x), "Other")
            )
        )
        benchmark_df["sector"] = benchmark_df["security"].map(
            lambda x: (
                x.sector
                if hasattr(x, "sector") and x.sector
                else self.sector_classifications.get(str(x), "Other")
            )
        )

        # Aggregate by sector
        portfolio_sectors = self._aggregate_by_sector(portfolio_df)
        benchmark_sectors = self._aggregate_by_sector(benchmark_df)

        # Perform attribution calculation
        attribution_results = {}
        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0

        # Get all sectors
        all_sectors = set(portfolio_sectors.index) | set(benchmark_sectors.index)

        for sector in all_sectors:
            # Portfolio weights and returns
            wp = (
                portfolio_sectors.loc[sector, "weight"]
                if sector in portfolio_sectors.index
                else 0.0
            )
            rp = (
                portfolio_sectors.loc[sector, "return"]
                if sector in portfolio_sectors.index
                else 0.0
            )

            # Benchmark weights and returns
            wb = (
                benchmark_sectors.loc[sector, "weight"]
                if sector in benchmark_sectors.index
                else 0.0
            )
            rb = (
                benchmark_sectors.loc[sector, "return"]
                if sector in benchmark_sectors.index
                else 0.0
            )

            # Calculate effects based on method
            if method == AttributionMethod.BRINSON_HOOD_BEEBOWER:
                # Allocation effect: (wp - wb) * rb
                allocation = (wp - wb) * rb

                # Selection effect: wb * (rp - rb)
                selection = wb * (rp - rb)

                # Interaction effect: (wp - wb) * (rp - rb)
                interaction = (wp - wb) * (rp - rb)

            else:  # Brinson-Fachler (no interaction term)
                allocation = (wp - wb) * rb
                selection = wp * (rp - rb)
                interaction = 0.0

            attribution_results[sector] = {
                "allocation": allocation,
                "selection": selection,
                "interaction": interaction,
                "total": allocation + selection + interaction,
            }

            total_allocation += allocation
            total_selection += selection
            total_interaction += interaction

        return AttributionResult(
            total_attribution=total_allocation + total_selection + total_interaction,
            allocation_effect=total_allocation,
            selection_effect=total_selection,
            interaction_effect=total_interaction,
            attribution_breakdown=attribution_results,
            period_start=datetime.now() - timedelta(days=30),  # Default period
            period_end=datetime.now(),
            attribution_type=AttributionType.SECTOR,
            method=method,
        )

    def factor_attribution(
        self,
        portfolio_holdings: List[Holding],
        factor_exposures: Dict[str, FactorExposure],
        factor_returns: Optional[Dict[str, float]] = None,
    ) -> AttributionResult:
        """
        Perform factor-based attribution analysis.

        Args:
            portfolio_holdings: List of portfolio holdings
            factor_exposures: Factor exposures for each security
            factor_returns: Factor returns for the period (optional, uses sample data)

        Returns:
            AttributionResult with factor attribution breakdown
        """
        if factor_returns is None:
            factor_returns = self.sample_factor_returns

        portfolio_df = self._holdings_to_dataframe(portfolio_holdings)

        # Calculate portfolio factor exposures
        portfolio_exposures = {}

        for factor in self.equity_factors:
            total_exposure = 0.0
            for _, holding in portfolio_df.iterrows():
                security = str(holding["security"])
                weight = holding["weight"]

                if security in factor_exposures:
                    exposure = factor_exposures[security].exposures.get(factor, 0.0)
                    total_exposure += weight * exposure
                else:
                    # Default exposures if not provided
                    default_exposures = self._get_default_factor_exposures(security)
                    exposure = default_exposures.get(factor, 0.0)
                    total_exposure += weight * exposure

            portfolio_exposures[factor] = total_exposure

        # Calculate factor attribution
        factor_attribution_breakdown = {}
        total_factor_return = 0.0

        for factor, exposure in portfolio_exposures.items():
            factor_return = factor_returns.get(factor, 0.0)
            factor_contribution = exposure * factor_return
            factor_attribution_breakdown[factor] = factor_contribution
            total_factor_return += factor_contribution

        # Calculate alpha (unexplained return)
        portfolio_return = sum(h.weight * h.return_period for h in portfolio_holdings)
        alpha = portfolio_return - total_factor_return
        factor_attribution_breakdown["alpha"] = alpha

        return AttributionResult(
            total_attribution=portfolio_return,
            allocation_effect=total_factor_return,
            selection_effect=alpha,
            interaction_effect=0.0,
            attribution_breakdown=factor_attribution_breakdown,
            period_start=datetime.now() - timedelta(days=30),
            period_end=datetime.now(),
            attribution_type=AttributionType.FACTOR,
            method=AttributionMethod.ARITHMETIC,
        )

    def style_attribution(
        self, portfolio_holdings: List[Holding], benchmark_holdings: List[Holding]
    ) -> AttributionResult:
        """
        Perform style-based attribution analysis.

        Args:
            portfolio_holdings: List of portfolio holdings
            benchmark_holdings: List of benchmark holdings

        Returns:
            AttributionResult with style attribution breakdown
        """
        portfolio_df = self._holdings_to_dataframe(portfolio_holdings)
        benchmark_df = self._holdings_to_dataframe(benchmark_holdings)

        # Calculate style exposures
        portfolio_style = self._calculate_style_exposures(portfolio_holdings)
        benchmark_style = self._calculate_style_exposures(benchmark_holdings)

        # Calculate style attribution
        style_attribution = {}
        total_attribution = 0.0

        for style_factor in self.style_factors:
            portfolio_exposure = portfolio_style.get(style_factor, 0.0)
            benchmark_exposure = benchmark_style.get(style_factor, 0.0)

            # Style factor return (simplified)
            factor_return = self.sample_factor_returns.get(style_factor, 0.0)

            # Attribution = (portfolio_exposure - benchmark_exposure) * factor_return
            attribution = (portfolio_exposure - benchmark_exposure) * factor_return
            style_attribution[style_factor] = attribution
            total_attribution += attribution

        # Calculate unexplained return
        portfolio_return = sum(h.weight * h.return_period for h in portfolio_holdings)
        benchmark_return = sum(h.weight * h.return_period for h in benchmark_holdings)

        unexplained = portfolio_return - benchmark_return - total_attribution
        style_attribution["alpha"] = unexplained

        return AttributionResult(
            total_attribution=portfolio_return - benchmark_return,
            allocation_effect=total_attribution,
            selection_effect=unexplained,
            interaction_effect=0.0,
            attribution_breakdown=style_attribution,
            period_start=datetime.now() - timedelta(days=30),
            period_end=datetime.now(),
            attribution_type=AttributionType.STYLE,
            method=AttributionMethod.ARITHMETIC,
        )

    def security_attribution(
        self, portfolio_holdings: List[Holding], benchmark_holdings: List[Holding]
    ) -> AttributionResult:
        """
        Perform security-level attribution analysis.

        Args:
            portfolio_holdings: List of portfolio holdings
            benchmark_holdings: List of benchmark holdings

        Returns:
            AttributionResult with security-level attribution breakdown
        """
        portfolio_df = self._holdings_to_dataframe(portfolio_holdings)
        benchmark_df = self._holdings_to_dataframe(benchmark_holdings)

        # Get all securities
        all_securities = set(portfolio_df["security"].astype(str)) | set(
            benchmark_df["security"].astype(str)
        )

        security_attribution = {}
        total_attribution = 0.0

        for security in all_securities:
            # Portfolio data
            portfolio_row = portfolio_df[
                portfolio_df["security"].astype(str) == security
            ]
            wp = portfolio_row["weight"].iloc[0] if len(portfolio_row) > 0 else 0.0
            rp = portfolio_row["return"].iloc[0] if len(portfolio_row) > 0 else 0.0

            # Benchmark data
            benchmark_row = benchmark_df[
                benchmark_df["security"].astype(str) == security
            ]
            wb = benchmark_row["weight"].iloc[0] if len(benchmark_row) > 0 else 0.0
            rb = benchmark_row["return"].iloc[0] if len(benchmark_row) > 0 else 0.0

            # Security attribution = wp * rp - wb * rb
            attribution = wp * rp - wb * rb
            security_attribution[security] = attribution
            total_attribution += attribution

        return AttributionResult(
            total_attribution=total_attribution,
            allocation_effect=0.0,  # Not applicable for security attribution
            selection_effect=total_attribution,
            interaction_effect=0.0,
            attribution_breakdown=security_attribution,
            period_start=datetime.now() - timedelta(days=30),
            period_end=datetime.now(),
            attribution_type=AttributionType.SECURITY,
            method=AttributionMethod.ARITHMETIC,
        )

    def multi_period_attribution(
        self,
        portfolio_history: List[List[Holding]],
        benchmark_history: List[List[Holding]],
        periods: List[datetime],
        attribution_type: AttributionType = AttributionType.SECTOR,
    ) -> List[AttributionResult]:
        """
        Perform attribution analysis across multiple periods.

        Args:
            portfolio_history: Portfolio holdings for each period
            benchmark_history: Benchmark holdings for each period
            periods: Date for each period
            attribution_type: Type of attribution to perform

        Returns:
            List of AttributionResult for each period
        """
        results = []

        for i, (portfolio_holdings, benchmark_holdings) in enumerate(
            zip(portfolio_history, benchmark_history)
        ):
            if attribution_type == AttributionType.SECTOR:
                result = self.brinson_attribution(
                    portfolio_holdings, benchmark_holdings
                )
            elif attribution_type == AttributionType.FACTOR:
                # Use empty factor exposures for simplicity
                result = self.factor_attribution(portfolio_holdings, {})
            elif attribution_type == AttributionType.STYLE:
                result = self.style_attribution(portfolio_holdings, benchmark_holdings)
            elif attribution_type == AttributionType.SECURITY:
                result = self.security_attribution(
                    portfolio_holdings, benchmark_holdings
                )

            # Update period dates
            if i < len(periods):
                result.period_start = (
                    periods[i] - timedelta(days=1)
                    if i > 0
                    else periods[i] - timedelta(days=30)
                )
                result.period_end = periods[i]

            results.append(result)

        return results

    def calculate_risk_attribution(
        self,
        portfolio_holdings: List[Holding],
        covariance_matrix: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Calculate risk attribution for the portfolio.

        Args:
            portfolio_holdings: List of portfolio holdings
            covariance_matrix: Asset covariance matrix (optional)

        Returns:
            Dictionary with risk attribution results
        """
        portfolio_df = self._holdings_to_dataframe(portfolio_holdings)

        # Create weights vector
        weights = portfolio_df["weight"].values
        securities = portfolio_df["security"].astype(str).values

        if covariance_matrix is None:
            # Generate sample covariance matrix
            n_assets = len(securities)
            covariance_matrix = self._generate_sample_covariance_matrix(n_assets)

        # Calculate portfolio variance
        portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
        portfolio_volatility = np.sqrt(portfolio_variance)

        # Calculate marginal contributions to risk
        marginal_contributions = (
            np.dot(covariance_matrix, weights) / portfolio_volatility
        )

        # Calculate component contributions to risk
        component_contributions = weights * marginal_contributions

        # Calculate percentage contributions
        percentage_contributions = component_contributions / portfolio_volatility

        risk_attribution = {
            "portfolio_volatility": portfolio_volatility,
            "portfolio_variance": portfolio_variance,
            "marginal_contributions": dict(zip(securities, marginal_contributions)),
            "component_contributions": dict(zip(securities, component_contributions)),
            "percentage_contributions": dict(zip(securities, percentage_contributions)),
            "diversification_ratio": np.sum(
                weights * np.sqrt(np.diag(covariance_matrix))
            )
            / portfolio_volatility,
        }

        return risk_attribution

    # Helper methods
    def _holdings_to_dataframe(self, holdings: List[Holding]) -> pd.DataFrame:
        """Convert holdings list to DataFrame."""
        data = []
        for holding in holdings:
            data.append(
                {
                    "security": holding.security,
                    "weight": holding.weight,
                    "return": holding.return_period,
                    "sector": holding.sector,
                }
            )
        return pd.DataFrame(data)

    def _aggregate_by_sector(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate holdings by sector."""
        sector_data = df.groupby("sector").agg(
            {
                "weight": "sum",
                "return": lambda x: np.average(x, weights=df.loc[x.index, "weight"]),
            }
        )
        return sector_data

    def _calculate_style_exposures(self, holdings: List[Holding]) -> Dict[str, float]:
        """Calculate portfolio style exposures."""
        style_exposures = {}

        for style_factor in self.style_factors:
            total_exposure = 0.0

            for holding in holdings:
                if holding.style_scores and style_factor in holding.style_scores:
                    exposure = holding.style_scores[style_factor]
                else:
                    # Default style exposures based on security type
                    exposure = self._get_default_style_exposure(
                        holding.security, style_factor
                    )

                total_exposure += holding.weight * exposure

            style_exposures[style_factor] = total_exposure

        return style_exposures

    def _get_default_factor_exposures(self, security: str) -> Dict[str, float]:
        """Get default factor exposures for a security."""
        # Simplified default exposures
        exposures = {
            "market": 1.0,  # Beta of 1
            "size": 0.0,  # Neutral size exposure
            "value": 0.0,  # Neutral value exposure
            "momentum": 0.0,
            "profitability": 0.0,
            "investment": 0.0,
        }

        # Adjust based on security type
        if any(crypto in security.upper() for crypto in ["BTC", "ETH", "BNB"]):
            exposures["market"] = 1.5  # Higher beta for crypto
            exposures["volatility"] = 1.0

        return exposures

    def _get_default_style_exposure(self, security: str, style_factor: str) -> float:
        """Get default style exposure for a security."""
        # Simplified style mapping
        style_map = {
            "value": 0.0,
            "growth": 0.0,
            "momentum": 0.0,
            "quality": 0.0,
            "volatility": 0.0,
            "size": 0.0,
        }

        security_str = str(security).upper()

        # Technology stocks tend to be growth
        if any(tech in security_str for tech in ["AAPL", "MSFT", "GOOGL"]):
            style_map["growth"] = 1.0
            style_map["quality"] = 0.8

        # Crypto tends to be high volatility, momentum
        if any(crypto in security_str for crypto in ["BTC", "ETH", "BNB"]):
            style_map["volatility"] = 1.5
            style_map["momentum"] = 0.5

        return style_map.get(style_factor, 0.0)

    def _generate_sample_covariance_matrix(self, n_assets: int) -> np.ndarray:
        """Generate a sample covariance matrix."""
        # Generate random correlation matrix
        np.random.seed(42)
        A = np.random.randn(n_assets, n_assets)
        correlation_matrix = np.dot(A, A.transpose())

        # Normalize to get valid correlation matrix
        d = np.sqrt(np.diag(correlation_matrix))
        correlation_matrix = correlation_matrix / np.outer(d, d)

        # Generate random volatilities
        volatilities = np.random.uniform(0.1, 0.5, n_assets)

        # Convert to covariance matrix
        covariance_matrix = np.outer(volatilities, volatilities) * correlation_matrix

        return covariance_matrix

    def generate_attribution_report(self, result: AttributionResult) -> str:
        """Generate a formatted attribution report."""
        report = []
        report.append("=" * 60)
        report.append(f"PERFORMANCE ATTRIBUTION REPORT")
        report.append("=" * 60)
        report.append(f"Attribution Type: {result.attribution_type.value.title()}")
        report.append(f"Method: {result.method.value.upper()}")
        report.append(
            f"Period: {result.period_start.strftime('%Y-%m-%d')} to {result.period_end.strftime('%Y-%m-%d')}"
        )
        report.append("")

        report.append("SUMMARY:")
        report.append("-" * 30)
        report.append(
            f"Total Attribution: {result.total_attribution:.4f} ({result.total_attribution*100:.2f}%)"
        )
        report.append(
            f"Allocation Effect: {result.allocation_effect:.4f} ({result.allocation_effect*100:.2f}%)"
        )
        report.append(
            f"Selection Effect: {result.selection_effect:.4f} ({result.selection_effect*100:.2f}%)"
        )
        if result.interaction_effect != 0:
            report.append(
                f"Interaction Effect: {result.interaction_effect:.4f} ({result.interaction_effect*100:.2f}%)"
            )
        report.append("")

        report.append("DETAILED BREAKDOWN:")
        report.append("-" * 30)

        # Sort by absolute contribution
        sorted_items = sorted(
            result.attribution_breakdown.items(),
            key=lambda x: (
                abs(x[1])
                if isinstance(x[1], (int, float))
                else abs(x[1].get("total", 0))
            ),
            reverse=True,
        )

        for item, contribution in sorted_items:
            if isinstance(contribution, dict):
                # Brinson-style breakdown
                total = contribution.get("total", 0)
                allocation = contribution.get("allocation", 0)
                selection = contribution.get("selection", 0)
                interaction = contribution.get("interaction", 0)

                report.append(f"{item:20} | Total: {total:8.4f} ({total*100:6.2f}%)")
                report.append(
                    f"{'':20} | Alloc: {allocation:8.4f} | Select: {selection:8.4f} | Inter: {interaction:8.4f}"
                )
            else:
                # Simple contribution
                report.append(
                    f"{item:20} | {contribution:8.4f} ({contribution*100:6.2f}%)"
                )

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)


# Example usage and testing
def create_sample_portfolio() -> List[Holding]:
    """Create sample portfolio for testing."""
    return [
        Holding("AAPL", 0.20, 0.15, "Technology"),
        Holding("MSFT", 0.15, 0.12, "Technology"),
        Holding("JPM", 0.10, 0.08, "Financials"),
        Holding("XOM", 0.10, 0.06, "Energy"),
        Holding("JNJ", 0.10, 0.09, "Healthcare"),
        Holding("BTC", 0.15, 0.25, "Cryptocurrency"),
        Holding("ETH", 0.10, 0.20, "Cryptocurrency"),
        Holding("TSLA", 0.10, 0.18, "Consumer Discretionary"),
    ]


def create_sample_benchmark() -> List[Holding]:
    """Create sample benchmark for testing."""
    return [
        Holding("AAPL", 0.25, 0.12, "Technology"),
        Holding("MSFT", 0.20, 0.10, "Technology"),
        Holding("JPM", 0.15, 0.07, "Financials"),
        Holding("XOM", 0.15, 0.05, "Energy"),
        Holding("JNJ", 0.15, 0.08, "Healthcare"),
        Holding("TSLA", 0.10, 0.15, "Consumer Discretionary"),
    ]


if __name__ == "__main__":
    # Example usage
    engine = PerformanceAttributionEngine()

    # Create sample data
    portfolio = create_sample_portfolio()
    benchmark = create_sample_benchmark()

    # Run different types of attribution
    print("Testing Performance Attribution Engine...")

    # Sector attribution
    sector_result = engine.brinson_attribution(portfolio, benchmark)
    print("\n" + engine.generate_attribution_report(sector_result))

    # Factor attribution
    factor_result = engine.factor_attribution(portfolio, {})
    print("\n" + engine.generate_attribution_report(factor_result))

    # Style attribution
    style_result = engine.style_attribution(portfolio, benchmark)
    print("\n" + engine.generate_attribution_report(style_result))

    # Risk attribution
    risk_attribution = engine.calculate_risk_attribution(portfolio)
    print(f"\nRisk Attribution:")
    print(f"Portfolio Volatility: {risk_attribution['portfolio_volatility']:.4f}")
    print(f"Diversification Ratio: {risk_attribution['diversification_ratio']:.4f}")

    print("\nPerformance Attribution Engine test completed successfully!")
