import tkinter as tk
from tkinter import ttk
import calendar
from datetime import datetime, date, timedelta

class DatePicker(tk.Toplevel):
    def __init__(self, parent, target_var, min_date=None, max_date=None, title="Select Date"):
        super().__init__(parent)
        self.title(title)
        self.geometry("300x250")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.target_var = target_var
        
        # min_date and max_date should be datetime.date objects
        self.min_date = min_date
        self.max_date = max_date
        
        # Start at today, or min_date if today is less than min_date
        today = date.today()
        start_date = today
        if self.min_date and start_date < self.min_date:
            start_date = self.min_date
        if self.max_date and start_date > self.max_date:
            start_date = self.max_date
            
        self.current_year = start_date.year
        self.current_month = start_date.month
        
        self.setup_ui()
        self.update_calendar()
        
    def setup_ui(self):
        # Header for Month/Year and navigation
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(header_frame, text="<<", width=3, command=self.prev_year).pack(side=tk.LEFT, padx=2)
        ttk.Button(header_frame, text="<", width=3, command=self.prev_month).pack(side=tk.LEFT, padx=2)
        
        self.month_year_lbl = ttk.Label(header_frame, text="", font=("Helvetica", 12, "bold"), anchor="center")
        self.month_year_lbl.pack(side=tk.LEFT, expand=True)
        
        ttk.Button(header_frame, text=">>", width=3, command=self.next_year).pack(side=tk.RIGHT, padx=2)
        ttk.Button(header_frame, text=">", width=3, command=self.next_month).pack(side=tk.RIGHT, padx=2)
        
        # Days of week header
        days_frame = ttk.Frame(self)
        days_frame.pack(fill=tk.X, padx=10)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days):
            lbl = ttk.Label(days_frame, text=day, width=4, anchor=tk.CENTER)
            lbl.grid(row=0, column=i, padx=1, pady=5)
            
        # Calendar grid
        self.cal_frame = ttk.Frame(self)
        self.cal_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
    def update_calendar(self):
        # Clear existing buttons
        for widget in self.cal_frame.winfo_children():
            widget.destroy()
            
        # Update header
        month_name = calendar.month_name[self.current_month]
        self.month_year_lbl.config(text=f"{month_name} {self.current_year}")
        
        # Get calendar data
        cal = calendar.monthcalendar(self.current_year, self.current_month)
        
        for row_idx, week in enumerate(cal):
            for col_idx, day in enumerate(week):
                if day != 0:
                    btn_date = date(self.current_year, self.current_month, day)
                    
                    # Check constraints
                    state = tk.NORMAL
                    if self.min_date and btn_date < self.min_date:
                        state = tk.DISABLED
                    if self.max_date and btn_date > self.max_date:
                        state = tk.DISABLED
                        
                    btn = tk.Button(self.cal_frame, text=str(day), width=3, state=state,
                                    command=lambda d=btn_date: self.select_date(d))
                    btn.grid(row=row_idx, column=col_idx, padx=2, pady=2)

    def prev_month(self):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.update_calendar()

    def next_month(self):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.update_calendar()

    def prev_year(self):
        self.current_year -= 1
        self.update_calendar()

    def next_year(self):
        self.current_year += 1
        self.update_calendar()
        
    def select_date(self, selected_date):
        self.target_var.set(selected_date.strftime("%Y-%m-%d"))
        self.destroy()
