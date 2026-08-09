import sys
from database import DatabaseManager
from AppUI import AppUI

def main():
    # Initialize the database
    db_manager = DatabaseManager()
    
    # Check command line arguments for specific roles
    start_role = "selection"
    if len(sys.argv) > 1:
        role = sys.argv[1].lower()
        if role == "--customer":
            start_role = "customer"
        elif role == "--admin":
            start_role = "admin"

    # Start the Tkinter application
    app = AppUI(db_manager, start_role)
    app.mainloop()

if __name__ == "__main__":
    main()
