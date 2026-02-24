# Backtesting Framework - PowerTrader AI

The PowerTrader Backtesting Framework provides comprehensive strategy testing, Monte Carlo simulation, and parameter optimization capabilities for quantitative trading analysis.

## Features

### Core Backtesting Engine
- **Historical Strategy Testing**: Simulate trading strategies against historical price data
- **Performance Metrics**: Calculate comprehensive statistics including:
  - Total and annualized returns
  - Sharpe ratio, Calmar ratio
  - Maximum drawdown analysis
  - Win rate and profit factor
  - Alpha and beta vs benchmark
  - Trade-level statistics

### Advanced Analytics
- **Monte Carlo Simulation**: Run thousands of simulations with randomized data
- **Parameter Optimization**: Grid search for optimal strategy parameters
- **Risk Analysis**: Detailed drawdown and volatility analysis
- **Statistical Testing**: Confidence intervals and probability distributions

### Interactive GUI Interface
- **4-Tab Design**: Data/Strategy, Results, Optimization, Monte Carlo
- **Strategy Builder**: Built-in MA Cross and RSI strategies with parameter controls
- **Visual Analytics**: Equity curves, drawdown charts, monthly returns heatmaps
- **Results Export**: Detailed performance reports and trade history

## Included Trading Strategies

### Moving Average Crossover
- **Logic**: Buy when fast MA crosses above slow MA, sell when below
- **Parameters**:
  - Short Window: Fast moving average period (default: 20)
  - Long Window: Slow moving average period (default: 50)
- **Best For**: Trending markets, longer timeframes

### RSI Mean Reversion
- **Logic**: Buy when RSI exits oversold, sell when RSI exits overbought
- **Parameters**:
  - RSI Period: Period for RSI calculation (default: 14)
  - Oversold Level: RSI threshold for oversold condition (default: 30)
  - Overbought Level: RSI threshold for overbought condition (default: 70)
- **Best For**: Range-bound markets, mean reversion opportunities

## Getting Started

### 1. Data Requirements
The backtesting engine expects OHLCV (Open, High, Low, Close, Volume) data in CSV or Excel format with:
- Date index (properly parsed)
- Columns: 'open', 'high', 'low', 'close', 'volume'

Example CSV structure:
```csv
date,open,high,low,close,volume
2023-01-01,100.0,102.0,99.5,101.5,1000
2023-01-02,101.5,103.0,101.0,102.8,1200
...
```

### 2. Quick Start Guide

1. **Load Data**:
   - Click "Browse" to load your historical data file
   - Or use "Load Sample" for demonstration data

2. **Configure Strategy**:
   - Select strategy type (MA Cross or RSI)
   - Adjust parameters as needed
   - Set initial capital and commission rates

3. **Run Backtest**:
   - Click "Run Backtest" for full analysis
   - Or "Quick Test" for sample data demo

4. **Analyze Results**:
   - Review performance metrics in the Results tab
   - Examine individual trades
   - View equity curve and drawdown charts

### 3. Advanced Features

#### Parameter Optimization
1. Go to the "Optimization" tab
2. Define parameter ranges (min, max, step)
3. Select optimization metric (Sharpe ratio, return, Calmar ratio)
4. Run optimization to find best parameters

#### Monte Carlo Analysis
1. Go to the "Monte Carlo" tab
2. Set number of simulations (100-1000+)
3. Set confidence level (90%, 95%, 99%)
4. Run simulation for risk assessment

## Dependencies

### Core Dependencies (Included)
- `datetime`, `typing` - Built-in Python modules
- Core functionality works without external packages

### Enhanced Features (Optional)
Install for full functionality:
```bash
python app/install_optional_deps.py
```

**Enhanced packages include**:
- `pandas >= 1.5.0` - Data manipulation and analysis
- `numpy >= 1.21.0` - Numerical computations
- `scipy >= 1.9.0` - Statistical functions and optimization
- `matplotlib >= 3.5.0` - Plotting and visualization
- `seaborn >= 0.11.0` - Statistical visualization

### Graceful Degradation
The framework provides graceful degradation when optional packages are missing:
- Basic backtesting works with core Python
- Enhanced analytics require pandas/numpy
- Visualizations require matplotlib/seaborn
- Optimization requires scipy

## Architecture

### Class Structure

```python
# Core Engine
class BacktestEngine:
    - run_backtest()
    - monte_carlo_simulation()
    - parameter_optimization()

# Strategy Base Class
class TradingStrategy:
    - generate_signals()
    - should_buy()
    - should_sell()

# Built-in Strategies
class MovingAverageCrossStrategy(TradingStrategy)
class RSIStrategy(TradingStrategy)

# GUI Interface
class BacktestingGUI:
    - 4-tab interface
    - Interactive controls
    - Results visualization
```

### Data Flow
1. **Input**: Historical OHLCV data
2. **Strategy**: Generate buy/sell signals
3. **Simulation**: Execute trades with commission
4. **Analysis**: Calculate performance metrics
5. **Output**: Results, charts, statistics

## Performance Metrics

### Return Metrics
- **Total Return**: (Final Value - Initial Value) / Initial Value
- **Annualized Return**: Total return adjusted for time period
- **Alpha**: Excess return vs benchmark
- **Beta**: Correlation with benchmark

### Risk Metrics
- **Volatility**: Standard deviation of returns
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted return (return/volatility)
- **Calmar Ratio**: Return/max drawdown ratio

### Trade Metrics
- **Total Trades**: Number of round-trip trades
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profit / gross loss
- **Average Trade**: Mean profit/loss per trade

## File Structure

```
app/
├── backtesting_engine.py      # Core backtesting engine
├── backtesting_gui.py         # Interactive GUI interface
├── pt_hub.py                  # Integration with PowerTrader Hub
└── install_optional_deps.py   # Dependency installer
```

## Integration with PowerTrader

The Backtesting Framework is fully integrated with PowerTrader Hub as **Tab 11**:
- Automatic dependency detection
- Graceful fallback for missing packages
- Consistent UI theme with PowerTrader
- Error handling and user feedback

## Example Usage

### Programmatic Usage
```python
from backtesting_engine import BacktestEngine, MovingAverageCrossStrategy
import pandas as pd

# Load data
data = pd.read_csv('historical_data.csv', index_col=0, parse_dates=True)

# Create strategy
strategy = MovingAverageCrossStrategy(short_window=20, long_window=50)

# Run backtest
engine = BacktestEngine(initial_capital=100000, commission=0.001)
results = engine.run_backtest(data, strategy)

# Display results
print(f"Total Return: {results.metrics['total_return']:.2%}")
print(f"Sharpe Ratio: {results.metrics['sharpe_ratio']:.3f}")
print(f"Max Drawdown: {results.metrics['max_drawdown']:.2%}")
```

### GUI Usage
```python
from backtesting_gui import BacktestingGUI
import tkinter as tk

# Create GUI
root = tk.Tk()
app = BacktestingGUI(root)
root.mainloop()
```

## Best Practices

### Data Quality
- Ensure clean, consistent historical data
- Handle missing values appropriately
- Use adequate sample size for statistical significance

### Strategy Development
- Start with simple strategies
- Test on out-of-sample data
- Consider transaction costs and slippage
- Validate results across different market conditions

### Risk Management
- Use position sizing rules
- Implement stop-loss mechanisms
- Consider correlation between strategies
- Monitor drawdowns and volatility

## Troubleshooting

### Common Issues

1. **Import Errors**:
   - Install optional dependencies: `python app/install_optional_deps.py`
   - Check Python version compatibility (3.8+)

2. **Data Format Issues**:
   - Ensure CSV has correct column names
   - Check date index is properly parsed
   - Verify no missing or invalid values

3. **Memory Issues**:
   - Reduce Monte Carlo simulation count
   - Use smaller parameter grids for optimization
   - Process data in smaller chunks

4. **Performance Issues**:
   - Optimize strategy code
   - Reduce data frequency if possible
   - Use vectorized operations where applicable

## Contributing

To add new trading strategies:

1. Inherit from `TradingStrategy` base class
2. Implement required methods:
   - `generate_signals()`
   - `should_buy()`
   - `should_sell()`
3. Add to GUI strategy selection
4. Update documentation

Example:
```python
class CustomStrategy(TradingStrategy):
    def __init__(self, param1, param2):
        super().__init__()
        self.param1 = param1
        self.param2 = param2

    def generate_signals(self, data):
        # Your signal logic here
        pass
```

## Support

For issues, questions, or feature requests:
1. Check this documentation first
2. Review console output for error messages
3. Ensure all dependencies are installed
4. Test with sample data to isolate issues

The Backtesting Framework provides a solid foundation for quantitative trading strategy development and validation within the PowerTrader ecosystem.
