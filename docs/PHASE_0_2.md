# MediVoice AI Phase 0.2 — Conversational Voice Intelligence

## Goal
Turn the Phase 0.1 patient-search foundation into a controlled voice-assisted retrieval workflow using synthetic records only.

## Retrieval flow
1. User submits text or browser speech transcript.
2. Backend checks the demo RBAC role.
3. Deterministic intent parser identifies the requested record type.
4. Patient resolver matches full name or MRN.
5. A DOB verification challenge is created.
6. User supplies DOB by text or speech.
7. On a match, the requested synthetic clinical resource is returned.
8. Browser text-to-speech reads the response.
9. Challenge/allow/deny actions are written to the in-memory audit trail.

## Supported intents
- GET_LATEST_LABS → Observation
- GET_ALLERGIES → AllergyIntolerance
- GET_MEDICATIONS → MedicationRequest
- GET_DIAGNOSES → Condition
- GET_APPOINTMENT → Appointment
- GET_SUMMARY → Patient summary

## Security note
This phase demonstrates the control flow only. It is not production identity proofing, authentication, authorization, consent management, or HIPAA compliance.
