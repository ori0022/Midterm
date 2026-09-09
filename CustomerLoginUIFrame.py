import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from AppUI import AppUI

class CustomerLoginUIFrame(ttk.Frame):
    def __init__(self, parent: 'AppUI'):
        super().__init__(parent)
        self.parent = parent
        
        ttk.Label(self, text="Customer Login", style="Header.TLabel").pack(pady=20)
        
        form_frame = ttk.Frame(self)
        form_frame.pack(pady=10)
        
        ttk.Label(form_frame, text="Email:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
        self.email_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.email_var).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(form_frame, text="Password:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
        self.password_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.password_var, show="*").grid(row=1, column=1, padx=5, pady=5)
        
        self.is_new_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="I am a new customer", variable=self.is_new_var, command=self.toggle_new_fields).grid(row=2, column=0, columnspan=2, pady=10)
        
        self.confirm_lbl = ttk.Label(form_frame, text="Confirm Password:")
        self.confirm_var = tk.StringVar()
        self.confirm_entry = ttk.Entry(form_frame, textvariable=self.confirm_var, show="*")
        
        self.name_lbl = ttk.Label(form_frame, text="Full Name:")
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(form_frame, textvariable=self.name_var)
        
        self.id_number_lbl = ttk.Label(form_frame, text="ID Number (9 digits):")
        self.id_number_var = tk.StringVar()
        self.id_number_entry = ttk.Entry(form_frame, textvariable=self.id_number_var)

        self.phone_lbl = ttk.Label(form_frame, text="Phone Number:")
        self.phone_var = tk.StringVar()
        self.phone_entry = ttk.Entry(form_frame, textvariable=self.phone_var)
        
        self.dob_lbl = ttk.Label(form_frame, text="Date of Birth:")
        self.dob_var = tk.StringVar()
        self.dob_frame = ttk.Frame(form_frame)
        ttk.Entry(self.dob_frame, textvariable=self.dob_var, state="readonly", width=12).pack(side=tk.LEFT)
        ttk.Button(self.dob_frame, text="📅", width=3, command=self.pick_dob).pack(side=tk.LEFT, padx=2)
        
        self.address_lbl = ttk.Label(form_frame, text="Address:")
        self.address_var = tk.StringVar()
        self.address_entry = ttk.Entry(form_frame, textvariable=self.address_var)
        
        ttk.Button(self, text="Login / Register", command=self.process_login).pack(pady=20)
        
        if self.parent.start_role == "selection":
            ttk.Button(self, text="Back", command=self.parent.show_role_selection).pack()

    def toggle_new_fields(self):
        if self.is_new_var.get():
            self.confirm_lbl.grid(row=3, column=0, padx=5, pady=5, sticky=tk.E)
            self.confirm_entry.grid(row=3, column=1, padx=5, pady=5)
            self.name_lbl.grid(row=4, column=0, padx=5, pady=5, sticky=tk.E)
            self.name_entry.grid(row=4, column=1, padx=5, pady=5)
            self.id_number_lbl.grid(row=5, column=0, padx=5, pady=5, sticky=tk.E)
            self.id_number_entry.grid(row=5, column=1, padx=5, pady=5)
            self.phone_lbl.grid(row=6, column=0, padx=5, pady=5, sticky=tk.E)
            self.phone_entry.grid(row=6, column=1, padx=5, pady=5)
            self.dob_lbl.grid(row=7, column=0, padx=5, pady=5, sticky=tk.E)
            self.dob_frame.grid(row=7, column=1, padx=5, pady=5, sticky=tk.W)
            self.address_lbl.grid(row=8, column=0, padx=5, pady=5, sticky=tk.E)
            self.address_entry.grid(row=8, column=1, padx=5, pady=5)
        else:
            self.confirm_lbl.grid_forget()
            self.confirm_entry.grid_forget()
            self.name_lbl.grid_forget()
            self.name_entry.grid_forget()
            self.id_number_lbl.grid_forget()
            self.id_number_entry.grid_forget()
            self.phone_lbl.grid_forget()
            self.phone_entry.grid_forget()
            self.dob_lbl.grid_forget()
            self.dob_frame.grid_forget()
            self.address_lbl.grid_forget()
            self.address_entry.grid_forget()

    def pick_dob(self):
        from datepicker import DatePicker
        from datetime import date
        min_date = date(1900, 1, 1)
        max_date = date.today()
        DatePicker(self, self.dob_var, min_date=min_date, max_date=max_date, title="Select DOB")

    def process_login(self):
        from auth_utils import hash_password
        email = self.email_var.get().strip()
        password = self.password_var.get().strip()
        
        if not email or "@" not in email:
            messagebox.showerror("Error", "A valid email containing '@' is required.")
            return
        if not password:
            messagebox.showerror("Error", "Password is required.")
            return
            
        if self.is_new_var.get():
            confirm_pwd = self.confirm_var.get().strip()
            name = self.name_var.get().strip()
            id_number = self.id_number_var.get().strip()
            phone = self.phone_var.get().strip()
            dob = self.dob_var.get().strip()
            address = self.address_var.get().strip()
            
            if password != confirm_pwd:
                messagebox.showerror("Error", "Passwords do not match.")
                return
            if len(password) < 8 or not any(c.isupper() for c in password):
                messagebox.showerror("Error", "Password must be at least 8 characters long and contain 1 uppercase letter.")
                return
            if len(name) < 2:
                messagebox.showerror("Error", "Name must be at least 2 letters long.")
                return
            if len(id_number) != 9 or not id_number.isdigit():
                messagebox.showerror("Error", "ID number (Teudat Zehut) must be exactly 9 digits.")
                return
            if len(phone) != 10 or not phone.isdigit():
                messagebox.showerror("Error", "Phone number must be exactly 10 digits.")
                return
            if not dob:
                messagebox.showerror("Error", "Date of Birth is required.")
                return
            if not address:
                messagebox.showerror("Error", "Address is required.")
                return
                
            try:
                password_hash = hash_password(password)
                customer = self.parent.db.create_customer(name, phone, email, dob, password_hash, address, id_number)
                messagebox.showinfo("Success", "Registration successful!")
                from CustomerUIFrame import CustomerUIFrame
                self.parent.switch_frame(CustomerUIFrame, customer)
            except ValueError as e:
                messagebox.showerror("Error", str(e))
        else:
            customer = self.parent.db.get_customer_by_auth(email, password)
            if customer:
                from CustomerUIFrame import CustomerUIFrame
                self.parent.switch_frame(CustomerUIFrame, customer)
            else:
                messagebox.showerror("Error", "Invalid email or password.")
