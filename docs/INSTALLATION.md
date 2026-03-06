# PowerTrader AI+ Installation Guide

Complete installation documentation for PowerTrader AI+ Enterprise Trading Platform.

## Prerequisites

### System Requirements

**Minimum Requirements:**
- **CPU**: Dual-core processor (Intel Core i3 or AMD equivalent)
- **RAM**: 8GB system memory
- **Storage**: 2GB free disk space
- **OS**: Windows 10/11, macOS 10.15+, or Ubuntu 18.04+
- **Network**: Broadband internet connection

**Recommended Requirements:**
- **CPU**: Quad-core processor (Intel Core i5/AMD Ryzen 5 or better)
- **RAM**: 16GB system memory (for large portfolios and multiple exchanges)
- **Storage**: 5GB free disk space (including data and logs)
- **Display**: 1920x1080 minimum resolution for optimal GUI experience
- **Network**: Stable broadband with low latency for real-time trading

### Software Prerequisites

1. **Python 3.11 or Higher** (Python 3.13 recommended)
   - Download from: https://python.org/downloads/
   - **CRITICAL**: Check "Add Python to PATH" during installation
   - Verify installation: `python --version`

2. **Git Version Control**
   - Windows: https://git-scm.com/download/win
   - macOS: `xcode-select --install` or via Homebrew
   - Linux: `sudo apt install git` (Ubuntu/Debian)

3. **Virtual Environment Support** (Built into Python 3.3+)
   - No additional installation required
   - Used for dependency isolation

## Installation Methods

### Method 1: Automated Installation (Recommended)

**For all users - simplest and most reliable:**

```bash
# Step 1: Clone repository
git clone <repository-url>
cd PowerTrader_AI

# Step 2: Create virtual environment (ESSENTIAL)
python -m venv .venv

# Step 3: Activate virtual environment
# Windows Command Prompt:
.venv\Scripts\activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# Step 4: Install all dependencies automatically
python install_dependencies.py

# Step 5: Launch PowerTrader AI+
cd app
python pt_hub.py
```

### Method 2: Manual Installation

**For users who prefer manual control:**

```bash
# Steps 1-3: Same as Method 1

# Step 4: Manual dependency installation
pip install --upgrade pip
pip install -r requirements.txt --no-warn-script-location --upgrade

# Step 5: Verify installation
python -c "import flask, openai, ccxt, matplotlib, pandas; print('All dependencies installed successfully!')"

# Step 6: Launch application
cd app
python pt_hub.py
```

### Method 3: One-Command Installation

**For experienced developers:**

```bash
git clone <repository-url> && cd PowerTrader_AI && python -m venv .venv && .venv\Scripts\activate && python install_dependencies.py && echo "Ready to run: cd app && python pt_hub.py"
```

## Installation Verification

### Quick System Check

Run these commands to verify your installation:

```bash
# 1. Verify Python version
python --version
# Expected: Python 3.11.x or higher

# 2. Check virtual environment status
python -c "import sys; print('✓ Virtual environment active' if hasattr(sys, 'real_prefix') or sys.base_prefix != sys.prefix else '✗ No virtual environment detected')"

# 3. Test core dependencies
python -c "
try:
    import flask, openai, ccxt, matplotlib, pandas, numpy, websockets, beautifulsoup4
    print('✓ All core dependencies available')
except ImportError as e:
    print(f'✗ Missing dependency: {e}')
"

# 4. Test PowerTrader modules
cd app
python -c "
try:
    from pt_hub import PowerTraderHub
    print('✓ PowerTrader Hub can be imported successfully')
except Exception as e:
    print(f'✗ PowerTrader import error: {e}')
"
```

### Expected Success Output

When installation is successful, you should see:

```
PowerTrader AI+ Dependency Installer
==================================================
Virtual environment detected

Installing dependencies...
   This process is completely automated and warning-free
All dependencies installed successfully!

Verifying installation...
  [OK] Flask web framework
  [OK] OpenAI API client
  [OK] Exchange integration
  [OK] Web scraping

PowerTrader AI+ is ready to run!

Next steps:
   1. cd app
   2. python pt_hub.py
```

## Troubleshooting Common Issues

### Issue 1: Python Not Found

**Error**: `'python' is not recognized as an internal or external command`

**Solutions**:
```bash
# Check if Python is installed
python --version
# or try:
python3 --version
py --version  # Windows Python Launcher

# If not found, reinstall Python with PATH option
# Download from python.org and check "Add Python to PATH"

# Temporary fix - use full path:
C:\Python313\python.exe install_dependencies.py
```

### Issue 2: Virtual Environment Issues

**Error**: `ModuleNotFoundError` after installation

**Solution**:
```bash
# Ensure virtual environment is active
# You should see (.venv) in your command prompt

# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Verify activation:
python -c "import sys; print('Virtual env path:', sys.prefix)"
```

### Issue 3: Dependency Installation Fails

**Error**: Various pip installation errors

**Solutions**:
```bash
# Update pip first
python -m pip install --upgrade pip

# Clear pip cache
python -m pip cache purge

# Use alternative installation method
pip install -r requirements.txt --no-cache-dir --force-reinstall

# For permission issues on Windows:
pip install -r requirements.txt --user
```

### Issue 4: Network/Proxy Issues

**Error**: SSL or connection errors during installation

**Solutions**:
```bash
# For corporate networks with proxies
pip install -r requirements.txt --proxy http://proxy.company.com:8080

# For SSL certificate issues
pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org

# Alternative package index
pip install -r requirements.txt -i https://pypi.python.org/simple/
```

### Issue 5: Application Won't Start

**Error**: PowerTrader GUI doesn't launch

**Diagnostic Steps**:
```bash
# 1. Check for Python errors
cd app
python pt_hub.py
# Look for specific error messages

# 2. Test core functionality
python -c "
import tkinter as tk
root = tk.Tk()
root.title('Test GUI')
root.geometry('300x200')
tk.Label(root, text='GUI Test').pack()
print('GUI test window should appear')
root.mainloop()
"

# 3. Check system logs
# Windows: Event Viewer > Application Logs
# Linux: journalctl or /var/log/
# macOS: Console.app
```

## Advanced Installation Options

### Development Installation

For developers working on PowerTrader AI+:

```bash
# Clone with development branches
git clone -b development <repository-url>
cd PowerTrader_AI

# Install with development dependencies
pip install -r requirements-dev.txt
pip install -e .  # Editable installation

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### Container Installation (Advanced)

For containerized deployments:

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "app/pt_hub.py"]
```

### Multiple Environment Setup

For users managing multiple PowerTrader instances:

```bash
# Environment 1: Production
python -m venv .venv-prod
.venv-prod\Scripts\activate
python install_dependencies.py

# Environment 2: Development  
python -m venv .venv-dev
.venv-dev\Scripts\activate
pip install -r requirements-dev.txt

# Environment 3: Testing
python -m venv .venv-test
.venv-test\Scripts\activate
pip install -r requirements-test.txt
```

## Post-Installation Setup

### Initial Configuration

1. **Launch PowerTrader AI+**:
   ```bash
   cd app
   python pt_hub.py
   ```

2. **First-Time Setup Wizard**:
   - Configure exchange API keys (optional)
   - Set up OpenAI API key for LLM features (optional)
   - Configure trading parameters
   - Set up security preferences

3. **Verify All Features**:
   - Test GUI tabs (Current, Holdings, History, etc.)
   - Verify exchange connectivity (if configured)
   - Test LLM research features (if OpenAI configured)
   - Check real-time market data feeds

### Performance Optimization

```bash
# Install optional performance packages
pip install numba cython
pip install pandas[performance]

# For large datasets
pip install pyarrow fastparquet

# For advanced charting
pip install plotly bokeh
```

## Getting Help

### Documentation Resources
- **User Guide**: `/docs/user-guide/README.md`
- **API Documentation**: `/docs/api-configuration/README.md`  
- **Troubleshooting**: `/docs/troubleshooting/README.md`
- **Exchange Setup**: `/docs/exchanges/README.md`

### Support Channels
- **GitHub Issues**: Technical problems and bug reports
- **Documentation**: Check `/docs/` folder for detailed guides
- **Community**: PowerTrader AI+ user community

### System Information Collection

For support requests, gather this information:

```bash
# System info
python --version
pip --version
python -c "import platform; print('OS:', platform.platform())"

# PowerTrader info
cd app
python -c "
try:
    from pt_hub import __version__
    print('PowerTrader version:', __version__)
except:
    print('PowerTrader version: Not available')
"

# Dependency versions
pip list | grep -E "(flask|openai|ccxt|matplotlib|pandas)"
```

---

**Installation complete!** You're now ready to use PowerTrader AI+ for professional trading and portfolio management.