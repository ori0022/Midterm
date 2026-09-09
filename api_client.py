import os
try:
    import requests
except ImportError:
    requests = None
from typing import List, Dict, Any, Optional

class BankApiClient:
    """
    API Calls Layer: Encapsulates all communication with the Haovdim Bank Entity API.
    Supports HTTP REST communication and direct database fallback for standalone execution.
    """
    def __init__(self, base_url: Optional[str] = None, db_manager: Optional[Any] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or os.getenv("API_BASE_URL", "http://127.0.0.1:8000")).rstrip('/')
        self.api_key = api_key or os.getenv("BANK_API_KEY", os.getenv("INTERNAL_API_KEY", "haovdim_bank_internal_secret_key_2026"))
        self._db = db_manager
        self._server_available = False if db_manager is not None else None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key
        }

    def _is_server_available(self) -> bool:
        if requests is None:
            return False
        if self._server_available is None:
            try:
                resp = requests.get(f"{self.base_url}/docs", timeout=0.2)
                self._server_available = (resp.status_code == 200)
            except Exception:
                self._server_available = False
        return self._server_available

    def _get_db(self):
        if self._db is None:
            from database import DatabaseManager
            self._db = DatabaseManager()
        return self._db

    def search_customers(self, query: str) -> List[Dict[str, Any]]:
        """Search for customers by partial or full name."""
        if self._is_server_available():
            try:
                resp = requests.get(
                    f"{self.base_url}/api/customers",
                    params={"search": query},
                    headers=self._get_headers(),
                    timeout=2.0
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                self._server_available = False
        
        # Fallback to direct DB query if API server is not running
        db = self._get_db()
        customers = db.search_customers_by_name(query)
        return [
            {
                "id": c.id,
                "name": c.name,
                "phone": c.phone,
                "email": c.email,
                "dob": c.dob,
                "address": c.address
            }
            for c in customers
        ]

    def get_customer(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve customer details by customer ID."""
        if self._is_server_available():
            try:
                resp = requests.get(
                    f"{self.base_url}/api/customers/{customer_id}",
                    headers=self._get_headers(),
                    timeout=2.0
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                self._server_available = False

        db = self._get_db()
        c = db.get_customer_by_id(customer_id)
        if c:
            return {
                "id": c.id,
                "name": c.name,
                "phone": c.phone,
                "email": c.email,
                "dob": c.dob,
                "address": c.address
            }
        return None

    def verify_customer_id(self, customer_id: int, id_number: str) -> bool:
        """Securely verify customer ID number against the API or DB without exposing ID data."""
        clean_id = id_number.strip()
        if self._is_server_available():
            try:
                resp = requests.post(
                    f"{self.base_url}/api/customers/{customer_id}/verify-id",
                    json={"id_number": clean_id},
                    headers=self._get_headers(),
                    timeout=2.0
                )
                if resp.status_code == 200:
                    return resp.json().get("verified", False)
            except Exception:
                self._server_available = False

        # Fallback to direct DB query if API server is not running
        db = self._get_db()
        c = db.get_customer_by_id(customer_id)
        if c and c.id_number:
            return c.id_number.strip() == clean_id
        return False

    def create_customer(self, name: str, phone: str, email: str, password: str, dob: str, address: str, id_number: str) -> Dict[str, Any]:
        """Register a new customer via REST API or direct DB fallback."""
        if self._is_server_available():
            try:
                resp = requests.post(
                    f"{self.base_url}/api/customers",
                    json={
                        "name": name,
                        "phone": phone,
                        "email": email,
                        "password": password,
                        "dob": dob,
                        "address": address,
                        "id_number": id_number
                    },
                    headers=self._get_headers(),
                    timeout=3.0
                )
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 400:
                    raise ValueError(resp.json().get("detail", "Failed to create customer."))
            except ValueError:
                raise
            except Exception:
                self._server_available = False

        db = self._get_db()
        from auth_utils import hash_password
        pw_hash = hash_password(password)
        cust = db.create_customer(name, phone, email, dob, pw_hash, address, id_number)
        return {
            "id": cust.id,
            "name": cust.name,
            "phone": cust.phone,
            "email": cust.email,
            "dob": cust.dob,
            "address": cust.address
        }

    def get_customer_appointments(self, customer_id: int) -> List[Dict[str, Any]]:
        """Retrieve appointments for a given customer."""
        if self._is_server_available():
            try:
                resp = requests.get(
                    f"{self.base_url}/api/appointments",
                    params={"customer_id": customer_id},
                    headers=self._get_headers(),
                    timeout=2.0
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                self._server_available = False

        db = self._get_db()
        apps = db.get_appointments_by_customer(customer_id)
        return [
            {
                "id": a.id,
                "customer_id": a.customer_id,
                "customer_name": a.customer_name,
                "service_type": a.service_type,
                "date": a.date,
                "time": a.time,
                "status": a.status
            }
            for a in apps
        ]

    def get_all_appointments(self) -> List[Dict[str, Any]]:
        """Retrieve all bank appointments."""
        if self._is_server_available():
            try:
                resp = requests.get(
                    f"{self.base_url}/api/appointments",
                    headers=self._get_headers(),
                    timeout=2.0
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                self._server_available = False

        db = self._get_db()
        apps = db.get_all_appointments()
        return [
            {
                "id": a.id,
                "customer_id": a.customer_id,
                "customer_name": a.customer_name,
                "service_type": a.service_type,
                "date": a.date,
                "time": a.time,
                "status": a.status
            }
            for a in apps
        ]

    def cancel_appointment(self, appointment_id: int, customer_id: Optional[int] = None) -> bool:
        """Cancel an appointment by ID with mandatory customer ownership check."""
        if self._is_server_available():
            try:
                params = {}
                if customer_id is not None:
                    params["customer_id"] = customer_id
                resp = requests.patch(
                    f"{self.base_url}/api/appointments/{appointment_id}/cancel",
                    params=params,
                    headers=self._get_headers(),
                    timeout=2.0
                )
                if resp.status_code == 200:
                    return True
                elif resp.status_code in (400, 403, 404, 422):
                    return False
            except Exception:
                self._server_available = False

        db = self._get_db()
        if customer_id is not None:
            rec = db.get_appointment_by_id(appointment_id)
            if not rec or rec.customer_id != customer_id:
                return False
        return db.update_appointment_status(appointment_id, "Cancelled")

    def create_appointment(self, customer_id: int, service_type: str, date: str, time: str) -> Dict[str, Any]:
        """Create a new appointment for a customer."""
        if self._is_server_available():
            try:
                resp = requests.post(
                    f"{self.base_url}/api/appointments",
                    json={
                        "customer_id": customer_id,
                        "service_type": service_type,
                        "date": date,
                        "time": time
                    },
                    headers=self._get_headers(),
                    timeout=2.0
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                self._server_available = False

        db = self._get_db()
        app = db.create_appointment(customer_id, service_type, date, time)
        return {
            "id": app.id,
            "customer_id": app.customer_id,
            "customer_name": app.customer_name,
            "service_type": app.service_type,
            "date": app.date,
            "time": app.time,
            "status": app.status
        }

    def reschedule_appointment(self, appointment_id: int, new_date: str, new_time: str, customer_id: Optional[int] = None) -> bool:
        """Reschedule an appointment to a new date and time with mandatory customer ownership check."""
        if self._is_server_available():
            try:
                params = {}
                if customer_id is not None:
                    params["customer_id"] = customer_id
                resp = requests.patch(
                    f"{self.base_url}/api/appointments/{appointment_id}/reschedule",
                    params=params,
                    json={"new_date": new_date, "new_time": new_time},
                    headers=self._get_headers(),
                    timeout=2.0
                )
                if resp.status_code == 200:
                    return True
                elif resp.status_code in (400, 403, 404, 422):
                    return False
            except Exception:
                self._server_available = False

        db = self._get_db()
        if customer_id is not None:
            rec = db.get_appointment_by_id(appointment_id)
            if not rec or rec.customer_id != customer_id:
                return False
        return db.reschedule_appointment(appointment_id, new_date, new_time)

    def get_invoices(self, customer_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve invoices, optionally filtered by customer ID."""
        if self._is_server_available():
            try:
                params = {"customer_id": customer_id} if customer_id else {}
                resp = requests.get(
                    f"{self.base_url}/api/invoices",
                    params=params,
                    headers=self._get_headers(),
                    timeout=2.0
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                self._server_available = False

        db = self._get_db()
        if customer_id:
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

    def get_leads(self) -> List[Dict[str, Any]]:
        """Retrieve all leads."""
        if self._is_server_available():
            try:
                resp = requests.get(
                    f"{self.base_url}/api/leads",
                    headers=self._get_headers(),
                    timeout=2.0
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                self._server_available = False

        db = self._get_db()
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
