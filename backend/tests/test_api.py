from fastapi.testclient import TestClient
from app.main import app, AUDIT_LOG, CHALLENGES

client = TestClient(app)


def setup_function():
    AUDIT_LOG.clear()
    CHALLENGES.clear()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "0.2.0"


def test_search_patient():
    response = client.get("/patients/search", params={"q": "Maria"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["mrn"] == "MV-0001001"


def test_get_patient():
    response = client.get("/patients/pat-1002")
    assert response.status_code == 200
    assert response.json()["last_name"] == "Dela Cruz"


def test_missing_patient_returns_404():
    response = client.get("/patients/pat-9999")
    assert response.status_code == 404


def test_agent_requires_verification():
    response = client.post("/agent/query", json={"text": "Get Juan Dela Cruz latest lab results", "user_id": "dr-demo", "role": "clinician"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verification_required"
    assert body["intent"] == "GET_LATEST_LABS"
    assert body["patient"]["id"] == "pat-1002"
    assert body["challenge_id"]


def test_agent_verify_returns_labs_and_audits():
    challenge = client.post("/agent/query", headers={"X-Input-Method": "VOICE"}, json={"text": "MediVoice retrieve Juan Dela Cruz latest laboratory results", "user_id": "dr-demo", "role": "clinician"}).json()
    response = client.post("/agent/verify", json={"challenge_id": challenge["challenge_id"], "spoken_dob": "November 4 1978", "user_id": "dr-demo", "role": "clinician"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["resource_type"] == "Observation"
    assert "HbA1c" in body["message"]
    assert any(event.result == "ALLOWED" and event.method == "VOICE" for event in AUDIT_LOG)


def test_agent_wrong_dob_denied():
    challenge = client.post("/agent/query", json={"text": "Get Maria Santos allergies", "user_id": "nurse-demo", "role": "nurse"}).json()
    response = client.post("/agent/verify", json={"challenge_id": challenge["challenge_id"], "spoken_dob": "March 13 1985", "user_id": "nurse-demo", "role": "nurse"})
    assert response.status_code == 200
    assert response.json()["status"] == "verification_failed"


def test_rbac_denies_unauthorized_role():
    response = client.post("/agent/query", json={"text": "Get Maria Santos", "user_id": "guest", "role": "guest"})
    assert response.status_code == 403


def test_fhir_bundle_contains_expected_resources():
    response = client.get("/fhir/Patient/pat-1001/$everything", headers={"X-User-Role": "clinician"})
    assert response.status_code == 200
    body = response.json()
    assert body["resourceType"] == "Bundle"
    resource_types = {entry["resource"]["resourceType"] for entry in body["entry"]}
    assert {"Patient", "AllergyIntolerance", "MedicationRequest", "Condition", "Observation", "Appointment"}.issubset(resource_types)
