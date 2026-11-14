"""Cross-domain scientific algorithms.

Implemented:
- `data_quality`: Data Quality Engine. How far can the data be trusted?
- `personal_baseline`: Personal Baseline Engine. Reference statistics per crew member,
  metric and mission phase.
- `robust_statistics`: descriptive and robust statistics used by both.

Not implemented yet: deviation evaluation.

See `README.md` in this package for the rules, the settings and the limitations.

Rules for code in this package:
- Pure Python. Never import FastAPI, `app.api` or `app.domains`.
- Inputs and outputs are the contract models from `app.models`.
- Every threshold or constant cites its source next to the value. See AGENTS.md.
"""
