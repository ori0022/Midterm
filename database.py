import sqlite3
import time
import json
from typing import List, Optional, Tuple, Dict, Any
from models import Customer, Appointment, Invoice, Lead
from auth_utils import hash_password, verify_password

DB_NAME = "bank_haovdim.db"

class DatabaseManager:
    def __init__(self, db_name: str = DB_NAME):
        self.db_name = db_name
        self.initialize_db()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def initialize_db(self):
        """Creates the necessary tables if they do not exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    dob TEXT,
                    address TEXT NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL,
                    service_type TEXT NOT NULL,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Pending',
                    FOREIGN KEY (customer_id) REFERENCES Customers (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    date TEXT NOT NULL,
                    FOREIGN KEY (customer_id) REFERENCES Customers (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'New',
                    notes TEXT
                )
            ''')
            
            # Atomic unique index to prevent race conditions on appointment booking/rescheduling
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_appointments_active_slot
                ON Appointments (date, time)
                WHERE status != 'Cancelled'
            ''')

            # Chat Sessions table for multi-process concurrency
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ChatSessions (
                    session_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    language TEXT DEFAULT 'en',
                    claimed_name TEXT,
                    claimed_date TEXT,
                    candidate_customer_json TEXT,
                    clarification_candidates_json TEXT,
                    pending_cancellation_id INTEGER,
                    pending_reschedule_id INTEGER,
                    pending_booking_date TEXT,
                    pending_booking_time TEXT,
                    pending_booking_service TEXT,
                    registration_data_json TEXT,
                    registration_step TEXT,
                    failed_attempts INTEGER DEFAULT 0,
                    verified INTEGER DEFAULT 0,
                    history_json TEXT,
                    last_activity REAL NOT NULL
                )
            ''')

            # Customer Verification Lockout tracking across sessions and workers
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS CustomerVerificationLocks (
                    customer_id INTEGER PRIMARY KEY,
                    failed_attempts INTEGER DEFAULT 0,
                    locked_until REAL DEFAULT 0,
                    last_attempt_at REAL NOT NULL,
                    FOREIGN KEY (customer_id) REFERENCES Customers (id)
                )
            ''')

            # Ensure id_number column exists in Customers
            cursor.execute("PRAGMA table_info(Customers)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'id_number' not in columns:
                cursor.execute("ALTER TABLE Customers ADD COLUMN id_number TEXT")
                conn.commit()

            # Ensure language column exists in ChatSessions
            cursor.execute("PRAGMA table_info(ChatSessions)")
            sess_cols = [col[1] for col in cursor.fetchall()]
            if 'language' not in sess_cols:
                cursor.execute("ALTER TABLE ChatSessions ADD COLUMN language TEXT DEFAULT 'en'")
                conn.commit()

            conn.commit()

    # --- Customer Methods ---

    def get_customer_by_auth(self, email: str, password_or_hash: str) -> Optional[Customer]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, phone, email, dob, address, id_number, password FROM Customers WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                stored_hash = row[7]
                if verify_password(password_or_hash, stored_hash) or password_or_hash == stored_hash:
                    return Customer(row[0], row[1], row[2], row[3], row[4], row[5], row[6])
        return None

    def create_customer(self, name: str, phone: str, email: str, dob: str, password_hash: str, address: str, id_number: Optional[str] = None) -> Customer:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO Customers (name, phone, email, password, dob, address, id_number) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                               (name, phone, email, password_hash, dob, address, id_number))
                conn.commit()
                return Customer(cursor.lastrowid, name, phone, email, dob, address, id_number)
            except sqlite3.IntegrityError:
                raise ValueError(f"Customer with email {email} already exists.")

    def get_all_customers(self) -> List[Customer]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, phone, email, dob, address, id_number FROM Customers")
            rows = cursor.fetchall()
            return [Customer(*row) for row in rows]

    def search_customers_by_name(self, query: str) -> List[Customer]:
        """Search customers by partial or full name (case-insensitive)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, phone, email, dob, address, id_number FROM Customers WHERE LOWER(name) LIKE LOWER(?)",
                (f"%{query.strip()}%",)
            )
            rows = cursor.fetchall()
            return [Customer(*row) for row in rows]

    def get_customer_by_id(self, customer_id: int) -> Optional[Customer]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, phone, email, dob, address, id_number FROM Customers WHERE id = ?",
                (customer_id,)
            )
            row = cursor.fetchone()
            if row:
                return Customer(*row)
        return None

    def update_customer_id_number(self, customer_id: int, id_number: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Customers SET id_number = ? WHERE id = ?", (id_number, customer_id))
            conn.commit()

    def delete_customer(self, customer_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Customers WHERE id = ?", (customer_id,))
            cursor.execute("DELETE FROM Appointments WHERE customer_id = ?", (customer_id,))
            cursor.execute("DELETE FROM Invoices WHERE customer_id = ?", (customer_id,))
            conn.commit()

    # --- Appointment Methods ---

    def get_booked_times_for_date(self, date: str) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT time FROM Appointments WHERE date = ? AND status != 'Cancelled'", (date,))
            rows = cursor.fetchall()
            return [row[0] for row in rows]

    def check_collision(self, date: str, time: str) -> bool:
        """Checks if a time slot is already taken (regardless of service type)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM Appointments WHERE date = ? AND time = ? AND status != 'Cancelled'", 
                (date, time)
            )
            count = cursor.fetchone()[0]
            return count > 0

    def create_appointment(self, customer_id: int, service_type: str, date: str, time: str) -> Appointment:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM Appointments WHERE date = ? AND time = ? AND status != 'Cancelled'",
                    (date, time)
                )
                if cursor.fetchone()[0] > 0:
                    conn.rollback()
                    raise ValueError(f"An appointment is already booked for {date} at {time}.")

                cursor.execute(
                    "INSERT INTO Appointments (customer_id, service_type, date, time, status) VALUES (?, ?, ?, ?, 'Pending')",
                    (customer_id, service_type, date, time)
                )
                app_id = cursor.lastrowid
                
                # Fetch the customer name for the Appointment model
                cursor.execute("SELECT name FROM Customers WHERE id = ?", (customer_id,))
                cust_row = cursor.fetchone()
                customer_name = cust_row[0] if cust_row else "Unknown"
                conn.commit()
                return Appointment(app_id, customer_id, customer_name, service_type, date, time, 'Pending')
            except sqlite3.IntegrityError:
                conn.rollback()
                raise ValueError(f"An appointment is already booked for {date} at {time}.")
            except Exception:
                conn.rollback()
                raise

    def get_all_appointments(self) -> List[Appointment]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.id, a.customer_id, c.name, a.service_type, a.date, a.time, a.status 
                FROM Appointments a
                JOIN Customers c ON a.customer_id = c.id
                ORDER BY a.date, a.time
            ''')
            rows = cursor.fetchall()
            return [Appointment(*row) for row in rows]

    def get_appointments_by_customer(self, customer_id: int) -> List[Appointment]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.id, a.customer_id, c.name, a.service_type, a.date, a.time, a.status 
                FROM Appointments a
                JOIN Customers c ON a.customer_id = c.id
                WHERE a.customer_id = ?
                ORDER BY a.date, a.time
            ''', (customer_id,))
            rows = cursor.fetchall()
            return [Appointment(*row) for row in rows]

    def get_appointment_by_id(self, appointment_id: int) -> Optional[Appointment]:
        """Retrieve an appointment by its ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.id, a.customer_id, c.name, a.service_type, a.date, a.time, a.status 
                FROM Appointments a
                JOIN Customers c ON a.customer_id = c.id
                WHERE a.id = ?
            ''', (appointment_id,))
            row = cursor.fetchone()
            if row:
                return Appointment(*row)
        return None

    def update_appointment_status(self, appointment_id: int, new_status: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Appointments SET status = ? WHERE id = ?", (new_status, appointment_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete_appointment(self, appointment_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Appointments WHERE id = ?", (appointment_id,))
            conn.commit()

    def reschedule_appointment(self, appointment_id: int, new_date: str, new_time: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            try:
                cursor.execute("SELECT id, status FROM Appointments WHERE id = ?", (appointment_id,))
                app_row = cursor.fetchone()
                if not app_row:
                    conn.rollback()
                    return False
                if app_row[1] == "Cancelled":
                    conn.rollback()
                    raise ValueError("Cannot reschedule an appointment that has already been cancelled.")

                cursor.execute(
                    "SELECT COUNT(*) FROM Appointments WHERE date = ? AND time = ? AND status != 'Cancelled' AND id != ?",
                    (new_date, new_time, appointment_id)
                )
                if cursor.fetchone()[0] > 0:
                    conn.rollback()
                    raise ValueError(f"An appointment is already booked for {new_date} at {new_time}.")

                cursor.execute(
                    "UPDATE Appointments SET date = ?, time = ?, status = 'Pending' WHERE id = ?",
                    (new_date, new_time, appointment_id)
                )
                rc = cursor.rowcount > 0
                conn.commit()
                return rc
            except sqlite3.IntegrityError:
                conn.rollback()
                raise ValueError(f"An appointment is already booked for {new_date} at {new_time}.")
            except Exception:
                conn.rollback()
                raise

    # --- Invoice Methods ---

    def create_invoice(self, customer_id: int, amount: float, date: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO Invoices (customer_id, amount, date) VALUES (?, ?, ?)", (customer_id, amount, date))
            conn.commit()

    def get_all_invoices(self) -> List[Invoice]:
        """Retrieve all invoices across all customers."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, customer_id, amount, date FROM Invoices")
            rows = cursor.fetchall()
            return [Invoice(*row) for row in rows]

    def get_invoices_by_customer(self, customer_id: int) -> List[Invoice]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, customer_id, amount, date FROM Invoices WHERE customer_id = ?", (customer_id,))
            rows = cursor.fetchall()
            return [Invoice(*row) for row in rows]

    # --- Lead Methods ---

    def add_lead(self, name: str, phone: str, source: str, notes: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO Leads (name, phone, source, notes) VALUES (?, ?, ?, ?)", (name, phone, source, notes))
            conn.commit()

    def get_all_leads(self) -> List[Lead]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, phone, source, status, notes FROM Leads")
            rows = cursor.fetchall()
            return [Lead(*row) for row in rows]

    def update_lead_status(self, lead_id: int, status: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Leads SET status = ? WHERE id = ?", (status, lead_id))
            conn.commit()
            
    def convert_lead(self, lead_id: int, email: str, password_hash: str, dob: str, address: str, id_number: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, phone FROM Leads WHERE id = ?", (lead_id,))
            lead = cursor.fetchone()
            if not lead: 
                raise ValueError("Lead not found")
            
            try:
                cursor.execute("INSERT INTO Customers (name, phone, email, password, dob, address, id_number) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                               (lead[0], lead[1], email, password_hash, dob, address, id_number))
            except sqlite3.IntegrityError:
                raise ValueError(f"Customer with email {email} already exists.")
            
            cursor.execute("UPDATE Leads SET status = 'Converted' WHERE id = ?", (lead_id,))
            conn.commit()

    # --- Chat Session Methods (Multi-Process Concurrency) ---

    def save_chat_session(self, session_dict: Dict[str, Any]):
        """Persist or update conversation session in SQLite."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ChatSessions (
                    session_id, state, language, claimed_name, claimed_date,
                    candidate_customer_json, clarification_candidates_json,
                    pending_cancellation_id, pending_reschedule_id,
                    pending_booking_date, pending_booking_time, pending_booking_service,
                    registration_data_json, registration_step,
                    failed_attempts, verified, history_json, last_activity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state = excluded.state,
                    language = excluded.language,
                    claimed_name = excluded.claimed_name,
                    claimed_date = excluded.claimed_date,
                    candidate_customer_json = excluded.candidate_customer_json,
                    clarification_candidates_json = excluded.clarification_candidates_json,
                    pending_cancellation_id = excluded.pending_cancellation_id,
                    pending_reschedule_id = excluded.pending_reschedule_id,
                    pending_booking_date = excluded.pending_booking_date,
                    pending_booking_time = excluded.pending_booking_time,
                    pending_booking_service = excluded.pending_booking_service,
                    registration_data_json = excluded.registration_data_json,
                    registration_step = excluded.registration_step,
                    failed_attempts = excluded.failed_attempts,
                    verified = excluded.verified,
                    history_json = excluded.history_json,
                    last_activity = excluded.last_activity
            ''', (
                session_dict["session_id"],
                session_dict.get("state", "INIT"),
                session_dict.get("language", "en"),
                session_dict.get("claimed_name"),
                session_dict.get("claimed_date"),
                json.dumps(session_dict.get("candidate_customer")),
                json.dumps(session_dict.get("clarification_candidates", [])),
                session_dict.get("pending_cancellation_id"),
                session_dict.get("pending_reschedule_id"),
                session_dict.get("pending_booking_date"),
                session_dict.get("pending_booking_time"),
                session_dict.get("pending_booking_service"),
                json.dumps(session_dict.get("registration_data", {})),
                session_dict.get("registration_step"),
                session_dict.get("failed_attempts", 0),
                1 if session_dict.get("verified") else 0,
                json.dumps(session_dict.get("history", [])),
                session_dict.get("last_activity", time.time())
            ))
            conn.commit()

    def get_chat_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored conversation session from SQLite."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT session_id, state, language, claimed_name, claimed_date,
                       candidate_customer_json, clarification_candidates_json,
                       pending_cancellation_id, pending_reschedule_id,
                       pending_booking_date, pending_booking_time, pending_booking_service,
                       registration_data_json, registration_step,
                       failed_attempts, verified, history_json, last_activity
                FROM ChatSessions WHERE session_id = ?
            ''', (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "session_id": row[0],
                "state": row[1],
                "language": row[2] or "en",
                "claimed_name": row[3],
                "claimed_date": row[4],
                "candidate_customer": json.loads(row[5]) if row[5] else None,
                "clarification_candidates": json.loads(row[6]) if row[6] else [],
                "pending_cancellation_id": row[7],
                "pending_reschedule_id": row[8],
                "pending_booking_date": row[9],
                "pending_booking_time": row[10],
                "pending_booking_service": row[11],
                "registration_data": json.loads(row[12]) if row[12] else {},
                "registration_step": row[13],
                "failed_attempts": row[14],
                "verified": bool(row[15]),
                "history": json.loads(row[16]) if row[16] else [],
                "last_activity": row[17]
            }

    def delete_chat_session(self, session_id: str):
        """Delete session from SQLite."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ChatSessions WHERE session_id = ?", (session_id,))
            conn.commit()

    def cleanup_stale_chat_sessions(self, ttl_seconds: int = 3600):
        """Purge sessions inactive beyond TTL."""
        threshold = time.time() - ttl_seconds
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ChatSessions WHERE last_activity < ?", (threshold,))
            conn.commit()

    # --- Customer Verification Lockout Methods (Brute Force Protection) ---

    def get_customer_lockout(self, customer_id: int) -> Tuple[int, float]:
        """Returns (failed_attempts, locked_until)."""
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT failed_attempts, locked_until FROM CustomerVerificationLocks WHERE customer_id = ?",
                (customer_id,)
            )
            row = cursor.fetchone()
            if row:
                failed_attempts, locked_until = row[0], row[1]
                if locked_until > 0 and now >= locked_until:
                    # Lockout expired, reset
                    cursor.execute(
                        "UPDATE CustomerVerificationLocks SET failed_attempts = 0, locked_until = 0 WHERE customer_id = ?",
                        (customer_id,)
                    )
                    conn.commit()
                    return (0, 0.0)
                return (failed_attempts, locked_until)
            return (0, 0.0)

    def record_failed_verification_attempt(self, customer_id: int, max_attempts: int = 3, lockout_duration: int = 900) -> Tuple[int, bool, float]:
        """
        Increments failed verification attempts atomically in database.
        Returns (current_failed_attempts, is_locked, locked_until).
        """
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            try:
                cursor.execute(
                    "SELECT failed_attempts, locked_until FROM CustomerVerificationLocks WHERE customer_id = ?",
                    (customer_id,)
                )
                row = cursor.fetchone()
                if row:
                    prev_fails, locked_until = row[0], row[1]
                    if locked_until > 0 and now >= locked_until:
                        prev_fails = 0
                        locked_until = 0.0
                    new_fails = prev_fails + 1
                else:
                    new_fails = 1
                    locked_until = 0.0

                is_locked = False
                if new_fails >= max_attempts:
                    locked_until = now + lockout_duration
                    is_locked = True

                cursor.execute('''
                    INSERT INTO CustomerVerificationLocks (customer_id, failed_attempts, locked_until, last_attempt_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(customer_id) DO UPDATE SET
                        failed_attempts = excluded.failed_attempts,
                        locked_until = excluded.locked_until,
                        last_attempt_at = excluded.last_attempt_at
                ''', (customer_id, new_fails, locked_until, now))
                conn.commit()
                return (new_fails, is_locked, locked_until)
            except Exception:
                conn.rollback()
                raise

    def clear_customer_lockout(self, customer_id: int):
        """Resets failed verification attempts and lockout on successful verification."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE CustomerVerificationLocks SET failed_attempts = 0, locked_until = 0 WHERE customer_id = ?",
                (customer_id,)
            )
            conn.commit()
