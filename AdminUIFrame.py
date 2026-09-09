import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING
from AppUI import SERVICES, STATUSES

if TYPE_CHECKING:
    from AppUI import AppUI

class AdminUIFrame(ttk.Frame):
    def __init__(self, parent: 'AppUI'):
        super().__init__(parent)
        self.parent = parent
        
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=10, padx=20)
        ttk.Label(header_frame, text="Bank Staff Dashboard", style="Header.TLabel").pack(side=tk.LEFT)
        if self.parent.start_role == "selection":
            ttk.Button(header_frame, text="Back to Home", command=self.parent.show_role_selection).pack(side=tk.RIGHT)
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.apps_tab = ttk.Frame(self.notebook)
        self.customers_tab = ttk.Frame(self.notebook)
        self.leads_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.apps_tab, text="Appointments")
        self.notebook.add(self.customers_tab, text="Customers")
        self.notebook.add(self.leads_tab, text="Leads")
        
        self.setup_apps_tab()
        self.setup_customers_tab()
        self.setup_leads_tab()

    # --- Appointments Tab ---
    def setup_apps_tab(self):
        # Filter Frame
        filter_frame = ttk.Frame(self.apps_tab)
        filter_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(filter_frame, text="Filter Date:").pack(side=tk.LEFT, padx=5)
        self.filter_date_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.filter_date_var, state="readonly", width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="📅", width=3, command=self.pick_filter_date).pack(side=tk.LEFT, padx=2)
        ttk.Button(filter_frame, text="X", width=2, command=lambda: self.filter_date_var.set("")).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(filter_frame, text="Filter Service:").pack(side=tk.LEFT, padx=5)
        self.filter_service_var = tk.StringVar()
        cb = ttk.Combobox(filter_frame, textvariable=self.filter_service_var, values=["All"] + SERVICES, state="readonly", width=20)
        cb.current(0)
        cb.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filter_frame, text="Apply Filters", command=self.refresh_apps).pack(side=tk.LEFT, padx=10)
        ttk.Button(filter_frame, text="Clear Filters", command=self.clear_app_filters).pack(side=tk.LEFT)
        
        # Treeview
        columns = ("ID", "Customer", "Service", "Date", "Time", "Status")
        self.app_tree = ttk.Treeview(self.apps_tab, columns=columns, show="headings")
        for col in columns:
            self.app_tree.heading(col, text=col)
            self.app_tree.column(col, width=120)
        self.app_tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Action Buttons
        action_frame = ttk.Frame(self.apps_tab)
        action_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(action_frame, text="Change Status:").pack(side=tk.LEFT, padx=5)
        self.status_var = tk.StringVar(value=STATUSES[1])
        ttk.Combobox(action_frame, textvariable=self.status_var, values=STATUSES, state="readonly", width=12).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="Update Status", command=self.update_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Generate Invoice", command=self.generate_invoice).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Delete Appointment", command=self.delete_appointment).pack(side=tk.LEFT, padx=20)
        
        self.refresh_apps()

    def pick_filter_date(self):
        from datepicker import DatePicker
        DatePicker(self, self.filter_date_var, title="Filter by Date")

    def clear_app_filters(self):
        self.filter_date_var.set("")
        self.filter_service_var.set("All")
        self.refresh_apps()

    def refresh_apps(self):
        for row in self.app_tree.get_children():
            self.app_tree.delete(row)
            
        apps = self.parent.db.get_all_appointments()
        f_date = self.filter_date_var.get().strip()
        f_srv = self.filter_service_var.get()
        
        for a in apps:
            if f_date and a.date != f_date: continue
            if f_srv != "All" and a.service_type != f_srv: continue
            self.app_tree.insert("", tk.END, values=(a.id, a.customer_name, a.service_type, a.date, a.time, a.status))

    def update_status(self):
        selected = self.app_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment.")
            return
        app_id = self.app_tree.item(selected[0])['values'][0]
        new_status = self.status_var.get()
        self.parent.db.update_appointment_status(app_id, new_status)
        self.refresh_apps()
        messagebox.showinfo("Success", f"Appointment status updated to {new_status}.")
        
    def generate_invoice(self):
        selected = self.app_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment.")
            return
        app_id = self.app_tree.item(selected[0])['values'][0]
        
        apps = self.parent.db.get_all_appointments()
        app = next((a for a in apps if a.id == app_id), None)
        if not app: return
        
        import tkinter.simpledialog as sd
        from datetime import date
        amount = sd.askfloat("Invoice Amount", "Enter invoice amount ($):", minvalue=0.0)
        if amount is not None:
            self.parent.db.create_invoice(app.customer_id, amount, date.today().strftime("%Y-%m-%d"))
            messagebox.showinfo("Success", "Invoice generated successfully!")

    def delete_appointment(self):
        selected = self.app_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment.")
            return
        app_id = self.app_tree.item(selected[0])['values'][0]
        if messagebox.askyesno("Confirm", "Are you sure you want to permanently delete this appointment?"):
            self.parent.db.delete_appointment(app_id)
            self.refresh_apps()
            messagebox.showinfo("Success", "Appointment deleted.")

    # --- Customers Tab ---
    def setup_customers_tab(self):
        columns = ("ID", "National ID", "Name", "Phone", "Email", "DOB", "Address")
        self.cust_tree = ttk.Treeview(self.customers_tab, columns=columns, show="headings")
        for col in columns:
            self.cust_tree.heading(col, text=col)
            self.cust_tree.column(col, width=100)
        self.cust_tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        action_frame = ttk.Frame(self.customers_tab)
        action_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(action_frame, text="Refresh", command=self.refresh_customers).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="View History & Invoices", command=self.view_customer_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Delete Customer", command=self.delete_customer).pack(side=tk.LEFT, padx=20)
        
        self.refresh_customers()

    def refresh_customers(self):
        for row in self.cust_tree.get_children():
            self.cust_tree.delete(row)
        for c in self.parent.db.get_all_customers():
            self.cust_tree.insert("", tk.END, values=(c.id, c.id_number or "-", c.name, c.phone, c.email, c.dob, c.address))
            
    def delete_customer(self):
        selected = self.cust_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a customer.")
            return
        cust_id = self.cust_tree.item(selected[0])['values'][0]
        if messagebox.askyesno("Confirm", "Delete customer and ALL their appointments/invoices?"):
            self.parent.db.delete_customer(cust_id)
            self.refresh_customers()
            self.refresh_apps()
            messagebox.showinfo("Success", "Customer deleted.")
            
    def view_customer_history(self):
        selected = self.cust_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a customer.")
            return
        
        cust_id = self.cust_tree.item(selected[0])['values'][0]
        cust_name = self.cust_tree.item(selected[0])['values'][1]
        
        top = tk.Toplevel(self)
        top.title(f"History for {cust_name}")
        top.geometry("600x400")
        
        nb = ttk.Notebook(top)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        f_apps = ttk.Frame(nb)
        f_inv = ttk.Frame(nb)
        nb.add(f_apps, text="Appointments")
        nb.add(f_inv, text="Invoices")
        
        # Apps tree
        a_tree = ttk.Treeview(f_apps, columns=("ID", "Service", "Date", "Time", "Status"), show="headings")
        for c in ("ID", "Service", "Date", "Time", "Status"): a_tree.heading(c, text=c)
        a_tree.pack(fill=tk.BOTH, expand=True)
        for a in self.parent.db.get_appointments_by_customer(cust_id):
            a_tree.insert("", tk.END, values=(a.id, a.service_type, a.date, a.time, a.status))
            
        # Invoices tree
        i_tree = ttk.Treeview(f_inv, columns=("ID", "Amount", "Date"), show="headings")
        for c in ("ID", "Amount", "Date"): i_tree.heading(c, text=c)
        i_tree.pack(fill=tk.BOTH, expand=True)
        for i in self.parent.db.get_invoices_by_customer(cust_id):
            i_tree.insert("", tk.END, values=(i.id, f"${i.amount:.2f}", i.date))

    # --- Leads Tab ---
    def setup_leads_tab(self):
        columns = ("ID", "Name", "Phone", "Source", "Status", "Notes")
        self.leads_tree = ttk.Treeview(self.leads_tab, columns=columns, show="headings")
        for col in columns:
            self.leads_tree.heading(col, text=col)
            self.leads_tree.column(col, width=100)
        self.leads_tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        form_frame = ttk.Frame(self.leads_tab)
        form_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(form_frame, text="Name:").grid(row=0, column=0, padx=2, pady=2, sticky=tk.E)
        self.l_name = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.l_name, width=15).grid(row=0, column=1, padx=2, pady=2)
        
        ttk.Label(form_frame, text="Phone:").grid(row=0, column=2, padx=2, pady=2, sticky=tk.E)
        self.l_phone = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.l_phone, width=15).grid(row=0, column=3, padx=2, pady=2)
        
        ttk.Label(form_frame, text="Source:").grid(row=0, column=4, padx=2, pady=2, sticky=tk.E)
        self.l_source = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.l_source, width=15).grid(row=0, column=5, padx=2, pady=2)
        
        ttk.Label(form_frame, text="Notes:").grid(row=0, column=6, padx=2, pady=2, sticky=tk.E)
        self.l_notes = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.l_notes, width=20).grid(row=0, column=7, padx=2, pady=2)
        
        ttk.Button(form_frame, text="Add Lead", command=self.add_lead).grid(row=0, column=8, padx=5, pady=2)
        
        action_frame = ttk.Frame(self.leads_tab)
        action_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(action_frame, text="Update Status:").pack(side=tk.LEFT, padx=5)
        self.l_status = tk.StringVar(value="In Progress")
        ttk.Combobox(action_frame, textvariable=self.l_status, values=["New", "In Progress", "Converted", "Rejected"], state="readonly", width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Update", command=self.update_lead_status).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="Convert to Customer", command=self.convert_lead).pack(side=tk.LEFT, padx=20)
        ttk.Button(action_frame, text="Refresh", command=self.refresh_leads).pack(side=tk.LEFT, padx=5)
        
        self.refresh_leads()
        
    def refresh_leads(self):
        for row in self.leads_tree.get_children():
            self.leads_tree.delete(row)
        for l in self.parent.db.get_all_leads():
            self.leads_tree.insert("", tk.END, values=(l.id, l.name, l.phone, l.source, l.status, l.notes))
            
    def add_lead(self):
        name = self.l_name.get().strip()
        phone = self.l_phone.get().strip()
        source = self.l_source.get().strip()
        notes = self.l_notes.get().strip()
        
        if not name or not phone or not source:
            messagebox.showerror("Error", "Name, phone, and source are required.")
            return
            
        self.parent.db.add_lead(name, phone, source, notes)
        self.refresh_leads()
        
        self.l_name.set("")
        self.l_phone.set("")
        self.l_source.set("")
        self.l_notes.set("")
        messagebox.showinfo("Success", "Lead added.")
        
    def update_lead_status(self):
        selected = self.leads_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a lead.")
            return
        l_id = self.leads_tree.item(selected[0])['values'][0]
        st = self.l_status.get()
        self.parent.db.update_lead_status(l_id, st)
        self.refresh_leads()
        messagebox.showinfo("Success", "Lead status updated.")
        
    def convert_lead(self):
        selected = self.leads_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a lead to convert.")
            return
        
        l_id = self.leads_tree.item(selected[0])['values'][0]
        l_st = self.leads_tree.item(selected[0])['values'][4]
        
        if l_st == "Converted":
            messagebox.showerror("Error", "This lead is already converted.")
            return
            
        top = tk.Toplevel(self)
        top.title("Convert Lead to Customer")
        
        ttk.Label(top, text="Email:").grid(row=0, column=0, padx=5, pady=5)
        em_var = tk.StringVar()
        ttk.Entry(top, textvariable=em_var).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(top, text="Password:").grid(row=1, column=0, padx=5, pady=5)
        pw_var = tk.StringVar()
        ttk.Entry(top, textvariable=pw_var, show="*").grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(top, text="DOB (YYYY-MM-DD):").grid(row=2, column=0, padx=5, pady=5)
        dob_var = tk.StringVar()
        ttk.Entry(top, textvariable=dob_var).grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(top, text="Address:").grid(row=3, column=0, padx=5, pady=5)
        ad_var = tk.StringVar()
        ttk.Entry(top, textvariable=ad_var).grid(row=3, column=1, padx=5, pady=5)
        
        ttk.Label(top, text="ID Number (9 digits):").grid(row=4, column=0, padx=5, pady=5)
        id_num_var = tk.StringVar()
        ttk.Entry(top, textvariable=id_num_var).grid(row=4, column=1, padx=5, pady=5)

        def save():
            import hashlib
            em = em_var.get().strip()
            pw = pw_var.get().strip()
            dob = dob_var.get().strip()
            ad = ad_var.get().strip()
            id_num = id_num_var.get().strip()
            
            if not em or "@" not in em or not pw or not dob or not ad:
                messagebox.showerror("Error", "All fields are required and valid.")
                return
                
            pwd_hash = hashlib.sha256(pw.encode()).hexdigest()
            try:
                self.parent.db.convert_lead(l_id, em, pwd_hash, dob, ad, id_num or None)
                messagebox.showinfo("Success", "Lead converted to Customer!")
                self.refresh_leads()
                self.refresh_customers()
                top.destroy()
            except ValueError as e:
                messagebox.showerror("Error", str(e))
                
        ttk.Button(top, text="Save Customer", command=save).grid(row=5, column=0, columnspan=2, pady=10)
