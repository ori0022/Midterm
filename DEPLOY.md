# Haovdim Bank — Deployment & Operations Guide (`DEPLOY.md`)

This guide covers local environment setup, architecture overview, repeatable DevOps procedures for server updates, and a complete demonstration transcript of the main scenario as required for the Final Project.

---

## 1. System Architecture (4-Layer Design)

The project builds a natural language conversation layer on top of Haovdim Bank's existing entity system:

1. **Natural Language Understanding (NLU) Layer (`nlu.py`)**:
   - Uses Google Gemini (`google-genai`) with structured JSON schema extraction.
   - Extracts `name`, `claimed_date`, `id_number`, and user confirmations.
   - Includes a deterministic fallback extractor for offline resilience and automated test stability.
   - Formulates natural language appointment responses that politely highlight and correct any date/time discrepancies.

2. **API Calls Layer (`api_client.py`)**:
   - Encapsulates all communication with the Entity API (`search_customers`, `get_customer`, `get_customer_appointments`, `get_invoices`, `get_leads`).
   - Ensures strict architectural separation between the conversational agent and backend services.

3. **Identity Verification & State Management (`verification.py`)**:
   - Manages conversation state per session (`INIT`, `AWAITING_NAME_CONFIRMATION`, `AWAITING_NAME_CLARIFICATION`, `AWAITING_ID_VERIFICATION`, `VERIFIED`, `BLOCKED`).
   - **Zero Information Leakage Guarantee**: No date, time, service, or personal details are exposed before successful identity verification.
   - Enforces a maximum of 3 failed verification attempts before permanently locking the session.

4. **Entity REST API & Web Application (`api_server.py` & `static/index.html`)**:
   - FastAPI server exposing REST endpoints for Customers, Appointments, Invoices, Leads, and Chat.
   - Interactive Swagger documentation at `/docs`.
   - Web Chat UI accessible at `/` with scenario test buttons.

---

## 2. How to Run the Application Locally

### Prerequisites
- Python 3.8+ installed (tested on Python 3.13)
- Git

### Step-by-Step Instructions

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/ori0022/Midterm.git
   cd Midterm
   ```

2. **Create and Activate a Virtual Environment** *(Recommended)*:
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables** *(Optional for Gemini)*:
   Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env     # Windows
   cp .env.example .env       # Linux / macOS
   ```
   Add your Gemini API Key in `.env`:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   GEMINI_MODEL=gemini-2.5-flash
   PORT=8000
   ```
   *(Note: If no API key is provided, the system seamlessly uses its intelligent built-in fallback parser, allowing 100% test scenario success offline).*

5. **Initialize or Reset the Database** *(Optional)*:
   Database tables are automatically created on first run. If you wish to reset all tables to a completely clean, empty state:
   ```bash
   python seed_data.py
   ```

6. **Run Automated Test Scenarios**:
   ```bash
   python test_scenarios.py
   ```

7. **Start the Web Application**:
   ```bash
   python api_server.py
   # Or run via uvicorn directly:
   uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
   ```
   *(Windows shortcut: You can also double-click `run_web.bat`).*

8. **Access the Application**:
   - **Web Chat UI**: [http://localhost:8000](http://localhost:8000)
   - **Swagger REST API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 3. DevOps Procedure: Updating Server from GitHub (Repeatable Process)

When changes are pushed to GitHub, follow this standard, consistent procedure to update and restart the running server.

### A. Manual Pull & Restart Procedure (Step-by-Step)

1. **SSH into the production / staging server**:
   ```bash
   ssh user@server-ip
   ```

2. **Navigate to the application root directory**:
   ```bash
   cd /path/to/Midterm
   ```

3. **Activate the virtual environment**:
   ```bash
   source .venv/bin/activate
   ```

4. **Fetch and pull the latest changes from GitHub**:
   ```bash
   git fetch origin
   git pull origin main
   ```

5. **Install / update any changed dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

6. **Verify Database Schema Integrity**:
   Ensure SQLite tables exist without altering or wiping existing customer data:
   ```bash
   python -c "from database import DatabaseManager; DatabaseManager()"
   ```
   *(Note: Do NOT run `seed_data.py` here, as it is strictly a data-wiping script for development resets).*

7. **Run the Automated Test Suite to Ensure Release Integrity**:
   ```bash
   python test_scenarios.py
   ```
   *(Proceed to restart only if all 5 test scenarios PASS with zero data leaks).*

8. **Restart the Application Service**:
   - **If running with systemd** (Recommended for production Linux servers):
     ```bash
     sudo systemctl restart haovdim-bank.service
     sudo systemctl status haovdim-bank.service
     ```
   - **If running under a process manager like PM2**:
     ```bash
     pm2 restart haovdim-bank
     ```
   - **If running in background / screen / tmux**:
     ```bash
     pkill -f "api_server.py" || pkill -f "uvicorn"
     nohup python api_server.py > app.log 2>&1 &
     ```

9. **Verify Health & Logs**:
   ```bash
   curl -I http://localhost:8000/docs
   # View live application logs:
   sudo journalctl -u haovdim-bank.service -f -n 50
   ```

### B. Standard `systemd` Service Unit Example (`/etc/systemd/system/haovdim-bank.service`)
```ini
[Unit]
Description=Haovdim Bank Appointment & Verification Chatbot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/path/to/Midterm
EnvironmentFile=/path/to/Midterm/.env
ExecStart=/path/to/Midterm/.venv/bin/uvicorn api_server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### C. Automated One-Command Server Update Script (`deploy.sh`)
For automated deployments on the remote server, run `./deploy.sh` directly:
```bash
#!/bin/bash
set -e

echo "=== [1/5] Fetching and pulling latest changes from GitHub ==="
git fetch origin
git pull origin main

echo "=== [2/5] Updating dependencies in virtual environment ==="
source .venv/bin/activate
pip install -r requirements.txt --quiet

echo "=== [3/5] Verifying database schema ==="
python -c "from database import DatabaseManager; DatabaseManager()"

echo "=== [4/5] Running automated verification test suite ==="
python test_scenarios.py

echo "=== [5/5] Restarting haovdim-bank service ==="
sudo systemctl restart haovdim-bank.service
sudo systemctl is-active --quiet haovdim-bank.service && echo ">>> Server update successful! Service is active."
```

### D. Rollback Procedure
If `python test_scenarios.py` fails or an issue occurs after pulling:
```bash
# 1. Roll back Git repository to previous commit
git reset --hard HEAD@{1}

# 2. Re-install previously working dependencies
pip install -r requirements.txt

# 3. Restart the service to restore stability
sudo systemctl restart haovdim-bank.service
```

---

## 4. Demonstration: Main Scenario Conversation Transcript

This transcript illustrates the primary scenario executed end-to-end, showing identification, confirmation, strict ID verification, and appointment correction.

```text
User: My name is Dana and I have an appointment on 18.01.2027
Bot:  Your name is Dana Shavit?

User: Yes
Bot:  What is your ID number? (For verification purposes only)

User: 123456789
Bot:  I found you! Please note: your actual appointment is on 19.01.2027 at 19:00 for Investment Planning (not 18.01.2027 as you stated).
```

### Breakdown of What Happened:
1. **Identification**: User entered free-form natural language with a partial name ("Dana") and an incorrect claimed date ("18.01.2027"). The NLU extracted both fields.
2. **Clarification/Confirmation**: The API found 1 matching record (`Dana Shavit`). The bot asked the user to confirm their full name without revealing any appointment date or time.
3. **Identity Verification**: Once confirmed, the bot strictly requested the user's ID number (`123456789`).
4. **Secure Match & Correction**: After verifying the ID against the API database, the bot retrieved the real appointment (`19.01.2027 at 19:00`) and formulated a natural language response highlighting and correcting the user's mistaken date.

---

## 5. Mandatory Test Scenarios Summary

The automated test script (`test_scenarios.py`) verifies all 5 mandatory scenarios:

| # | Scenario | Input / Conditions | System Behavior | Result |
|---|---|---|---|---|
| **1** | **Unique Name + Incorrect Date** | "Dana" claims `18.01.2027`, ID `123456789` | Confirms name, verifies ID, corrects date to `19.01.2027 at 19:00` | **PASS** |
| **2** | **Duplicate First Name** | "David" matches David Cohen & David Levi | Asks user to clarify full name without guessing | **PASS** |
| **3** | **Incorrect ID Number** | User provides invalid IDs 3 times | Politely refuses without leaking data; blocks on 3rd attempt | **PASS** |
| **4** | **Customer with No Appointments** | "Yossi Mizrahi", ID `222333444` | Verifies identity, reports zero open appointments | **PASS** |
| **5** | **Customer Not in System** | "Elon Musk" | Informs user that name was not found in records | **PASS** |

Run the test suite anytime with:
```bash
python test_scenarios.py
```
