# Haovdim Bank Appointment Management System

This is a Python-based GUI application built for managing appointments at "Haovdim" Bank. It is built using Python's standard `tkinter` library and uses SQLite for persistent storage.

## Prerequisites
- Python 3.7 or higher installed on your system.
- No external Python libraries are required (only standard libraries like `tkinter` and `sqlite3` are used).

## File Structure
- `main.py`: The entry point of the application. It initializes the database and launches the graphical interface.
- `database.py`: Contains the `DatabaseManager` class which handles all interactions with the SQLite database, including creating the schema on the first run.
- `ui.py`: Contains all the `tkinter` classes and layouts for the application (Role Selection, Customer UI, Admin UI).
- `models.py`: Data structures (`dataclass`) for `Customer` and `Appointment` to pass typed data between the database and UI.

## How to Run
1. Open a terminal or command prompt.
2. Navigate to the directory containing these files.
3. Run the following command:
   ```bash
   python main.py
   ```
4. On the first run, the system will automatically create `bank_haovdim.db` in the same directory.

## Features
- **Customer Portal**: Register a new account, book an appointment (with collision detection), view your own appointments, and cancel them.
- **Admin Portal**: View all bank appointments, filter by date or service type, update statuses, or permanently delete records.

## Bonuses Implemented
- **Bonus 1 (Customers & Invoices):** Fully implemented tracking for customers, history viewing, and invoice generation.
- **Bonus 2 (Lead Management):** Fully implemented lead tracking with conversion-to-customer functionality.
