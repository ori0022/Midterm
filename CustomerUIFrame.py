import tkinter as tk
from tkinter import ttk, messagebox
from models import Customer
from typing import TYPE_CHECKING
from AppUI import SERVICES

if TYPE_CHECKING:
    from AppUI import AppUI

class CustomerUIFrame(ttk.Frame):
    def __init__(self, parent: 'AppUI', customer: Customer):
        super().__init__(parent)
        self.parent = parent
        self.customer = customer
        
        ttk.Label(self, text=f"Welcome, {customer.name}", style="Header.TLabel").pack(pady=10)
        
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.book_tab = ttk.Frame(notebook)
        self.my_apps_tab = ttk.Frame(notebook)
        
        notebook.add(self.book_tab, text="Book Appointment")
        notebook.add(self.my_apps_tab, text="My Appointments")
        
        self.setup_book_tab()
        self.setup_my_apps_tab()
        
        if self.parent.start_role == "selection":
            ttk.Button(self, text="Logout", command=self.parent.show_role_selection).pack(pady=10)
        else:
            def logout():
                from CustomerLoginUIFrame import CustomerLoginUIFrame
                self.parent.switch_frame(CustomerLoginUIFrame)
            ttk.Button(self, text="Logout", command=logout).pack(pady=10)

    def setup_book_tab(self):
        form = ttk.Frame(self.book_tab)
        form.pack(pady=20)
        
        ttk.Label(form, text="Service Type:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
        self.service_var = tk.StringVar(value=SERVICES[0])
        ttk.Combobox(form, textvariable=self.service_var, values=SERVICES, state="readonly").grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(form, text="Date:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
        self.date_var = tk.StringVar()
        self.date_var.trace_add("write", self.update_available_times)
        date_frame = ttk.Frame(form)
        date_frame.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(date_frame, textvariable=self.date_var, state="readonly", width=12).pack(side=tk.LEFT)
        ttk.Button(date_frame, text="📅", width=3, command=self.pick_appointment_date).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(form, text="Time:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.E)
        self.time_var = tk.StringVar()
        self.cb_time = ttk.Combobox(form, textvariable=self.time_var, state="readonly", width=10)
        self.cb_time.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Button(form, text="Book Appointment", command=self.book_appointment).grid(row=3, column=0, columnspan=2, pady=20)

    def update_available_times(self, *args):
        date_selected = self.date_var.get().strip()
        if not date_selected:
            return
            
        all_times = [f"{str(h).zfill(2)}:{m}" for h in range(9, 17) for m in ("00", "30")] + ["17:00"]
        booked_times = self.parent.db.get_booked_times_for_date(date_selected)
        
        available = [t for t in all_times if t not in booked_times]
        self.cb_time['values'] = available
        if available:
            self.cb_time.current(0)
        else:
            self.time_var.set("")

    def pick_appointment_date(self):
        from datepicker import DatePicker
        from datetime import date, timedelta
        min_date = date.today() + timedelta(days=1)
        DatePicker(self, self.date_var, min_date=min_date, title="Select Date")

    def book_appointment(self):
        service = self.service_var.get()
        date = self.date_var.get().strip()
        time = self.time_var.get().strip()
        
        if not date or not time:
            messagebox.showerror("Error", "Date and Time are required.")
            return
            
        try:
            self.parent.db.create_appointment(self.customer.id, service, date, time)
            messagebox.showinfo("Success", "Appointment booked successfully!")
            self.date_var.set("")
            self.time_var.set("")
            self.refresh_my_apps()
        except ValueError as e:
            messagebox.showerror("Booking Collision", str(e))

    def setup_my_apps_tab(self):
        columns = ("ID", "Service", "Date", "Time", "Status")
        self.tree = ttk.Treeview(self.my_apps_tab, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        btn_frame = ttk.Frame(self.my_apps_tab)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="Cancel Selected", command=self.cancel_appointment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_my_apps).pack(side=tk.LEFT, padx=5)
        
        self.refresh_my_apps()

    def refresh_my_apps(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        
        apps = self.parent.db.get_appointments_by_customer(self.customer.id)
        for a in apps:
            self.tree.insert("", tk.END, values=(a.id, a.service_type, a.date, a.time, a.status))

    def cancel_appointment(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment to cancel.")
            return
        
        item = self.tree.item(selected[0])
        app_id = item['values'][0]
        status = item['values'][4]
        
        if status in ["Completed", "Cancelled"]:
            messagebox.showerror("Error", f"Cannot cancel an appointment that is {status}.")
            return
            
        if messagebox.askyesno("Confirm", "Are you sure you want to cancel this appointment?"):
            self.parent.db.update_appointment_status(app_id, "Cancelled")
            self.refresh_my_apps()
            messagebox.showinfo("Success", "Appointment cancelled.")
