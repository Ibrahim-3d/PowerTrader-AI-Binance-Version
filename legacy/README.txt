Legacy Reference Files
======================

These are the original monolithic scripts preserved for reference during
the migration to the new src/powertrader/ package structure.

DO NOT MODIFY these files. They exist solely for:
- Behavioral comparison (side-by-side output verification)
- Understanding original logic during the refactoring process
- Rollback reference if needed

Original file sizes:
- pt_hub.py      ~5,300 lines (GUI control center)
- pt_trader.py   ~2,200 lines (trade executor)
- pt_trainer.py  ~1,600 lines (model trainer)
- pt_thinker.py  ~1,100 lines (signal generator)

The new equivalent code lives in src/powertrader/ with entry points in scripts/.
