import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from AppUI import AppUI

class RoleSelectionUIFrame(ttk.Frame):
    def __init__(self, parent: 'AppUI'):
        super().__init__(parent)
        self.parent = parent
        
        lbl = ttk.Label(self, text="Welcome to Haovdim Bank", style="Header.TLabel")
        lbl.pack(pady=40)
        
        desc = ttk.Label(self, text="Please select your role to continue:", justify=tk.CENTER)
        desc.pack(pady=10)
        
        def go_customer():
            from CustomerLoginUIFrame import CustomerLoginUIFrame
            self.parent.switch_frame(CustomerLoginUIFrame)
            
        def go_admin():
            from AdminUIFrame import AdminUIFrame
            self.parent.switch_frame(AdminUIFrame)
        
        btn_customer = ttk.Button(self, text="Customer Portal", command=go_customer)
        btn_customer.pack(pady=10, ipadx=20)
        
        btn_admin = ttk.Button(self, text="Bank Staff (Admin) Portal", command=go_admin)
        btn_admin.pack(pady=10, ipadx=20)
