# PowerTrader AI+ — Project Context for Claude

## What This Project Is

Automated crypto/stock trading platform built in Python. Core loop: fetch market data, run neural analysis, make DCA/trade decisions, execute orders via exchange APIs, manage risk. Targets Robinhood (primary), Binance, Kraken, KuCoin, and 60+ exchanges via `ccxt`.

GUI is Tkinter-based (`pt_hub.py` — 330KB, the main window). Backend logic in `pt_trader.py` (100KB). Neural analysis in `pt_thinker.py` (55KB) and `pt_neural_processor.py`.

## Project Goal

Migrate from working prototype (~40-50% production-ready) to enterprise-grade trading platform. 16-week roadmap across 4 phases tracked in `TODO.md`.

**Owner:** @sjackson0109  
**Contributor:** @Ibrahim-3d (me — working via fork PRs, no direct push access)  
**Fork:** `Ibrahim-3d/PowerTraderAI` → PRs into `sjackson0109/PowerTraderAI`

## Current Status (Phase 1 - Security)

6 open PRs, all awaiting owner review/approval:

| PR | Issues Closed | Topic |
|----|--------------|-------|
| #79 | #61 | Circuit breaker for API protection |
| #80 | #58, #59 | Credential rotation + permission validation |
| #81 | #60 | Centralized error management |
| #82 | #62, #63 | DB backup/restore + data corruption detection |
| #83 | #54 | DB connection pool, atomic transactions, health monitor |
| #84 | #55 | Security/audit logging with correlation IDs |

New modules added this phase: `pt_circuit_breaker.py`, `pt_backup.py`, `pt_database_manager.py`, `pt_security_logger.py`, `pt_error_handler.py`. Enhanced: `pt_credentials.py`, `pt_validation.py`.

## Repository Layout

```
app/
  pt_hub.py              # Main GUI window (Tkinter, 330KB)
  pt_trader.py           # Core trading logic (100KB)
  pt_thinker.py          # Neural/AI signal analysis (55KB)
  pt_exchanges.py        # Exchange API integrations (54KB)
  pt_credentials.py      # Encrypted credential management
  pt_risk.py             # Risk management engine
  pt_data_provider.py    # Market data pipeline
  pt_logging_system.py   # Structured logging
  pt_errors.py           # Custom exceptions + ErrorHandler
  order_management_db.py # SQLAlchemy ORM for orders (SQLite)
  order_management_models.py
  migrations.py
  advanced_*.py          # Stop-loss, take-profit, risk modules
  *_gui.py               # Tkinter GUI components
  test_*.py              # Test files
  config/                # YAML/JSON config files
.github/workflows/
  ci-cd.yml              # Security scan + tests
  code-quality.yml       # Black, flake8, pytest
  project-management.yml # Auto-labeling, milestone tracking
```

## Architecture Decisions

- **Exchange abstraction**: `pt_exchange_abstraction.py` wraps ccxt + native APIs. Never hardcode exchange-specific calls outside this layer.
- **Credentials**: Fernet-encrypted at rest via `pt_credentials.py`. Never read `r_key.txt`/`r_secret.txt` directly — always use `get_credentials()`.
- **Database**: SQLite via SQLAlchemy ORM (`order_management_db.py`). Use `atomic_transaction()` from `pt_database_manager.py` for critical writes.
- **Errors**: Raise typed exceptions from `pt_errors.py`. Route through `get_handler()` from `pt_error_handler.py` for callbacks/notifications.
- **Logging**: Use `pt_logging_system.py` for app logs. Use `pt_security_logger.py` + `correlation_context()` for security/audit events.

## Code Standards

- **Formatter**: Black (`black --check app/`)
- **Linter**: flake8, max line length 100, ignore E203/W503
- **Tests**: pytest, all new modules need test files (`test_{module}.py`)
- **No bare except**: Catch specific exceptions. Use types from `pt_errors.py`.
- **No plaintext secrets**: All credentials via `get_credentials()` or env vars.

CI checks on every PR: Black, flake8 (hard errors E9/F63/F7/F82 block, soft warnings with `--exit-zero`), pytest. Bandit + Safety security scans run too.

## PR Workflow (Fork Contributor)

```bash
# Always branch from main
git checkout main && git checkout -b feat/{issue-number}-description

# Push to fork, not origin
git push fork feat/{issue-number}-description

# Open PR from fork into upstream
gh pr create --repo sjackson0109/PowerTraderAI \
  --head "Ibrahim-3d:feat/branch-name" --base main
```

CI workflows show `action_required` on fork PRs — owner must approve before they run. Simulate locally first:

```bash
black --check app/new_file.py
flake8 app/new_file.py --max-line-length=100 --extend-ignore=E203,W503
python -m pytest app/test_new_file.py -q
```

## Responding to Copilot Review Comments

1. Get inline comment IDs: `gh api repos/sjackson0109/PowerTraderAI/pulls/{pr}/comments`
2. Reply per-thread: `POST /repos/.../pulls/{pr}/comments/{id}/replies`
3. Resolve threads via GraphQL `resolveReviewThread` mutation (we have write access via fork ownership)
4. Add table summary comment on PR conversation listing each thread with plain `#1, #2` numbering
5. Do NOT link to `#discussion_r{id}` anchors — they break when threads are resolved/collapsed

Reply structure: original design intent → what was wrong → fix justification → open question if trade-off exists.

## Remaining Work (TODO.md Reference)

**Phase 1 remaining** (still open issues): #52 credential storage full audit, #53 bare except audit in `pt_trader.py`  
**Phase 2**: Order execution (#56), risk engine (#57), advanced orders (#64), emergency procedures (#66), data pipeline (#67), performance monitoring (#68)  
**Phase 3**: Compliance framework (#69), enterprise features (#70), installer (#71), test automation (#72), monitoring suite (#73)  
**Phase 4**: High-perf execution (#74), distributed architecture (#75), cloud deployment (#76), ML optimization (#77)

New issues opened by owner: #85 Binance order execution, #86 paper trading bug, #87 e2e demo script.

## Key Files to Know Before Touching

| File | Risk | Notes |
|------|------|-------|
| `pt_trader.py` | High | Core loop. Touch carefully. Test paper trading first. |
| `pt_hub.py` | High | 330KB GUI. Many interdependencies. |
| `pt_thinker.py` | Medium | Neural signals. Changes affect trade decisions. |
| `order_management_db.py` | High | ORM layer. Schema changes need migration. |
| `pt_credentials.py` | Critical | Any change risks locking users out. |
| `migrations.py` | High | Migrations must be reversible. |

## Workflow Rules

1. **Plan before build** — for anything 3+ steps, write plan to a scratch note first.
2. **Verify before done** — never mark complete without test evidence.
3. **Minimal impact** — touch only what's needed. No side effects.
4. **No temp fixes** — find root cause. Senior-engineer standard.
5. **After corrections** — update `LEARNINGS.md` with the pattern.

See `LEARNINGS.md` for session-specific technical lessons (API endpoints, patterns, gotchas).
