# Legacy Scripts

This directory contains the **original monolithic scripts** preserved for reference
and behavioral comparison during the migration to the modular `src/powertrader/` package.

These files are **frozen snapshots** and should not be modified.

| File | Lines | Description |
|------|-------|-------------|
| `pt_hub.py` | ~5,236 | Original GUI hub (Tkinter) |
| `pt_trainer.py` | ~1,695 | Original per-coin training script |
| `pt_thinker.py` | ~1,058 | Original signal generator |
| `pt_trader.py` | ~2,195 | Original trade executor |

## Purpose

1. **Reference** -- compare new module behavior against the originals
2. **Rollback** -- if a behavioral regression is found, revert to these scripts
3. **Comparison** -- `scripts/compare_outputs.py` uses these to verify identical outputs

## Replacement

The root-level `pt_*.py` files are now thin wrappers that delegate to the
new modular package (`src/powertrader/`). The originals live here.
