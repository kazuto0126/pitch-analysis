# Deprecated / preserved components

Preprocessing is preserved on `integration/opencode-preprocessing`, checkpoint
`4a65c32` (parent analysis baseline `bc29f48`). It contains all 15 previously
uncommitted files: URL/local acquisition, yt-dlp, clip extraction, motion candidates,
CLIP ReID, naming, manifests, tests and documentation. It is not merged into
`codex/analysis-phase-0`; another project may import it later. Nothing was discarded.

The following remain on disk for compatibility, but are deprecated for new users:

- Top-level `src/*.py`: hard-coded single-video experiments, per-video Min-Max,
  legacy angle/stride names, plotting and missing-as-zero comparisons.
- `audit-media` / `media_audit.py`: historical source intake. Contact sheets can be
  reused for future analysis visualization, but source catalogs are outside scope.
- `detect-motion-windows`: historical long-video candidate workflow. Internal
  segmentation utilities remain used by `pipeline.py`; do not delete that module.
- `prepare-segment`: historical source-range API, still the adapter's core worker.
- `data/pitcher_database/raw/source_catalog.json` and intake_review: historical
  source records, not new input contracts.

No legacy source or dataset was deleted. `.venv`, videos and old generated outputs
already tracked by Git remain tracked; .gitignore does not remove them from history.
Untracking them needs a separate, reviewed data migration. The active environment
is `.venv-analysis`, created from an installed Python 3.12 and requirements-lock.txt.

Release directories v0.5 and v0.6 both remain available. **v0.6 is the current
canonical analysis baseline**. Historical schema strings such as registry version
`0.5-reviewed-event-window-provisional` are schema versions, not release names, and
must not be rewritten to v0.6.
