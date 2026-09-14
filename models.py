from dataclasses import dataclass
from typing import Optional

@dataclass
class Customer:
    id: Optional[int]
    name: str
    phone: str
    email: str
    dob: str
    address: str
    id_number: Optional[str] = None

@dataclass
class Appointment:
    id: Optional[int]
    customer_id: int
    customer_name: str
    service_type: str
    date: str
    time: str
    status: str

@dataclass
class Invoice:
    id: Optional[int]
    customer_id: int
    amount: float
    date: str

@dataclass
class Lead:
    id: Optional[int]
    name: str
    phone: str
    source: str
    status: str
    notes: str
