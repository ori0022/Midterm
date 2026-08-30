import os
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
            except Exception:
                pass

_load_env()

from database import DatabaseManager
from verification import ChatbotService

app = FastAPI(
    title="Haovdim Bank Entity API & Appointment Chatbot",
    description="REST API for Haovdim Bank entities and an intelligent 4-layer verification appointment chatbot.",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DatabaseManager()
chatbot = ChatbotService()

# --- Pydantic Models for API Requests / Responses ---

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"

class ResetRequest(BaseModel):
    session_id: str = "default_session"

class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: str
    email: str
    dob: Optional[str] = None
    address: str
    id_number: Optional[str] = None

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

# --- Entity REST API Endpoints ---

@app.get("/api/customers", response_model=List[CustomerResponse], tags=["Customers"])
def get_customers(search: Optional[str] = Query(None, description="Search by partial or full customer name")):
    """Retrieve all customers or search by name."""
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
            dob=c.dob,
            address=c.address,
            id_number=c.id_number
        )
        for c in customers
    ]

@app.get("/api/customers/{customer_id}", response_model=CustomerResponse, tags=["Customers"])
def get_customer_by_id(customer_id: int):
    """Retrieve a single customer by ID."""
    customer = db.get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer with ID {customer_id} not found.")
    return CustomerResponse(
        id=customer.id,
        name=customer.name,
        phone=customer.phone,
        email=customer.email,
        dob=customer.dob,
        address=customer.address,
        id_number=customer.id_number
    )

@app.post("/api/customers", response_model=CustomerResponse, tags=["Customers"])
def create_customer_endpoint(req: CustomerCreateRequest):
    """Register a new customer with their ID number."""
    import hashlib
    clean_id = req.id_number.strip()
    if len(clean_id) != 9 or not clean_id.isdigit():
        raise HTTPException(status_code=400, detail="ID number (Teudat Zehut) must be exactly 9 digits.")
    pw_hash = hashlib.sha256(req.password.encode()).hexdigest()
    try:
        c = db.create_customer(req.name, req.phone, req.email, req.dob, pw_hash, req.address, clean_id)
        return CustomerResponse(
            id=c.id,
            name=c.name,
            phone=c.phone,
            email=c.email,
            dob=c.dob,
            address=c.address,
            id_number=c.id_number
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/appointments", response_model=List[AppointmentResponse], tags=["Appointments"])
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
def cancel_appointment_endpoint(appointment_id: int):
    """Cancel an appointment by ID."""
    db.update_appointment_status(appointment_id, "Cancelled")
    return {"message": f"Appointment {appointment_id} cancelled successfully."}

@app.post("/api/appointments", response_model=AppointmentResponse, tags=["Appointments"])
def create_appointment_endpoint(req: AppointmentCreateRequest):
    """Create a new appointment for a customer."""
    try:
        app = db.create_appointment(req.customer_id, req.service_type, req.date, req.time)
        return AppointmentResponse(
            id=app.id,
            customer_id=app.customer_id,
            customer_name=app.customer_name,
            service_type=app.service_type,
            date=app.date,
            time=app.time,
            status=app.status
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.patch("/api/appointments/{appointment_id}/reschedule", tags=["Appointments"])
def reschedule_appointment_endpoint(appointment_id: int, req: AppointmentRescheduleRequest):
    """Reschedule an appointment to a new date and time."""
    try:
        db.reschedule_appointment(appointment_id, req.new_date, req.new_time)
        return {"message": f"Appointment {appointment_id} rescheduled to {req.new_date} at {req.new_time}."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/invoices", tags=["Invoices"])
def get_invoices(customer_id: Optional[int] = Query(None, description="Filter invoices by customer ID")):
    """Retrieve invoices, optionally filtered by customer ID."""
    if customer_id is not None:
        invoices = db.get_invoices_by_customer(customer_id)
    else:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, customer_id, amount, date FROM Invoices")
            from models import Invoice
            invoices = [Invoice(*row) for row in cursor.fetchall()]
    return [
        {
            "id": inv.id,
            "customer_id": inv.customer_id,
            "amount": inv.amount,
            "date": inv.date
        }
        for inv in invoices
    ]

@app.get("/api/leads", tags=["Leads"])
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
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    result = chatbot.process_message(req.session_id, req.message)
    return result

@app.post("/api/chat/reset", tags=["Chatbot"])
def reset_chat_endpoint(req: ResetRequest):
    """
    Reset conversation state for a given session.
    """
    session = chatbot.reset_session(req.session_id)
    return {
        "message": f"Session {req.session_id} reset successfully.",
        "session": session.to_dict()
    }

@app.get("/api/chat/session/{session_id}", tags=["Chatbot"])
def get_session_endpoint(session_id: str):
    """
    Get current state of a conversation session.
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
    print(f"Starting Haovdim Bank Chatbot Web App at http://127.0.0.1:{port}")
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=True)
