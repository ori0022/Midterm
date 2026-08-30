# Haovdim Bank — Appointment Management & AI Verification Chatbot System

This project combines an existing Tkinter banking system with an **AI-powered Natural Language Verification & Appointment Assistant** built on FastAPI, SQLite, and Google Gemini AI.

---

## Quick Start (Windows)

The easiest way to launch the system on Windows is double-clicking:
```bash
run_web.bat
```
This automatically boots using the local virtual environment and starts the server at **`http://127.0.0.1:8000`**.

---

## Detailed Setup & Installation

### 1. Environment & Dependencies
```bash
# 1. Create a virtual environment
python -m venv .venv

# 2. Activate the virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows Command Prompt:
.venv\Scripts\activate.bat
# Linux/macOS:
source .venv/bin/activate

# 3. Install requirements
pip install -r requirements.txt
```

### 2. (Optional) Gemini API Key
Create a `.env` file in the root folder:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```
*(Note: If no API key is provided, the system automatically falls back to its built-in rule-based offline parser).*

---

## How to Run

### Method 1: Web Chatbot & REST API Server
```bash
python api_server.py
```
- **Web Chatbot UI**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Swagger REST API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Method 2: Native Desktop GUI Application (Tkinter)
```bash
python main.py
```
Opens the desktop client featuring:
- Role Selection (Customer vs. Admin)
- Customer Registration (with 9-digit national ID validation)
- Appointment booking with collision detection
- Admin dashboard with lead conversion and customer history

### Method 3: Automated Test Suite (5 Mandatory Scenarios)
```bash
python test_scenarios.py
```
Verifies all 5 mandatory scenarios:
1. **Unique Name + Claimed Date Discrepancy** (Main Scenario)
2. **Duplicate First Name** (Disambiguation between David Cohen & David Levi)
3. **Incorrect ID & Security Block** (Perm-lock after 3 failed attempts)
4. **Existing Customer with 0 Open Appointments** (Yossi Mizrahi)
5. **Name Not in System** (Elon Musk)

### Method 4: Reset / Clear Database (Empty State)
```bash
python seed_data.py
```
Clears all customer, appointment, invoice, and lead records, leaving all lists completely clean and empty. Real customers can be registered anytime via the desktop UI (`python main.py`) or API.

---

## Using the Chatbot (Command & Workflow Guide)

1. **Identification**:
   - The bot greets you and asks you to introduce yourself.
   - Example: *"My name is Dana Shavit"* or *"My name is Dana and I have an appointment on 18.01.2027"*.
2. **Confirmation**:
   - The bot asks: *"Your name is Dana Shavit?"*
   - Reply: *"Yes"*.
3. **Identity Verification**:
   - The bot requests: *"What is your ID number? (For verification purposes only)"*.
   - Reply: *"123456789"*.
4. **Interactive Services Menu**:
   - Once verified, the bot displays your appointment details and presents the options:
     - **1️⃣ View My Appointments**: `1` or *"open your appointments list"*
     - **2️⃣ Create an Appointment**: `2` or *"create an appointment on 04.09.2026 at 10:00"*
     - **3️⃣ Move an Appointment**: `3` or *"move to 25.01.2027 at 15:00"*
     - **4️⃣ Cancel an Appointment**: `4` or *"cancel that appointment"*
     - **5️⃣ Bank Services & Hours**: `5` or *"hours"*

---

## Troubleshooting

- **Port 8000 in use**: Run with `python -m uvicorn api_server:app --port 8080`.
- **PowerShell Script Policy Error**: Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
- **Offline / No API Key**: The system operates with zero external network dependencies via regex fallback.
