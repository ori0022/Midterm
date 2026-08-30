import sqlite3
from database import DatabaseManager

def clear_database():
    """Clears all customer, appointment, invoice, and lead records, leaving all tables completely empty."""
    db = DatabaseManager()
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
    print("Database reset successfully! All customer and appointment lists are now completely empty.")

if __name__ == "__main__":
    clear_database()
