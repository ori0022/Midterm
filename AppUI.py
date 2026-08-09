import tkinter as tk
from tkinter import ttk
from database import DatabaseManager

SERVICES = [
    "New Account Opening",
    "Mortgage Consultation",
    "Personal Loan Application",
    "Investment Planning"
]

STATUSES = ["Pending", "Confirmed", "Completed", "Cancelled"]

class AppUI(tk.Tk):
    def __init__(self, db_manager: DatabaseManager, start_role: str = "selection"):
        super().__init__()
        self.db = db_manager
        self.start_role = start_role
        self.title('"Haovdim" Bank Appointment Management')
        self.geometry("800x600")
        
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        
        style.configure("TButton", padding=6, relief="flat", background="#0052cc", foreground="white", font=("Helvetica", 10, "bold"))
        style.map("TButton", background=[('active', '#0043a6')])
        style.configure("TLabel", font=("Helvetica", 11))
        style.configure("Header.TLabel", font=("Helvetica", 16, "bold"), padding=10)
        
        self.current_frame = None
        if self.start_role == "customer":
            from CustomerLoginUIFrame import CustomerLoginUIFrame
            self.switch_frame(CustomerLoginUIFrame)
        elif self.start_role == "admin":
            from AdminUIFrame import AdminUIFrame
            self.switch_frame(AdminUIFrame)
        else:
            self.show_role_selection()

    def switch_frame(self, frame_class, *args):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = frame_class(self, *args)
        self.current_frame.pack(fill=tk.BOTH, expand=True)

    def show_role_selection(self):
        from RoleSelectionUIFrame import RoleSelectionUIFrame
        self.switch_frame(RoleSelectionUIFrame)
