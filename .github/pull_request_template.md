## What and why

## Checklist
- [ ] `make check` passes
- [ ] No PHI in code, fixtures, logs, traces or test data (synthetic only)
- [ ] New external dependency goes behind a port in `libs/aibase/providers` (vendor-agnostic)
- [ ] Prompt changes are a new version file, not an in-place edit
- [ ] New endpoints enforce auth scope + tenant scoping and write an audit event
