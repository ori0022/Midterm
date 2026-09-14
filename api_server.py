import os
import uuid
import secrets
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Depends, Header, Security
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from auth_utils import hash_password, create_access_token, verify_access_token, validate_israeli_id

def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception as e:
                print(f"[DEBUG] Notice while reading .env file: {e}")

_load_env()

from database import DatabaseManager
from verification import ChatbotService

app = FastAPI(
    title="Haovdim Bank Entity API & Appointment Chatbot",
    description="REST API for Haovdim Bank entities and an intelligent 4-layer verification appointment chatbot.",
    version="1.0.0"
)

# Enable CORS (compliant with CORS spec - credentials=False when wildcard/multi-origin)
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Authentication & Authorization Layer ---
# Load configured API key or generate a secure random key on startup (no static hardcoded default)
_configured_key = os.getenv("BANK_API_KEY", os.getenv("INTERNAL_API_KEY"))
if _configured_key and _configured_key.strip():
    BANK_API_KEY = _configured_key.strip()
else:
    BANK_API_KEY = secrets.token_urlsafe(32)

os.environ["BANK_API_KEY"] = BANK_API_KEY

from api_client import BankApiClient
db = DatabaseManager()
api_client = BankApiClient(base_url="http://127.0.0.1:8000", api_key=BANK_API_KEY)
chatbot = ChatbotService(api_client=api_client, db_manager=db)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(
    x_api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Header(None)
):
    """
    Validates that incoming requests to entity/admin endpoints provide
    a valid internal API key via X-API-Key header or Authorization Bearer token.
    Prevents unauthorized entity enumeration and direct API tampering.
    """
    token = x_api_key
    if not token and authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()

    if not token or token != BANK_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Valid X-API-Key header or Bearer token is required to access this endpoint."
        )
    return token

def get_current_user_or_staff(
    x_api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Validates either a Staff API Key or a signed Customer JWT Bearer token.
    Enforces authentication to prevent IDOR and unauthorized data manipulation.
    """
    token = x_api_key
    if not token and authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()

    # 1. Staff API key match
    if token and token == BANK_API_KEY:
        return {"role": "staff"}

    # 2. Signed customer JWT token
    if token:
        payload = verify_access_token(token)
        if payload and "sub" in payload:
            return {
                "role": payload.get("role", "customer"),
                "customer_id": int(payload["sub"])
            }

    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Valid Bearer JWT token or Staff API Key is required."
    )

# --- Pydantic Models for API Requests / Responses ---

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer_id: int
    customer_name: str

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ResetRequest(BaseModel):
    session_id: Optional[str] = None

class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: str
    email: str
    dob: Optional[str] = None
    address: Optional[str] = None

class VerifyIdRequest(BaseModel):
    id_number: str

class VerifyIdResponse(BaseModel):
    verified: bool
    message: str

class CustomerCreateRequest(BaseModel):
    name: str
    phone: str
    email: str
    password: str
    dob: str
    address: str
    id_number: str

class AppointmentResponse(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    service_type: str
    date: str
    time: str
    status: str

class AppointmentCreateRequest(BaseModel):
    customer_id: int
    service_type: str
    date: str
    time: str

class AppointmentRescheduleRequest(BaseModel):
    new_date: str
    new_time: str

# --- Authentication Endpoints ---

@app.post("/api/auth/login", response_model=LoginResponse, tags=["Authentication"])
def login_endpoint(req: LoginRequest):
    """Authenticate customer with email and password, returning a signed JWT access token."""
    customer = db.get_customer_by_auth(req.email.strip(), req.password)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token({"sub": customer.id, "role": "customer"})
    return LoginResponse(
        access_token=token,
        customer_id=customer.id,
        customer_name=customer.name
    )

# --- Entity REST API Endpoints ---

@app.get("/api/customers", response_model=List[CustomerResponse], tags=["Customers"], dependencies=[Depends(verify_api_key)])
def get_customers(search: Optional[str] = Query(None, description="Search by partial or full customer name")):
    """Retrieve all customers or search by name. PII like ID numbers, DOB, and address are withheld for privacy."""
    if search:
        customers = db.search_customers_by_name(search)
    else:
        customers = db.get_all_customers()
    return [
        CustomerResponse(
            id=c.id,
            name=c.name,
            phone=c.phone,
            email=c.email,
            dob=None,       # Withheld for privacy
            address=None    # Withheld for privacy
        )
        for c in customers
    ]

@app.get("/api/customers/{customer_id}", response_model=CustomerResponse, tags=["Customers"])
def get_customer_by_id(
    customer_id: int,
    auth_user: Dict[str, Any] = Depends(get_current_user_or_staff)
):
    """
    Retrieve a single customer by ID.
    PII (Date of Birth and Address) are strictly protected and withheld
    unless the caller is verified bank staff or the customer accessing their own record.
    """
    customer = db.get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer with ID {customer_id} not found.")

    allow_pii = (auth_user["role"] == "staff") or (auth_user.get("customer_id") == customer_id)
    return CustomerResponse(
        id=customer.id,
        name=customer.name,
        phone=customer.phone,
        email=customer.email,
        dob=customer.dob if allow_pii else None,
        address=customer.address if allow_pii else None
    )

@app.post("/api/customers/{customer_id}/verify-id", response_model=VerifyIdResponse, tags=["Customers"], dependencies=[Depends(verify_api_key)])
def verify_customer_id_endpoint(customer_id: int, req: VerifyIdRequest):
    """
    Securely verify a customer's ID number without exposing the actual ID in API responses.
    Enforces persistent database-backed brute force lockout (max 3 failed attempts).
    """
    customer = db.get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer with ID {customer_id} not found.")

    failed_attempts, locked_until = db.get_customer_lockout(customer_id)
    if locked_until > 0 and time.time() < locked_until:
        raise HTTPException(
            status_code=423,
            detail="Account is locked due to exceeding maximum verification attempts. Please contact bank support."
        )

    clean_id = req.id_number.strip().replace("-", "").replace(" ", "")
    actual_id = customer.id_number.strip().replace("-", "").replace(" ", "") if customer.id_number else ""

    if actual_id and actual_id == clean_id:
        db.clear_customer_lockout(customer_id)
        return VerifyIdResponse(verified=True, message="ID verification successful.")
    else:
        fails, is_locked, lock_time = db.record_failed_verification_attempt(customer_id)
        if is_locked:
            raise HTTPException(
                status_code=423,
                detail="Verification failed. Maximum of 3 attempts exceeded. Customer account has been locked for 15 minutes."
            )
        remaining = max(0, 3 - fails)
        return VerifyIdResponse(
            verified=False,
            message=f"The ID number provided does not match our records. You have {remaining} attempt{'s' if remaining > 1 else ''} remaining."
        )

@app.post("/api/customers", response_model=CustomerResponse, tags=["Customers"])
def create_customer_endpoint(req: CustomerCreateRequest):
    """Register a new customer with their ID number and salted bcrypt password."""
    clean_id = req.id_number.strip().replace("-", "").replace(" ", "")
    if not validate_israeli_id(clean_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid Israeli ID number (Teudat Zehut): must be 9 digits and pass the Luhn Modulo 10 check digit verification."
        )
    pw_hash = hash_password(req.password)
    try:
        c = db.create_customer(req.name, req.phone, req.email, req.dob, pw_hash, req.address, clean_id)
        return CustomerResponse(
            id=c.id,
            name=c.name,
            phone=c.phone,
            email=c.email,
            dob=c.dob,
            address=c.address
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/appointments", response_model=List[AppointmentResponse], tags=["Appointments"], dependencies=[Depends(verify_api_key)])
def get_appointments(customer_id: Optional[int] = Query(None, description="Filter appointments by customer ID")):
    """Retrieve appointments, optionally filtered by customer ID."""
    if customer_id is not None:
        appointments = db.get_appointments_by_customer(customer_id)
    else:
        appointments = db.get_all_appointments()
    return [
        AppointmentResponse(
            id=a.id,
            customer_id=a.customer_id,
            customer_name=a.customer_name,
            service_type=a.service_type,
            date=a.date,
            time=a.time,
            status=a.status
        )
        for a in appointments
    ]

@app.patch("/api/appointments/{appointment_id}/cancel", tags=["Appointments"])
def cancel_appointment_endpoint(
    appointment_id: int,
    auth_user: Dict[str, Any] = Depends(get_current_user_or_staff),
    customer_id: Optional[int] = Query(None, description="Customer ID for ownership check")
):
    """Cancel an appointment by ID with verified ownership validation (prevents IDOR)."""
    app_record = db.get_appointment_by_id(appointment_id)
    if not app_record:
        raise HTTPException(status_code=404, detail=f"Appointment with ID {appointment_id} not found.")

    if auth_user["role"] == "customer":
        if app_record.customer_id != auth_user["customer_id"]:
            raise HTTPException(status_code=403, detail="Forbidden: You are not authorized to cancel this appointment.")
        if customer_id is not None and customer_id != auth_user["customer_id"]:
            raise HTTPException(status_code=403, detail="Forbidden: customer_id parameter does not match authenticated token.")
    elif auth_user["role"] == "staff":
        if customer_id is None:
            raise HTTPException(status_code=422, detail="Field 'customer_id' query parameter is required.")
        if app_record.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="You are not authorized to cancel this appointment.")

    if app_record.status == "Cancelled":
        raise HTTPException(status_code=400, detail=f"Appointment {appointment_id} is already cancelled.")

    db.update_appointment_status(appointment_id, "Cancelled")
    return {"message": f"Appointment {appointment_id} cancelled successfully."}

@app.post("/api/appointments", response_model=AppointmentResponse, tags=["Appointments"], dependencies=[Depends(verify_api_key)])
def create_appointment_endpoint(req: AppointmentCreateRequest):
    """Create a new appointment for a customer."""
    try:
        app_item = db.create_appointment(req.customer_id, req.service_type, req.date, req.time)
        return AppointmentResponse(
            id=app_item.id,
            customer_id=app_item.customer_id,
            customer_name=app_item.customer_name,
            service_type=app_item.service_type,
            date=app_item.date,
            time=app_item.time,
            status=app_item.status
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.patch("/api/appointments/{appointment_id}/reschedule", tags=["Appointments"])
def reschedule_appointment_endpoint(
    appointment_id: int,
    req: AppointmentRescheduleRequest,
    auth_user: Dict[str, Any] = Depends(get_current_user_or_staff),
    customer_id: Optional[int] = Query(None, description="Customer ID for ownership check")
):
    """Reschedule an appointment to a new date and time with verified ownership validation (prevents IDOR)."""
    app_record = db.get_appointment_by_id(appointment_id)
    if not app_record:
        raise HTTPException(status_code=404, detail=f"Appointment with ID {appointment_id} not found.")

    if auth_user["role"] == "customer":
        if app_record.customer_id != auth_user["customer_id"]:
            raise HTTPException(status_code=403, detail="Forbidden: You are not authorized to reschedule this appointment.")
        if customer_id is not None and customer_id != auth_user["customer_id"]:
            raise HTTPException(status_code=403, detail="Forbidden: customer_id parameter does not match authenticated token.")
    elif auth_user["role"] == "staff":
        if customer_id is None:
            raise HTTPException(status_code=422, detail="Field 'customer_id' query parameter is required.")
        if app_record.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="You are not authorized to reschedule this appointment.")

    if app_record.status == "Cancelled":
        raise HTTPException(status_code=400, detail="Cannot reschedule an appointment that has already been cancelled.")

    try:
        db.reschedule_appointment(appointment_id, req.new_date, req.new_time)
        return {"message": f"Appointment {appointment_id} rescheduled to {req.new_date} at {req.new_time}."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/invoices", tags=["Invoices"], dependencies=[Depends(verify_api_key)])
def get_invoices(customer_id: Optional[int] = Query(None, description="Filter invoices by customer ID")):
    """Retrieve invoices, optionally filtered by customer ID."""
    if customer_id is not None:
        invoices = db.get_invoices_by_customer(customer_id)
    else:
        invoices = db.get_all_invoices()
    return [
        {
            "id": inv.id,
            "customer_id": inv.customer_id,
            "amount": inv.amount,
            "date": inv.date
        }
        for inv in invoices
    ]

@app.get("/api/leads", tags=["Leads"], dependencies=[Depends(verify_api_key)])
def get_leads():
    """Retrieve all leads."""
    leads = db.get_all_leads()
    return [
        {
            "id": l.id,
            "name": l.name,
            "phone": l.phone,
            "source": l.source,
            "status": l.status,
            "notes": l.notes
        }
        for l in leads
    ]

# --- Chatbot Conversation Endpoints ---

@app.post("/api/chat", tags=["Chatbot"])
def chat_endpoint(req: ChatRequest):
    """
    Send a message to the verification & appointment chatbot.
    Auto-generates a cryptographically secure session_id if none is provided.
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    session_id = req.session_id.strip() if req.session_id and req.session_id.strip() else f"session_{secrets.token_hex(16)}"
    result = chatbot.process_message(session_id, req.message)
    return result

@app.post("/api/chat/reset", tags=["Chatbot"])
def reset_chat_endpoint(req: ResetRequest):
    """
    Reset conversation state for a given session.
    Auto-generates a cryptographically secure session_id if none is provided.
    """
    session_id = req.session_id.strip() if req.session_id and req.session_id.strip() else f"session_{secrets.token_hex(16)}"
    session = chatbot.reset_session(session_id)
    return {
        "message": f"Session {session_id} reset successfully.",
        "session": session.to_dict()
    }

@app.get("/api/chat/session/{session_id}", tags=["Chatbot"], dependencies=[Depends(verify_api_key)])
def get_session_endpoint(session_id: str):
    """
    Get current state of a conversation session (internal/diagnostic endpoint).
    Requires API key to prevent session probing.
    """
    session = chatbot.get_session(session_id)
    return session.to_dict()

# --- Serve Web Chat UI ---

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

@app.get("/", include_in_schema=False)
def serve_ui():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "Haovdim Bank API is running. Access /docs for Swagger."})

app.mount("/static", StaticFiles(directory=static_dir), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    reload_flag = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    print(f"Starting Haovdim Bank Chatbot Web App at http://{host}:{port} (reload={reload_flag})")
    uvicorn.run("api_server:app", host=host, port=port, reload=reload_flag)
