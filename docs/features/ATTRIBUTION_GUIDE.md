# Performance Attribution Engine - PowerTrader AI

The PowerTrader Performance Attribution Engine provides comprehensive analysis of portfolio performance sources through advanced attribution methodologies, factor decomposition, and risk analysis.

## Overview

Performance attribution is the process of measuring the sources of a portfolio's performance relative to a benchmark. This engine implements multiple attribution methodologies to help investors understand what drove their portfolio returns and identify areas for improvement.

## Core Attribution Methods

### 1. Brinson Attribution (Sector-Based)
Decomposes performance into allocation, selection, and interaction effects:

- **Allocation Effect**: Performance due to sector weight differences vs benchmark
- **Selection Effect**: Performance due to security selection within sectors
- **Interaction Effect**: Combined effect of allocation and selection decisions

#### Available Methods:
- **Brinson-Hood-Beebower**: Includes interaction term
- **Brinson-Fachler**: No interaction term (used for cleaner decomposition)

### 2. Factor-Based Attribution
Attributes performance to systematic factor exposures:

- **Market Factor**: Beta exposure to overall market movements
- **Size Factor**: Exposure to small-cap vs large-cap stocks
- **Value Factor**: Exposure to value vs growth characteristics
- **Momentum Factor**: Exposure to price momentum
- **Quality Factor**: Exposure to profitability and quality metrics
- **Alpha**: Unexplained return (manager skill)

### 3. Style Attribution
Analyzes performance through style exposures:

- **Growth vs Value**: Attribution to growth/value style bias
- **Size Bias**: Attribution to market cap preferences
- **Quality Bias**: Attribution to quality factor exposure
- **Volatility Bias**: Attribution to volatility preferences

### 4. Risk Attribution
Decomposes portfolio risk into component contributions:

- **Marginal Risk Contribution**: Risk contribution per unit increase
- **Component Risk Contribution**: Total risk contribution
- **Percentage Risk Contribution**: Percentage of total risk
- **Diversification Ratio**: Measure of diversification benefit

## Key Features

### Interactive GUI Interface
- **5-Tab Design**: Data Input, Sector Attribution, Factor Attribution, Risk Attribution, Reports
- **Real-time Analysis**: Immediate results with interactive controls
- **Visual Analytics**: Charts and plots for attribution breakdown
- **Export Functionality**: Generate and export comprehensive reports

### Flexible Data Input
- **File Import**: CSV/Excel format support for portfolio and benchmark data
- **Manual Entry**: Add/edit individual holdings
- **Sample Data**: Built-in test data for demonstration
- **Format Detection**: Automatic column mapping

### Comprehensive Reporting
- **Multi-Method Analysis**: Compare different attribution approaches
- **Detailed Breakdowns**: Security and sector level analysis
- **Performance Metrics**: Risk-adjusted and absolute measures
- **Export Options**: Text and formatted report generation

## Data Requirements

### Portfolio Holdings Format
Required fields for portfolio analysis:

```csv
security,weight,return,sector
AAPL,0.20,0.15,Technology
MSFT,0.15,0.12,Technology
JPM,0.10,0.08,Financials
...
```

### Field Descriptions:
- **security**: Security identifier (ticker, name, or ID)
- **weight**: Portfolio weight (decimal, sum should equal 1.0)
- **return**: Period return (decimal, e.g., 0.15 for 15%)
- **sector**: Sector classification (optional but recommended)

### Benchmark Data
Same format as portfolio holdings, representing the benchmark composition and returns.

## Attribution Calculations

### Brinson-Hood-Beebower Method

For each sector i:

```
Allocation Effect = (wp_i - wb_i) × rb_i
Selection Effect = wb_i × (rp_i - rb_i)
Interaction Effect = (wp_i - wb_i) × (rp_i - rb_i)
```

Where:
- wp_i = Portfolio weight in sector i
- wb_i = Benchmark weight in sector i
- rp_i = Portfolio return in sector i
- rb_i = Benchmark return in sector i

### Factor Attribution Model

```
Portfolio Return = α + Σ(β_f × Factor_Return_f) + ε
```

Where:
- α = Alpha (manager skill)
- β_f = Factor exposure/loading
- Factor_Return_f = Factor return for period
- ε = Residual error

### Risk Attribution

Component risk contribution for asset i:

```
Risk_Contribution_i = Weight_i × (Σ(Covariance_ij × Weight_j)) / Portfolio_Volatility
```

## Performance Metrics

### Return Metrics
- **Total Attribution**: Sum of all attribution effects
- **Allocation Effect**: Performance from asset allocation decisions
- **Selection Effect**: Performance from security selection
- **Alpha**: Risk-adjusted excess return

### Risk Metrics
- **Portfolio Volatility**: Standard deviation of returns
- **Diversification Ratio**: Portfolio volatility vs weighted average volatility
- **Risk Contributions**: Individual security risk contributions
- **Marginal Risk**: Risk change per unit weight increase

## Getting Started

### 1. Basic Sector Attribution
```python
from performance_attribution import PerformanceAttributionEngine, Holding

# Create engine
engine = PerformanceAttributionEngine()

# Define portfolio holdings
portfolio = [
    Holding('AAPL', 0.30, 0.15, 'Technology'),
    Holding('JPM', 0.20, 0.08, 'Financials'),
    # ... more holdings
]

# Define benchmark
benchmark = [
    Holding('AAPL', 0.25, 0.12, 'Technology'),
    Holding('JPM', 0.25, 0.07, 'Financials'),
    # ... more holdings
]

# Run attribution
result = engine.brinson_attribution(portfolio, benchmark)

# Display results
print(f"Total Attribution: {result.total_attribution:.4f}")
print(f"Allocation Effect: {result.allocation_effect:.4f}")
print(f"Selection Effect: {result.selection_effect:.4f}")
```

### 2. Factor Attribution Analysis
```python
# Run factor attribution
factor_result = engine.factor_attribution(portfolio, {})

# Display factor contributions
for factor, contribution in factor_result.attribution_breakdown.items():
    print(f"{factor}: {contribution:.4f}")
```

### 3. GUI Application
```python
from performance_attribution_gui import PerformanceAttributionGUI
import tkinter as tk

# Launch GUI
root = tk.Tk()
app = PerformanceAttributionGUI(root)
root.mainloop()
```

## Integration with PowerTrader

The Performance Attribution Engine is fully integrated with PowerTrader Hub as **Tab 12**:

### Features:
- Automatic dependency detection and graceful degradation
- Consistent dark theme with PowerTrader interface
- Real-time analysis with portfolio data
- Export integration with PowerTrader reporting

### Access:
1. Open PowerTrader Hub (`python app/pt_hub.py`)
2. Navigate to "Performance Attribution" tab
3. Load portfolio and benchmark data
4. Run attribution analyses
5. Export results and reports

## Dependencies

### Core Dependencies (Included)
- `numpy` - Numerical computations
- `pandas` - Data manipulation
- `datetime`, `typing` - Built-in Python modules
- Basic functionality works without external packages

### Enhanced Features (Optional)
Install for full functionality:
```bash
python app/install_optional_deps.py
```

**Enhanced packages**:
- `scipy >= 1.9.0` - Advanced statistical functions
- `matplotlib >= 3.5.0` - Charts and visualization
- `seaborn >= 0.11.0` - Statistical plotting
- `scikit-learn >= 1.0.0` - Machine learning utilities (optional)

### Graceful Degradation
The engine provides graceful degradation when optional packages are missing:
- Basic attribution works with core Python/numpy
- Enhanced analytics require scipy
- Visualizations require matplotlib/seaborn
- Statistical analysis may be limited without scipy

## Algorithm Details

### Sector Weight Aggregation
For portfolio holdings in the same sector:

```python
sector_weight = Σ(individual_weights)
sector_return = Σ(individual_weights × individual_returns) / sector_weight
```

### Factor Exposure Calculation
Default factor exposures are estimated based on:
- **Technology stocks**: High growth exposure, positive quality
- **Financial stocks**: High value exposure, market beta
- **Cryptocurrency**: High volatility, momentum exposure
- **Small caps**: Positive size factor exposure

### Risk Decomposition
Portfolio variance decomposition:

```
σ²_portfolio = Σ Σ (w_i × w_j × σ_ij)
```

Where σ_ij is the covariance between assets i and j.

## Example Use Cases

### 1. Monthly Portfolio Review
- Load month-end portfolio vs benchmark
- Run Brinson attribution to identify allocation vs selection
- Analyze sector over/under weights and their impact
- Generate report for investment committee

### 2. Factor Exposure Analysis
- Input quarterly portfolio holdings
- Run factor attribution against common factors
- Identify unintended factor bets
- Adjust portfolio to target factor exposures

### 3. Risk Attribution Study
- Analyze current portfolio risk sources
- Identify concentrated risk positions
- Calculate marginal risk contributions
- Optimize portfolio for better diversification

### 4. Multi-Period Attribution
- Run attribution across multiple periods
- Track consistency of allocation and selection effects
- Identify persistent sources of alpha or risk
- Generate performance attribution history

## Advanced Features

### Custom Factor Models
The engine supports custom factor definitions:

```python
# Define custom factors
custom_factors = {
    'momentum_12m': 0.05,    # 12-month momentum return
    'volatility': -0.02,     # Low volatility premium
    'dividend_yield': 0.03   # Dividend factor return
}

# Run attribution with custom factors
result = engine.factor_attribution(portfolio, {}, custom_factors)
```

### Multi-Currency Attribution
For international portfolios:

```python
# Currency effects can be separated
# Portfolio return = Local return + Currency return + Interaction
currency_effect = engine.calculate_currency_attribution(portfolio, benchmark)
```

### Time-Series Attribution
Analyze attribution across time:

```python
# Multi-period analysis
periods = [date1, date2, date3]
portfolio_history = [portfolio1, portfolio2, portfolio3]
benchmark_history = [benchmark1, benchmark2, benchmark3]

results = engine.multi_period_attribution(
    portfolio_history,
    benchmark_history,
    periods
)
```

## Troubleshooting

### Common Issues

1. **Weight Mismatch**:
   ```
   Error: Portfolio weights don't sum to 1.0
   Solution: Normalize weights or check for missing positions
   ```

2. **Sector Classification**:
   ```
   Warning: Some securities lack sector classification
   Solution: Add sector data or use default "Other" category
   ```

3. **Return Period Mismatch**:
   ```
   Error: Inconsistent return periods
   Solution: Ensure all returns are for the same time period
   ```

4. **Memory Issues with Large Portfolios**:
   ```
   Solution: Process in smaller batches or reduce factor complexity
   ```

### Data Validation
The engine performs automatic validation:

- Weight normalization checking
- Return reasonableness tests
- Sector classification consistency
- Date alignment verification

### Performance Optimization
For large portfolios:

- Use vectorized operations where possible
- Cache factor exposures for repeated analyses
- Implement parallel processing for multi-period attribution
- Consider sampling for very large universes

## Research and Development

### Planned Enhancements
1. **Machine Learning Attribution**: Use ML to identify non-linear attribution patterns
2. **ESG Attribution**: Integrate ESG factors into attribution analysis
3. **Alternative Assets**: Support for real estate, commodities, private equity
4. **Real-time Attribution**: Live attribution with streaming data

### Academic References
- Brinson, G.P., Hood, L.R., and Beebower, G.L. (1986)
- Fama, E.F. and French, K.R. (1993, 2015, 2018)
- Carhart, M.M. (1997) four-factor model
- Bacon, C. (2019) Practical Portfolio Performance Measurement

## Support and Contributing

### Getting Help
1. Check this documentation for common questions
2. Review sample code and examples
3. Examine console output for detailed error messages
4. Test with provided sample data to isolate issues

### Contributing New Features
To add new attribution methods:

1. Implement method in `PerformanceAttributionEngine` class
2. Add GUI controls in `PerformanceAttributionGUI`
3. Update documentation and tests
4. Submit code with examples and validation

### Code Structure
```
app/
├── performance_attribution.py      # Core attribution engine
├── performance_attribution_gui.py  # Interactive GUI interface
├── pt_hub.py                      # PowerTrader integration
└── ATTRIBUTION_GUIDE.md           # This documentation
```

## Best Practices

### Data Quality
- Ensure clean, consistent historical data
- Validate sector classifications
- Check weight normalization
- Handle corporate actions appropriately

### Attribution Analysis
- Use appropriate benchmark for comparison
- Consider attribution period frequency
- Account for transaction costs and fees
- Validate results with alternative methods

### Interpretation
- Focus on statistically significant effects
- Consider attribution persistence over time
- Account for market regime changes
- Combine with qualitative analysis

The Performance Attribution Engine provides a comprehensive foundation for understanding portfolio performance sources and making informed investment decisions within the PowerTrader ecosystem.
