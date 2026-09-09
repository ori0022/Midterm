import sqlite3
from typing import Optional
from database import DatabaseManager
from auth_utils import hash_password

def clear_database(db: Optional[DatabaseManager] = None):
    """Clears all customer, appointment, invoice, and lead records, leaving all tables completely empty."""
    db = db or DatabaseManager()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Invoices")
        cursor.execute("DELETE FROM Appointments")
        cursor.execute("DELETE FROM Customers")
        cursor.execute("DELETE FROM Leads")
        try:
            cursor.execute("DELETE FROM sqlite_sequence")
        except Exception:
            pass
        conn.commit()
    print("Database cleared successfully! All customer, appointment, invoice, and lead tables are empty.")

def seed_database(db: Optional[DatabaseManager] = None):
    """Populates the database with realistic demo data (>= 5 records for all entities)."""
    db = db or DatabaseManager()
    
    pw_hash = hash_password("password123")
    
    # 1. Customers (with 9-digit Teudat Zehut and bcrypt password hashes)
    c1 = db.create_customer("Dana Shavit", "0541112233", "dana.shavit@bank.com", "1995-05-12", pw_hash, "Tel Aviv, Rothschild 45", "123456789")
    c2 = db.create_customer("David Cohen", "0523334455", "david.cohen@bank.com", "1988-11-20", pw_hash, "Jerusalem, Jaffa 12", "987654321")
    c3 = db.create_customer("David Levi", "0504445566", "david.levi@bank.com", "1990-03-15", pw_hash, "Haifa, Herzl 78", "555666777")
    c4 = db.create_customer("Tamar Ben-David", "0537778899", "tamar.bd@bank.com", "1984-02-28", pw_hash, "Rishon LeZion, Jabotinsky 5", "444333222")
    c5 = db.create_customer("Yossi Mizrahi", "0589990011", "yossi.m@bank.com", "1978-06-22", pw_hash, "Herzliya, Sokolov 20", "222333444")
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # 2. Appointments (at least 5 records across statuses)
        cursor.execute("INSERT INTO Appointments (customer_id, service_type, date, time, status) VALUES (?, ?, ?, ?, ?)", 
                       (c1.id, "Investment Planning", "2027-01-19", "19:00", "Confirmed"))
        cursor.execute("INSERT INTO Appointments (customer_id, service_type, date, time, status) VALUES (?, ?, ?, ?, ?)", 
                       (c2.id, "Mortgage Consultation", "2027-02-10", "10:30", "Pending"))
        cursor.execute("INSERT INTO Appointments (customer_id, service_type, date, time, status) VALUES (?, ?, ?, ?, ?)", 
                       (c3.id, "New Account Opening", "2027-02-15", "14:00", "Confirmed"))
        cursor.execute("INSERT INTO Appointments (customer_id, service_type, date, time, status) VALUES (?, ?, ?, ?, ?)", 
                       (c4.id, "Personal Loan Application", "2027-03-01", "11:00", "Confirmed"))
        cursor.execute("INSERT INTO Appointments (customer_id, service_type, date, time, status) VALUES (?, ?, ?, ?, ?)", 
                       (c1.id, "Account Review", "2026-12-01", "10:00", "Completed"))
        
        # 3. Invoices (at least 5 records)
        invoices = [
            (c1.id, 250.0, "2027-01-10"),
            (c2.id, 1200.0, "2027-01-12"),
            (c3.id, 150.0, "2027-01-15"),
            (c4.id, 450.0, "2027-01-20"),
            (c5.id, 300.0, "2027-02-01")
        ]
        for cid, amt, dt in invoices:
            cursor.execute("INSERT INTO Invoices (customer_id, amount, date) VALUES (?, ?, ?)", (cid, amt, dt))
            
        # 4. Leads (at least 5 records)
        leads = [
            ("Noa Golan", "0501112244", "Website Form", "New", "Interested in private wealth management"),
            ("Itamar Katz", "0529988776", "Referral", "Contacted", "Follow up regarding business account"),
            ("Maya Shapira", "0543322110", "Social Media", "New", "Inquired about student checking"),
            ("Oren Shaked", "0534455667", "Walk-in", "In Progress", "Requested loan comparison"),
            ("Gal Cohen", "0587766554", "Phone Call", "New", "Callback scheduled for next week")
        ]
        for name, phone, source, status, notes in leads:
            cursor.execute("INSERT INTO Leads (name, phone, source, status, notes) VALUES (?, ?, ?, ?, ?)", 
                           (name, phone, source, status, notes))
            
        conn.commit()
        
    print("Database seeded successfully with demo records:")
    print("  • 5 Customers (with bcrypt hashed passwords & 9-digit IDs)")
    print("  • 5 Appointments")
    print("  • 5 Invoices")
    print("  • 5 Leads")

if __name__ == "__main__":
    clear_database()
    seed_database()
