from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import uuid4
import re

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="MediVoice AI API",
    version="0.2.0",
    description="Conversational patient-record retrieval demo using synthetic data only.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LabResult(BaseModel):
    test: str
    value: str
    reference_range: str
    status: str = "normal"


class Patient(BaseModel):
    id: str
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    allergies: List[str]
    medications: List[str]
    diagnoses: List[str]
    latest_labs: List[LabResult]
    next_appointment: Optional[str] = None


class AgentRequest(BaseModel):
    text: str
    user_id: str = "clinician-demo"
    role: str = "clinician"


class VerifyRequest(BaseModel):
    challenge_id: str
    spoken_dob: str
    user_id: str = "clinician-demo"
    role: str = "clinician"


class AuditEvent(BaseModel):
    timestamp: str
    user_id: str
    role: str
    action: str
    patient_id: Optional[str]
    resource: Optional[str]
    method: str
    result: str
    detail: str


PATIENTS = [
    Patient(
        id="pat-1001",
        mrn="MV-0001001",
        first_name="Maria",
        last_name="Santos",
        date_of_birth=date(1985, 3, 12),
        sex="Female",
        allergies=["Penicillin"],
        medications=["Losartan 50 mg once daily"],
        diagnoses=["Essential hypertension"],
        latest_labs=[
            LabResult(test="Hemoglobin", value="13.2 g/dL", reference_range="12.0-15.5 g/dL"),
            LabResult(test="Fasting Glucose", value="104 mg/dL", reference_range="70-99 mg/dL", status="high"),
            LabResult(test="Creatinine", value="0.9 mg/dL", reference_range="0.6-1.1 mg/dL"),
        ],
        next_appointment="2026-09-18 10:30 Asia/Manila",
    ),
    Patient(
        id="pat-1002",
        mrn="MV-0001002",
        first_name="Juan",
        last_name="Dela Cruz",
        date_of_birth=date(1978, 11, 4),
        sex="Male",
        allergies=["None known"],
        medications=["Metformin 500 mg twice daily"],
        diagnoses=["Type 2 diabetes mellitus"],
        latest_labs=[
            LabResult(test="HbA1c", value="7.1%", reference_range="<5.7%", status="high"),
            LabResult(test="Creatinine", value="1.0 mg/dL", reference_range="0.7-1.3 mg/dL"),
        ],
        next_appointment="2026-09-22 14:00 Asia/Manila",
    ),
]

AUDIT_LOG: List[AuditEvent] = []
CHALLENGES = {}
ALLOWED_ROLES = {"clinician", "nurse", "records"}


def audit(user_id: str, role: str, action: str, result: str, detail: str,
          patient_id: Optional[str] = None, resource: Optional[str] = None,
          method: str = "TEXT"):
    AUDIT_LOG.append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_id=user_id,
        role=role,
        action=action,
        patient_id=patient_id,
        resource=resource,
        method=method,
        result=result,
        detail=detail,
    ))


def require_role(role: str):
    if role.lower() not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Role is not authorized for patient-record retrieval")


def patient_by_id(patient_id: str) -> Patient:
    patient = next((p for p in PATIENTS if p.id == patient_id), None)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def detect_patient(text: str) -> Optional[Patient]:
    lowered = text.lower()
    for p in PATIENTS:
        full = f"{p.first_name} {p.last_name}".lower()
        if full in lowered or p.mrn.lower() in lowered:
            return p
    return None


def detect_intent(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["lab", "laboratory", "hba1c", "creatinine", "glucose", "hemoglobin"]):
        return "GET_LATEST_LABS"
    if any(k in t for k in ["allerg", "reaction"]):
        return "GET_ALLERGIES"
    if any(k in t for k in ["medication", "medicine", "medications", "drug"]):
        return "GET_MEDICATIONS"
    if any(k in t for k in ["diagnosis", "diagnoses", "condition"]):
        return "GET_DIAGNOSES"
    if any(k in t for k in ["appointment", "schedule", "next visit"]):
        return "GET_APPOINTMENT"
    return "GET_SUMMARY"


def parse_spoken_dob(value: str) -> Optional[date]:
    cleaned = value.strip().lower().replace(",", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)

    m = re.search(r"(\d{4})[-/]([01]?\d)[-/]([0-3]?\d)", cleaned)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    m = re.search(r"([0-3]?\d)[-/]([01]?\d)[-/](\d{4})", cleaned)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for name, month in months.items():
        m = re.search(rf"{name}\s+(\d{{1,2}})\s+(\d{{4}})", cleaned)
        if m:
            try:
                return date(int(m.group(2)), month, int(m.group(1)))
            except ValueError:
                return None
        m = re.search(rf"(\d{{1,2}})\s+{name}\s+(\d{{4}})", cleaned)
        if m:
            try:
                return date(int(m.group(2)), month, int(m.group(1)))
            except ValueError:
                return None
    return None


def build_answer(patient: Patient, intent: str) -> tuple[str, str]:
    if intent == "GET_LATEST_LABS":
        parts = [f"{lab.test}: {lab.value} ({lab.status})" for lab in patient.latest_labs]
        return "Observation", f"Latest laboratory results for {patient.first_name} {patient.last_name}: " + "; ".join(parts) + "."
    if intent == "GET_ALLERGIES":
        return "AllergyIntolerance", f"Allergies for {patient.first_name} {patient.last_name}: " + ", ".join(patient.allergies) + "."
    if intent == "GET_MEDICATIONS":
        return "MedicationRequest", f"Current medications for {patient.first_name} {patient.last_name}: " + ", ".join(patient.medications) + "."
    if intent == "GET_DIAGNOSES":
        return "Condition", f"Recorded diagnoses for {patient.first_name} {patient.last_name}: " + ", ".join(patient.diagnoses) + "."
    if intent == "GET_APPOINTMENT":
        return "Appointment", f"The next appointment for {patient.first_name} {patient.last_name} is {patient.next_appointment}."
    abnormal = [lab for lab in patient.latest_labs if lab.status != "normal"]
    abnormal_text = ", ".join(f"{x.test} {x.value}" for x in abnormal) or "none flagged"
    return "Patient", (
        f"Summary for {patient.first_name} {patient.last_name}. Diagnoses: {', '.join(patient.diagnoses)}. "
        f"Allergies: {', '.join(patient.allergies)}. Medications: {', '.join(patient.medications)}. "
        f"Flagged latest labs: {abnormal_text}. Next appointment: {patient.next_appointment}."
    )


def fhir_bundle(patient: Patient):
    entries = [
        {
            "resource": {
                "resourceType": "Patient",
                "id": patient.id,
                "identifier": [{"system": "urn:medivoice:mrn", "value": patient.mrn}],
                "name": [{"family": patient.last_name, "given": [patient.first_name]}],
                "birthDate": patient.date_of_birth.isoformat(),
                "gender": patient.sex.lower(),
            }
        }
    ]
    for allergy in patient.allergies:
        entries.append({"resource": {"resourceType": "AllergyIntolerance", "patient": {"reference": f"Patient/{patient.id}"}, "code": {"text": allergy}}})
    for med in patient.medications:
        entries.append({"resource": {"resourceType": "MedicationRequest", "subject": {"reference": f"Patient/{patient.id}"}, "medication": {"concept": {"text": med}}, "status": "active", "intent": "order"}})
    for diagnosis in patient.diagnoses:
        entries.append({"resource": {"resourceType": "Condition", "subject": {"reference": f"Patient/{patient.id}"}, "code": {"text": diagnosis}, "clinicalStatus": {"text": "active"}})
    for lab in patient.latest_labs:
        entries.append({"resource": {"resourceType": "Observation", "subject": {"reference": f"Patient/{patient.id}"}, "code": {"text": lab.test}, "valueString": lab.value, "interpretation": [{"text": lab.status}], "referenceRange": [{"text": lab.reference_range}]}})
    if patient.next_appointment:
        entries.append({"resource": {"resourceType": "Appointment", "status": "booked", "description": "Synthetic follow-up appointment", "start": patient.next_appointment, "participant": [{"actor": {"reference": f"Patient/{patient.id}"}, "status": "accepted"}]}})
    return {"resourceType": "Bundle", "type": "collection", "total": len(entries), "entry": entries}


@app.get("/")
def root():
    return {"service": "MediVoice AI", "phase": "0.2", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "medivoice-api", "version": "0.2.0"}


@app.get("/patients/search", response_model=List[Patient])
def search_patients(q: Optional[str] = Query(default=None, min_length=1), mrn: Optional[str] = None):
    results = PATIENTS
    if q:
        needle = q.strip().lower()
        results = [p for p in results if needle in f"{p.first_name} {p.last_name}".lower() or needle in f"{p.last_name}, {p.first_name}".lower()]
    if mrn:
        results = [p for p in results if p.mrn.lower() == mrn.lower()]
    return results


@app.get("/patients/{patient_id}", response_model=Patient)
def get_patient(patient_id: str):
    return patient_by_id(patient_id)


@app.get("/patients/{patient_id}/summary")
def get_patient_summary(patient_id: str):
    patient = patient_by_id(patient_id)
    abnormal_labs = [lab for lab in patient.latest_labs if lab.status != "normal"]
    return {
        "patient_id": patient.id,
        "patient_name": f"{patient.first_name} {patient.last_name}",
        "diagnoses": patient.diagnoses,
        "allergies": patient.allergies,
        "medications": patient.medications,
        "abnormal_labs": abnormal_labs,
        "next_appointment": patient.next_appointment,
        "disclaimer": "Synthetic demonstration data only. Not for clinical use.",
    }


@app.get("/fhir/Patient/{patient_id}/$everything")
def get_fhir_everything(patient_id: str, x_user_role: str = Header(default="clinician")):
    require_role(x_user_role)
    patient = patient_by_id(patient_id)
    return fhir_bundle(patient)


@app.post("/agent/query")
def agent_query(request: AgentRequest, x_input_method: str = Header(default="TEXT")):
    require_role(request.role)
    patient = detect_patient(request.text)
    intent = detect_intent(request.text)
    if not patient:
        audit(request.user_id, request.role, intent, "NO_MATCH", "No patient could be resolved", method=x_input_method)
        return {
            "status": "patient_not_found",
            "intent": intent,
            "message": "I could not identify the patient. Please say the patient's full name or MRN.",
        }

    challenge_id = str(uuid4())
    CHALLENGES[challenge_id] = {
        "patient_id": patient.id,
        "intent": intent,
        "user_id": request.user_id,
        "role": request.role,
        "method": x_input_method,
    }
    audit(request.user_id, request.role, intent, "CHALLENGE", "Patient matched; DOB verification requested", patient.id, method=x_input_method)
    return {
        "status": "verification_required",
        "intent": intent,
        "patient": {"id": patient.id, "mrn": patient.mrn, "name": f"{patient.first_name} {patient.last_name}"},
        "challenge_id": challenge_id,
        "message": f"I found {patient.first_name} {patient.last_name}. Please confirm the patient's date of birth.",
    }


@app.post("/agent/verify")
def agent_verify(request: VerifyRequest):
    require_role(request.role)
    challenge = CHALLENGES.get(request.challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Verification challenge not found or expired")
    if challenge["user_id"] != request.user_id:
        raise HTTPException(status_code=403, detail="Challenge does not belong to this user")

    patient = patient_by_id(challenge["patient_id"])
    parsed = parse_spoken_dob(request.spoken_dob)
    if parsed != patient.date_of_birth:
        audit(request.user_id, request.role, challenge["intent"], "DENIED", "DOB verification failed", patient.id, method=challenge["method"])
        return {"status": "verification_failed", "message": "The date of birth did not match. Access was not granted."}

    resource, answer = build_answer(patient, challenge["intent"])
    del CHALLENGES[request.challenge_id]
    audit(request.user_id, request.role, challenge["intent"], "ALLOWED", "DOB verified; requested record returned", patient.id, resource, challenge["method"])
    return {
        "status": "ok",
        "intent": challenge["intent"],
        "resource_type": resource,
        "patient": patient.model_dump(mode="json"),
        "message": answer,
        "disclaimer": "Synthetic demonstration data only. Not for clinical use.",
    }


@app.get("/audit", response_model=List[AuditEvent])
def get_audit_log(x_user_role: str = Header(default="records")):
    require_role(x_user_role)
    return AUDIT_LOG[-100:]
