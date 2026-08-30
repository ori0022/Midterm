================================================================================
          HAODVIM BANK - APPOINTMENT MANAGEMENT & AI CHATBOT SYSTEM
                             RUN & SETUP GUIDE
================================================================================

TABLE OF CONTENTS:
  1. System Overview
  2. Prerequisites
  3. Environment Setup & Dependency Installation
  4. How to Run
     4.1 Method A: One-Click Windows Launcher (Fastest)
     4.2 Method B: Web Chatbot & REST API Server
     4.3 Method C: Desktop Application (Tkinter GUI)
     4.4 Method D: Automated Test Suite (5 Mandatory Scenarios)
     4.5 Method E: Database Seeding & Reset
  5. How to Use the Chatbot (Command & Workflow Guide)
  6. API Documentation & Endpoints
  7. Troubleshooting & Common Issues

================================================================================
1. SYSTEM OVERVIEW
================================================================================
This system provides two complete interfaces for Haovdim Bank:
  1. AI-Powered Verification & Appointment Web Chatbot (FastAPI + Gemini NLU)
  2. Full-Featured Desktop Management Application (Tkinter + SQLite)

Features:
  - Natural language understanding (NLU) with Google Gemini AI and zero-dependency regex fallback.
  - Strict 3-step security verification (Identify Name -> Confirm Identity -> Verify ID Number).
  - ZERO appointment data leakage prior to full identity verification.
  - 3-attempt lock protection against unauthorized access.
  - Interactive appointment management: view list, book, reschedule/move, and cancel.
  - Desktop Customer and Admin portals with lead conversion and invoice tracking.

================================================================================
2. PREREQUISITES
================================================================================
  - Python 3.10 or higher installed on your operating system (Windows, macOS, or Linux).
  - Internet access (for installing dependencies and connecting to Gemini API).
  - (Optional) Google Gemini API key. If not provided, the system automatically uses its built-in rule-based fallback parser.

================================================================================
3. ENVIRONMENT SETUP & DEPENDENCY INSTALLATION
================================================================================

Step 1: Open a terminal (PowerShell, Command Prompt, or Bash) in the project directory:
   cd /path/to/Midterm

Step 2: Create a Python virtual environment:
   python -m venv .venv

Step 3: Activate the virtual environment:
   - On Windows (PowerShell):
       .venv\Scripts\Activate.ps1
       (If you get an execution policy error, run: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)
   - On Windows (Command Prompt):
       .venv\Scripts\activate.bat
   - On macOS / Linux:
       source .venv/bin/activate

Step 4: Install the required dependencies:
   pip install -r requirements.txt

   The requirements include:
     - fastapi
     - uvicorn
     - google-genai
     - requests
     - python-dotenv
     - pydantic

Step 5 (Optional): Set your Google Gemini API Key:
   Create a file named `.env` in the root folder with:
     GEMINI_API_KEY=your_actual_gemini_api_key_here

================================================================================
4. HOW TO RUN
================================================================================

--------------------------------------------------------------------------------
4.1 METHOD A: ONE-CLICK WINDOWS LAUNCHER (FASTEST)
--------------------------------------------------------------------------------
Simply double-click the file:
   run_web.bat

This automatically detects the local `.venv` environment, starts the FastAPI server, and displays the server console.
Open your browser and navigate to:
   http://127.0.0.1:8000

--------------------------------------------------------------------------------
4.2 METHOD B: WEB CHATBOT & REST API SERVER
--------------------------------------------------------------------------------
From your activated terminal, run:
   python api_server.py

Or directly targeting your virtual environment:
   & .venv/Scripts/python.exe api_server.py

Console Output:
   INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

Open your web browser and go to:
   - Web Chatbot UI:  http://127.0.0.1:8000
   - Swagger REST API: http://127.0.0.1:8000/docs
   - ReDoc API Docs:   http://127.0.0.1:8000/redoc

--------------------------------------------------------------------------------
4.3 METHOD C: DESKTOP APPLICATION (TKINTER GUI)
--------------------------------------------------------------------------------
From your terminal, run:
   python main.py

Or:
   & .venv/Scripts/python.exe main.py

This opens the native desktop GUI containing:
   - Role Selection Screen (Customer Portal vs Admin Portal)
   - Customer Login / Registration (with 9-digit National ID field)
   - Appointment Booking with collision avoidance
   - Admin Dashboard: Appointment management, lead tracking, and invoice history

--------------------------------------------------------------------------------
4.4 METHOD D: AUTOMATED TEST SUITE (5 MANDATORY SCENARIOS)
--------------------------------------------------------------------------------
To run the automated verification suite covering all 5 mandatory project scenarios:
   python test_scenarios.py

Or:
   & .venv/Scripts/python.exe test_scenarios.py

What is tested:
   [PRE-CHECK] Validates >= 5 records for Customers, Appointments, Invoices, and Leads.
   Scenario 1: Unique Name + Claimed Date Discrepancy (Main Scenario - Dana Shavit).
   Scenario 2: Non-Unique Name (Disambiguation between David Cohen & David Levi).
   Scenario 3: Incorrect ID & Permanent Security Block after 3 failed attempts.
   Scenario 4: Existing Customer with zero open appointments (Yossi Mizrahi).
   Scenario 5: Name not found in system (Elon Musk).

Result: 100% PASS with ZERO appointment data leaks.

--------------------------------------------------------------------------------
4.5 METHOD E: DATABASE RESET & EMPTY STATE
--------------------------------------------------------------------------------
The database (`bank_haovdim.db`) starts completely empty with NO fake people or 
placeholder data. All lists (Customers, Appointments, Invoices, Leads) are clean.

You can add real customers and appointments anytime by:
  - Registering a customer through the Desktop GUI: `python main.py`
  - Or using the REST API / Swagger docs at http://127.0.0.1:8000/docs

To reset or clear the database back to a completely empty state at any time, run:
   python seed_data.py

================================================================================
5. HOW TO USE THE CHATBOT (COMMAND & WORKFLOW GUIDE)
================================================================================

Step 1: Introduction & Identification
   When you open http://127.0.0.1:8000, the bot will greet you and ask you to introduce yourself.
   Type:
     "My name is [Your Name]"
     (e.g., "My name is Dana Shavit" or "My name is Dana and I have an appointment on 18.01.2027")

Step 2: Confirmation
   Bot asks: "Your name is Dana Shavit?"
   Type:
     "Yes"

Step 3: Identity Verification
   Bot asks: "What is your ID number? (For verification purposes only)"
   Type:
     "123456789"

Step 4: Services Menu
   Once verified, the bot displays your appointment details (correcting any mistaken date)
   and presents the interactive services menu:

     1. View My Appointments
     2. Create an Appointment
     3. Move an Appointment (Reschedule)
     4. Cancel an Appointment
     5. Bank Services & Hours

Step 5: Executing Actions (Use numbers or plain text):
   - Option 1 (View Appointments):
       Type: "1" or "open your appointments list" or "see my appointments"
   - Option 2 (Create an Appointment):
       Type: "2" or "I want an appointment on 04.09.2026 at 10:00"
   - Option 3 (Move / Reschedule):
       Type: "3" or "move an appointment" or "move to 25.01.2027 at 15:00"
   - Option 4 (Cancel an Appointment):
       Type: "4" or "cancel that appointment"
   - Option 5 (Bank Info & Hours):
       Type: "5" or "branch hours" or "help"

================================================================================
6. REST API DOCUMENTATION & ENDPOINTS
================================================================================
When `api_server.py` is running, visit:
   http://127.0.0.1:8000/docs

Key Endpoints:
   GET   /api/customers                       Retrieve all customers or search by name (?search=)
   GET   /api/customers/{customer_id}         Retrieve single customer details
   POST  /api/customers                       Register a new customer with national ID
   GET   /api/appointments                    Retrieve appointments (?customer_id=)
   POST  /api/appointments                   Create a new appointment
   PATCH /api/appointments/{id}/cancel        Cancel an appointment
   PATCH /api/appointments/{id}/reschedule    Move / reschedule an appointment
   GET   /api/invoices                        Retrieve customer invoices
   GET   /api/leads                           Retrieve bank leads
   POST  /api/chat                            Main chatbot conversational endpoint
   POST  /api/chat/reset                      Reset conversation session

================================================================================
7. TROUBLESHOOTING & COMMON ISSUES
================================================================================

Issue: Port 8000 is already in use.
Fix:   Specify another port when running:
       python -m uvicorn api_server:app --port 8080
       Then visit http://127.0.0.1:8080

Issue: "ModuleNotFoundError: No module named 'fastapi'" (or similar)
Fix:   Ensure you are using the virtual environment:
       & .venv\Scripts\python.exe api_server.py
       Or run: pip install -r requirements.txt

Issue: PowerShell script execution error when running `Activate.ps1`
Fix:   Run: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
       Then run: .venv\Scripts\Activate.ps1

Issue: No internet or Gemini API quota limit reached.
Fix:   The chatbot has a 100% built-in offline regex fallback engine.
       It will continue functioning completely offline without crashing.

================================================================================
Haovdim Bank Project (c) 2026 - All Rights Reserved
================================================================================
