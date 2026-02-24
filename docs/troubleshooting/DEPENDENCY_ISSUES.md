# PowerTrader Dependency Troubleshooting Guide

This guide helps resolve common dependency-related issues in PowerTrader.

## Quick Dependency Fix

If you're experiencing dependency issues, run the automated installer:

```bash
# Navigate to PowerTrader directory
cd PowerTraderAI

# Run the dependency installer
python app/install_optional_deps.py
```

## Common Issues and Solutions

### 1. "Real-time Market Data Fails to Load"

**Symptoms**:
- Market data tab shows error messages
- Missing WebSocket or CCXT functionality
- Import errors related to `websocket` or `ccxt`

**Solution**:
```bash
# Install real-time market data dependencies
python app/install_optional_deps.py
# Choose option 2 for "Real-time Market Data packages only"
```

**Manual Installation**:
```bash
pip install websocket-client ccxt
```

### 2. "Module Not Found" Errors

**Symptoms**:
- `ModuleNotFoundError: No module named 'websocket'`
- `ModuleNotFoundError: No module named 'ccxt'`
- `ModuleNotFoundError: No module named 'scipy'`

**Solution**:
```bash
# Check what's missing
python test_dependencies.py

# Install all missing packages
python app/install_optional_deps.py
```

### 3. Charts and Visualization Issues

**Symptoms**:
- Basic charts work but advanced statistical plots fail
- Missing seaborn functionality

**Solution**:
```bash
pip install seaborn
```

### 4. AI Research Features Not Available

**Symptoms**:
- LLM research tab shows limited functionality
- OpenAI API features missing

**Solution**:
```bash
pip install openai
```

## Dependency Categories Explained

### Core Dependencies (Always Required)
These are installed with `pip install -r requirements.txt`:
- `tkinter` - GUI framework
- `matplotlib` - Basic charting
- `pandas` - Data analysis
- `numpy` - Numerical computing
- `requests` - HTTP client
- `cryptography` - Security

### Optional Dependencies (Enhanced Features)

#### Real-time Market Data
- **websocket-client**: Live market data streams
- **ccxt**: Multi-exchange cryptocurrency library (100+ exchanges)
- **Impact**: Without these, market data tab shows installation instructions

#### Advanced Analytics
- **scipy**: Scientific computing and advanced statistics
- **Impact**: Enhanced risk calculations and statistical analysis

#### Charts & Visualization
- **seaborn**: Beautiful statistical plots
- **Impact**: Advanced charting features and statistical visualizations

#### AI Research
- **openai**: AI-powered market analysis
- **Impact**: LLM research capabilities and AI market insights

## Graceful Degradation

PowerTrader is designed to work even with missing optional dependencies:

1. **Core Functionality**: Always available with base requirements
2. **Feature Detection**: System automatically detects available packages
3. **Helpful Messages**: Clear instructions when enhanced features are requested
4. **No Crashes**: Missing packages never cause application crashes

## Testing Your Installation

### Quick Test
```bash
python test_dependencies.py
```

### Detailed Testing
```bash
# Test specific modules
python -c "from app.real_time_market_data import MarketDataAggregator; print('Market data OK')"
python -c "import scipy; print('Advanced analytics OK')"
python -c "import seaborn; print('Advanced charts OK')"
python -c "import openai; print('AI research OK')"
```

## Installation Verification

After installing dependencies, verify everything works:

```bash
# 1. Test dependencies
python test_dependencies.py

# 2. Launch PowerTrader
python app/pt_hub.py

# 3. Check all tabs load correctly
# - All 9 tabs should be visible
# - Market data tab should show real functionality (not error messages)
# - No import errors in console
```

## Advanced Troubleshooting

### Virtual Environment Issues

If dependencies seem installed but aren't recognized:

```bash
# Check which Python you're using
python --version
which python  # On Windows: where python

# Verify package installation
pip list | grep websocket
pip list | grep ccxt
```

### Permission Issues

On some systems, you may need elevated permissions:

```bash
# Windows (run as Administrator)
pip install --user websocket-client ccxt scipy seaborn openai

# Or use the installer with elevated permissions
python app/install_optional_deps.py
```

### Network/Proxy Issues

If installation fails due to network issues:

```bash
# Try with different index
pip install --index-url https://pypi.org/simple/ websocket-client

# Use proxy if needed
pip install --proxy http://user:pass@proxy.server:port websocket-client
```

### Version Conflicts

If you encounter version conflicts:

```bash
# Check for conflicts
pip check

# Upgrade conflicting packages
pip install --upgrade websocket-client ccxt scipy seaborn openai
```

## Getting Help

If you continue experiencing issues:

1. **Run diagnostics**: `python test_dependencies.py` and share the output
2. **Check logs**: Look for error messages in the console when running PowerTrader
3. **Create issue**: [GitHub Issues](https://github.com/sjackson0109/PowerTraderAI/issues) with:
   - Your operating system
   - Python version (`python --version`)
   - Output of `pip list`
   - Complete error messages

## Prevention

To avoid dependency issues in the future:

1. **Use virtual environments** for isolation
2. **Keep dependencies updated**: Periodically run `pip install --upgrade -r requirements.txt`
3. **Test after updates**: Run `python test_dependencies.py` after any changes
4. **Follow installation guide**: Always use the official installation instructions

Remember: PowerTrader is designed to work gracefully even with missing optional dependencies, so core functionality should always be available.
