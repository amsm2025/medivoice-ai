# MediVoice AI — Phase 0.1 Foundation

## Objective
Create a runnable development baseline for secure patient record retrieval before introducing LLM and voice capabilities.

## Functional baseline
1. API service starts and exposes health status.
2. Users can search synthetic patients by name or MRN.
3. Users can retrieve a patient record by internal patient ID.
4. Users can retrieve a compact clinical summary.
5. Browser UI can call the API.
6. Automated tests validate the core API.

## Security posture for this phase
- Synthetic records only.
- No production PHI.
- No direct LLM access to databases.
- CORS constrained to local development origins.
- Authentication, RBAC, consent and immutable audit controls are mandatory before any real-world data integration.

## Acceptance criteria
- `/health` returns HTTP 200.
- Maria Santos can be found through `/patients/search?q=Maria`.
- Unknown patient IDs return HTTP 404.
- Test suite passes.
- Docker Compose can run both API and UI.
