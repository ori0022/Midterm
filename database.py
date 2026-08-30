import sqlite3
from typing import List, Optional
from models import Customer, Appointment, Invoice, Lead

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
            
            # Ensure id_number column exists in Customers
            cursor.execute("PRAGMA table_info(Customers)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'id_number' not in columns:
                cursor.execute("ALTER TABLE Customers ADD COLUMN id_number TEXT")
                conn.commit()

            conn.commit()

    # --- Customer Methods ---

    def get_customer_by_auth(self, email: str, password_hash: str) -> Optional[Customer]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, phone, email, dob, address, id_number FROM Customers WHERE email = ? AND password = ?", (email, password_hash))
            row = cursor.fetchone()
            if row:
                return Customer(*row)
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
        if self.check_collision(date, time):
            raise ValueError(f"An appointment is already booked for {date} at {time}.")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Appointments (customer_id, service_type, date, time, status) VALUES (?, ?, ?, ?, 'Pending')",
                (customer_id, service_type, date, time)
            )
            conn.commit()
            
            # Fetch the customer name for the Appointment model
            cursor.execute("SELECT name FROM Customers WHERE id = ?", (customer_id,))
            customer_name = cursor.fetchone()[0]
            
            return Appointment(cursor.lastrowid, customer_id, customer_name, service_type, date, time, 'Pending')

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

    def update_appointment_status(self, appointment_id: int, new_status: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Appointments SET status = ? WHERE id = ?", (new_status, appointment_id))
            conn.commit()

    def delete_appointment(self, appointment_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Appointments WHERE id = ?", (appointment_id,))
            conn.commit()

    def reschedule_appointment(self, appointment_id: int, new_date: str, new_time: str) -> bool:
        if self.check_collision(new_date, new_time):
            raise ValueError(f"An appointment is already booked for {new_date} at {new_time}.")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE Appointments SET date = ?, time = ?, status = 'Pending' WHERE id = ?",
                (new_date, new_time, appointment_id)
            )
            conn.commit()
            return True

    # --- Invoice Methods ---

    def create_invoice(self, customer_id: int, amount: float, date: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO Invoices (customer_id, amount, date) VALUES (?, ?, ?)", (customer_id, amount, date))
            conn.commit()

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
