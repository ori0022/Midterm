import os
from typing import List, Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

class BankApiClient:
    """
    API Calls Layer: Encapsulates all communication with the Haovdim Bank Entity REST API.
    Pure HTTP client compliant with architectural layer separation (no direct SQLite database fallback).
    """
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        session: Optional[Any] = None,
        timeout: float = 5.0,
        db_manager: Optional[Any] = None  # Retained solely for signature compatibility; direct DB fallback is disabled
    ):
        self.base_url = (base_url or os.getenv("API_BASE_URL", "http://127.0.0.1:8000")).rstrip('/')
        self.api_key = api_key or os.getenv("BANK_API_KEY", os.getenv("INTERNAL_API_KEY"))
        self.token = token
        self.timeout = timeout
        self._session = session or requests

    def _get_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        api_key = self.api_key or os.getenv("BANK_API_KEY", os.getenv("INTERNAL_API_KEY"))
        if api_key:
            headers["X-API-Key"] = api_key
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        if self._session is None:
            raise RuntimeError("The 'requests' package is required for BankApiClient HTTP communication.")
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        kwargs["headers"] = headers

        try:
            timeout = kwargs.pop("timeout", self.timeout)
            if not hasattr(self._session, "app"):
                kwargs["timeout"] = timeout
            resp = self._session.request(method, url, **kwargs)
            return resp
        except Exception as e:
            raise ConnectionError(
                f"Bank API server is unreachable at {url} ({e}). "
                "Direct database fallback is strictly disabled to enforce API monitoring and security abstraction."
            ) from e

    def search_customers(self, query: str) -> List[Dict[str, Any]]:
        """Search for customers by partial or full name via REST API."""
        resp = self._request("GET", "/api/customers", params={"search": query})
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 401:
            raise PermissionError("Unauthorized: Invalid API key or token for customer search.")
        return []

    def get_customer(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve customer details by customer ID via REST API."""
        resp = self._request("GET", f"/api/customers/{customer_id}")
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return None
        elif resp.status_code == 401:
            raise PermissionError("Unauthorized: Invalid API key or token.")
        return None

    def verify_customer_id(self, customer_id: int, id_number: str) -> bool:
        """Securely verify customer ID number against the API without exposing ID data."""
        clean_id = id_number.strip().replace("-", "").replace(" ", "")
        resp = self._request(
            "POST",
            f"/api/customers/{customer_id}/verify-id",
            json={"id_number": clean_id}
        )
        if resp.status_code == 200:
            return resp.json().get("verified", False)
        return False

    def create_customer(
        self,
        name: str,
        phone: str,
        email: str,
        password: str,
        dob: str,
        address: str,
        id_number: str
    ) -> Dict[str, Any]:
        """Register a new customer via REST API."""
        resp = self._request(
            "POST",
            "/api/customers",
            json={
                "name": name,
                "phone": phone,
                "email": email,
                "password": password,
                "dob": dob,
                "address": address,
                "id_number": id_number
            }
        )
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code in (400, 422):
            detail = resp.json().get("detail", "Failed to create customer.")
            raise ValueError(detail)
        raise RuntimeError(f"Unexpected status {resp.status_code} during customer creation.")

    def get_customer_appointments(self, customer_id: int) -> List[Dict[str, Any]]:
        """Retrieve appointments for a given customer via REST API."""
        resp = self._request("GET", "/api/appointments", params={"customer_id": customer_id})
        if resp.status_code == 200:
            return resp.json()
        return []

    def get_all_appointments(self) -> List[Dict[str, Any]]:
        """Retrieve all bank appointments via REST API."""
        resp = self._request("GET", "/api/appointments")
        if resp.status_code == 200:
            return resp.json()
        return []

    def cancel_appointment(self, appointment_id: int, customer_id: Optional[int] = None) -> bool:
        """Cancel an appointment by ID with verified authorization."""
        params = {}
        if customer_id is not None:
            params["customer_id"] = customer_id
        resp = self._request("PATCH", f"/api/appointments/{appointment_id}/cancel", params=params)
        return resp.status_code == 200

    def create_appointment(self, customer_id: int, service_type: str, date: str, time: str) -> Dict[str, Any]:
        """Create a new appointment for a customer via REST API."""
        resp = self._request(
            "POST",
            "/api/appointments",
            json={
                "customer_id": customer_id,
                "service_type": service_type,
                "date": date,
                "time": time
            }
        )
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code in (400, 422):
            detail = resp.json().get("detail", "Failed to create appointment.")
            raise ValueError(detail)
        raise RuntimeError(f"Failed to create appointment, status {resp.status_code}")

    def reschedule_appointment(
        self,
        appointment_id: int,
        new_date: str,
        new_time: str,
        customer_id: Optional[int] = None
    ) -> bool:
        """Reschedule an appointment to a new date and time with verified authorization."""
        params = {}
        if customer_id is not None:
            params["customer_id"] = customer_id
        resp = self._request(
            "PATCH",
            f"/api/appointments/{appointment_id}/reschedule",
            params=params,
            json={"new_date": new_date, "new_time": new_time}
        )
        return resp.status_code == 200

    def get_invoices(self, customer_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve invoices via REST API."""
        params = {"customer_id": customer_id} if customer_id else {}
        resp = self._request("GET", "/api/invoices", params=params)
        if resp.status_code == 200:
            return resp.json()
        return []

    def get_leads(self) -> List[Dict[str, Any]]:
        """Retrieve all leads via REST API."""
        resp = self._request("GET", "/api/leads")
        if resp.status_code == 200:
            return resp.json()
        return []
