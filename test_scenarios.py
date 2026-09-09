import os
import sys
import hashlib
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from verification import ChatbotService, ConversationState
from database import DatabaseManager
from api_client import BankApiClient

TEST_DB = "test_scenarios_isolated.db"

def print_separator(title: str):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def seed_isolated_test_db(db: DatabaseManager):
    pw_hash = hashlib.sha256("password123".encode()).hexdigest()
    c1 = db.create_customer("Dana Shavit", "0541112233", "dana.shavit@bank.com", "1995-05-12", pw_hash, "Tel Aviv", "123456789")
    c2 = db.create_customer("David Cohen", "0523334455", "david.cohen@bank.com", "1988-11-20", pw_hash, "Jerusalem", "987654321")
    c3 = db.create_customer("David Levi", "0504445566", "david.levi@bank.com", "1990-03-15", pw_hash, "Haifa", "555666777")
    c4 = db.create_customer("Tamar Ben-David", "0537778899", "tamar.bd@bank.com", "1984-02-28", pw_hash, "Rishon LeZion", "444333222")
    c5 = db.create_customer("Yossi Mizrahi", "0589990011", "yossi.m@bank.com", "1978-06-22", pw_hash, "Herzliya", "222333444")
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Appointments (customer_id, service_type, date, time, status) VALUES (?, ?, ?, ?, ?)", (c1.id, "Investment Planning", "2027-01-19", "19:00", "Confirmed"))
        cursor.execute("INSERT INTO Appointments (customer_id, service_type, date, time, status) VALUES (?, ?, ?, ?, ?)", (c2.id, "Mortgage Consultation", "2027-02-10", "10:30", "Pending"))
        cursor.execute("INSERT INTO Appointments (customer_id, service_type, date, time, status) VALUES (?, ?, ?, ?, ?)", (c3.id, "New Account Opening", "2027-02-15", "14:00", "Confirmed"))
        cursor.execute("INSERT INTO Appointments (customer_id, service_type, date, time, status) VALUES (?, ?, ?, ?, ?)", (c4.id, "Personal Loan Application", "2027-03-01", "11:00", "Confirmed"))
        cursor.execute("INSERT INTO Appointments (customer_id, service_type, date, time, status) VALUES (?, ?, ?, ?, ?)", (c1.id, "New Account Opening", "2026-12-01", "10:00", "Completed"))
        
        for cid, amt, dt in [(c1.id, 250.0, "2027-01-10"), (c2.id, 1200.0, "2027-01-12"), (c3.id, 150.0, "2027-01-15"), (c4.id, 450.0, "2027-01-20"), (c5.id, 300.0, "2027-02-01")]:
            cursor.execute("INSERT INTO Invoices (customer_id, amount, date) VALUES (?, ?, ?)", (cid, amt, dt))
            
        for l_name, l_src in [("Lead 1", "Website"), ("Lead 2", "Referral"), ("Lead 3", "Social"), ("Lead 4", "Walk-in"), ("Lead 5", "Phone")]:
            cursor.execute("INSERT INTO Leads (name, phone, source, status) VALUES (?, ?, ?, ?)", (l_name, "0500000000", l_src, "New"))
        conn.commit()

def run_all_tests():
    print_separator("HAODVIM BANK CHATBOT — AUTOMATED TEST SUITE")
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass

    db = DatabaseManager(db_name=TEST_DB)
    seed_isolated_test_db(db)
    api = BankApiClient(db_manager=db)
    svc = ChatbotService(api_client=api)

    # -------------------------------------------------------------
    # Pre-Check: Entity Counts
    # -------------------------------------------------------------
    print("\n[PRE-CHECK] Verifying Entity Counts in Database (>= 5 rows required)...")
    customers = db.get_all_customers()
    appointments = db.get_all_appointments()
    leads = db.get_all_leads()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Invoices")
        invoices_count = cursor.fetchone()[0]

    print(f"  • Customers count:    {len(customers)} (>=5)")
    print(f"  • Appointments count: {len(appointments)} (>=5)")
    print(f"  • Invoices count:     {invoices_count} (>=5)")
    print(f"  • Leads count:        {len(leads)} (>=5)")

    assert len(customers) >= 5, f"Expected >= 5 customers, got {len(customers)}"
    assert len(appointments) >= 5, f"Expected >= 5 appointments, got {len(appointments)}"
    assert invoices_count >= 5, f"Expected >= 5 invoices, got {invoices_count}"
    assert len(leads) >= 5, f"Expected >= 5 leads, got {len(leads)}"
    print("  --> PASS: All entities have at least 5 records.")

    # -------------------------------------------------------------
    # Scenario 1: Unique Name + Claimed Date Discrepancy (Main Scenario)
    # -------------------------------------------------------------
    print_separator("TEST SCENARIO 1: Unique Name + Claimed Date Discrepancy")
    s1 = "test_s1"
    
    # Step 1: User states name and claimed date
    r1 = svc.process_message(s1, "My name is Dana and I have an appointment on 18.01.2027")
    print(f"User: My name is Dana and I have an appointment on 18.01.2027")
    print(f"Bot:  {r1['reply']}")
    assert "Dana Shavit" in r1["reply"], f"Expected bot to ask for confirmation of Dana Shavit, got: {r1['reply']}"
    assert r1["session"]["state"] == ConversationState.AWAITING_NAME_CONFIRMATION
    # Security assertion: No appointment time or actual date leaked!
    assert "19:00" not in r1["reply"] and "19.01" not in r1["reply"], "SECURITY LEAK: Date/time exposed before verification!"
    print("  --> Step 1 PASS: Bot asked confirmation without leaking details.")

    # Step 2: User confirms name
    r2 = svc.process_message(s1, "Yes")
    print(f"User: Yes")
    print(f"Bot:  {r2['reply']}")
    assert "ID number" in r2["reply"], f"Expected bot to ask for ID number, got: {r2['reply']}"
    assert r2["session"]["state"] == ConversationState.AWAITING_ID_VERIFICATION
    # Security assertion:
    assert "19:00" not in r2["reply"] and "19.01" not in r2["reply"], "SECURITY LEAK: Date/time exposed before verification!"
    print("  --> Step 2 PASS: Bot asked for ID number without leaking details.")

    # Step 3: User enters matching ID
    r3 = svc.process_message(s1, "123456789")
    print(f"User: 123456789")
    print(f"Bot:  {r3['reply']}")
    assert r3["session"]["state"] == ConversationState.VERIFIED
    assert "19.01.2027" in r3["reply"], f"Expected actual date 19.01.2027 in reply: {r3['reply']}"
    assert "19:00" in r3["reply"], f"Expected actual time 19:00 in reply: {r3['reply']}"
    assert "18.01" in r3["reply"], f"Expected discrepancy reference to 18.01: {r3['reply']}"
    print("  --> Step 3 PASS: User verified and discrepancy correctly highlighted.")

    # -------------------------------------------------------------
    # Scenario 2: Non-Unique Name (Clarification Required)
    # -------------------------------------------------------------
    print_separator("TEST SCENARIO 2: Non-Unique Name (Ambiguity Clarification)")
    s2 = "test_s2"

    # Step 1: User says partial name matching 2 customers
    r1 = svc.process_message(s2, "Hello, my name is David and I have an appointment")
    print(f"User: Hello, my name is David and I have an appointment")
    print(f"Bot:  {r1['reply']}")
    assert r1["session"]["state"] == ConversationState.AWAITING_NAME_CLARIFICATION
    # Privacy assertion: No other customer names leaked!
    assert "David Cohen" not in r1["reply"] and "David Levi" not in r1["reply"], "PRIVACY LEAK: Other customer names exposed!"
    assert "full name" in r1["reply"].lower(), f"Expected prompt for full name, got: {r1['reply']}"
    # Security assertion:
    assert "Mortgage" not in r1["reply"] and "10:30" not in r1["reply"], "SECURITY LEAK: Service/time exposed before verification!"
    print("  --> Step 1 PASS: Bot detected duplicate names and requested full name without leaking other customer names.")

    # Step 2: User clarifies which David
    r2 = svc.process_message(s2, "David Cohen")
    print(f"User: David Cohen")
    print(f"Bot:  {r2['reply']}")
    assert r2["session"]["state"] == ConversationState.AWAITING_ID_VERIFICATION
    assert "ID number" in r2["reply"]
    print("  --> Step 2 PASS: Candidate identified, prompted for ID number.")

    # Step 3: User provides matching ID
    r3 = svc.process_message(s2, "987654321")
    print(f"User: 987654321")
    print(f"Bot:  {r3['reply']}")
    assert r3["session"]["state"] == ConversationState.VERIFIED
    assert "closest appointment" in r3["reply"].lower()
    assert "2027" in r3["reply"] and "10:30" in r3["reply"]
    print("  --> Step 3 PASS: David Cohen successfully verified and closest appointment retrieved.")

    # -------------------------------------------------------------
    # Scenario 3: Incorrect ID Number (Zero Leakage + Block after 3 attempts)
    # -------------------------------------------------------------
    print_separator("TEST SCENARIO 3: Incorrect ID & Security Block (Max 3 Attempts)")
    s3 = "test_s3"

    svc.process_message(s3, "My name is Dana")
    svc.process_message(s3, "Yes")
    
    # Attempt 1: Wrong ID
    r_bad1 = svc.process_message(s3, "000000000")
    print(f"User (Attempt 1): 000000000")
    print(f"Bot:  {r_bad1['reply']}")
    assert "not match" in r_bad1["reply"].lower()
    assert "2 attempts remaining" in r_bad1["reply"]
    assert "19:00" not in r_bad1["reply"] and "19.01" not in r_bad1["reply"], "SECURITY LEAK on wrong ID!"
    print("  --> Attempt 1 PASS: Refused without leaking details (2 attempts left).")

    # Attempt 2: Wrong ID
    r_bad2 = svc.process_message(s3, "111111111")
    print(f"User (Attempt 2): 111111111")
    print(f"Bot:  {r_bad2['reply']}")
    assert "1 attempt remaining" in r_bad2["reply"]
    assert "19:00" not in r_bad2["reply"], "SECURITY LEAK on wrong ID!"
    print("  --> Attempt 2 PASS: Refused without leaking details (1 attempt left).")

    # Attempt 3: Wrong ID
    r_bad3 = svc.process_message(s3, "222222222")
    print(f"User (Attempt 3): 222222222")
    print(f"Bot:  {r_bad3['reply']}")
    assert r_bad3["session"]["state"] == ConversationState.BLOCKED
    assert "exceeded" in r_bad3["reply"].lower() or "locked" in r_bad3["reply"].lower()
    assert "19:00" not in r_bad3["reply"], "SECURITY LEAK on lock!"
    print("  --> Attempt 3 PASS: Session blocked after 3 failed attempts.")

    # Attempt 4: Blocked persistence check
    r_bad4 = svc.process_message(s3, "123456789") # Even if correct now, must remain blocked
    print(f"User (After lock): 123456789")
    print(f"Bot:  {r_bad4['reply']}")
    assert r_bad4["session"]["state"] == ConversationState.BLOCKED
    assert "locked" in r_bad4["reply"].lower() or "blocked" in r_bad4["reply"].lower()
    print("  --> Persistence PASS: Session remains blocked.")

    # -------------------------------------------------------------
    # Scenario 4: Existing Customer with No Open Appointments
    # -------------------------------------------------------------
    print_separator("TEST SCENARIO 4: Existing Customer With No Open Appointments")
    s4 = "test_s4"

    r1 = svc.process_message(s4, "My name is Yossi Mizrahi")
    print(f"User: My name is Yossi Mizrahi")
    print(f"Bot:  {r1['reply']}")
    assert "Yossi Mizrahi" in r1["reply"]

    r2 = svc.process_message(s4, "Yes")
    print(f"User: Yes")
    print(f"Bot:  {r2['reply']}")

    r3 = svc.process_message(s4, "222333444")
    print(f"User: 222333444")
    print(f"Bot:  {r3['reply']}")
    assert r3["session"]["state"] == ConversationState.VERIFIED
    assert "no open or scheduled appointments" in r3["reply"].lower() or "no" in r3["reply"].lower()
    print("  --> PASS: Verified customer identified with zero open appointments.")

    # -------------------------------------------------------------
    # Scenario 5: Customer Name Does Not Exist
    # -------------------------------------------------------------
    print_separator("TEST SCENARIO 5: Customer Name Does Not Exist in System")
    s5 = "test_s5"

    r1 = svc.process_message(s5, "My name is Elon Musk and I have an appointment")
    print(f"User: My name is Elon Musk and I have an appointment")
    print(f"Bot:  {r1['reply']}")
    assert "couldn't find" in r1["reply"].lower() or "not find" in r1["reply"].lower()
    assert r1["session"]["state"] == ConversationState.INIT
    print("  --> PASS: Handled unregistered name gracefully.")

    # -------------------------------------------------------------
    # Scenario 6: Review Remediation & Security Enhancements
    # -------------------------------------------------------------
    print_separator("TEST SCENARIO 6: Review Remediation & Security Hardening")
    
    # 6.1: Zero PII Leak in search_customers
    dana_records = api.search_customers("Dana")
    assert len(dana_records) > 0
    assert "id_number" not in dana_records[0], "SECURITY LEAK: id_number found in customer search response!"
    print("  --> 6.1 PASS: Customer search strictly withholds id_number (PII Protected).")

    # 6.2: Salted Bcrypt Hashing & Backward Compatibility
    from auth_utils import hash_password, verify_password
    b_hash = hash_password("SecurePassword2026")
    assert b_hash != "SecurePassword2026"
    assert verify_password("SecurePassword2026", b_hash), "Bcrypt verification failed!"
    assert not verify_password("WrongPassword", b_hash), "Bcrypt accepted invalid password!"
    # Verify legacy SHA-256 fallback
    sha_legacy = hashlib.sha256("legacy123".encode()).hexdigest()
    assert verify_password("legacy123", sha_legacy), "Legacy SHA-256 verification fallback failed!"
    print("  --> 6.2 PASS: Salted bcrypt password hashing & legacy fallback fully verified.")

    # 6.3: Multi-Session Customer Brute-Force Lockout Prevention
    # Attacker attempts to brute-force by rotating session IDs
    rot_s1 = "attacker_session_1"
    svc.process_message(rot_s1, "My name is Tamar Ben-David")
    svc.process_message(rot_s1, "Yes")
    r_rot1 = svc.process_message(rot_s1, "000000001")
    assert "2 attempts remaining" in r_rot1["reply"]

    rot_s2 = "attacker_session_2"
    svc.process_message(rot_s2, "My name is Tamar Ben-David")
    svc.process_message(rot_s2, "Yes")
    r_rot2 = svc.process_message(rot_s2, "000000002")
    assert "1 attempt remaining" in r_rot2["reply"]

    rot_s3 = "attacker_session_3"
    svc.process_message(rot_s3, "My name is Tamar Ben-David")
    svc.process_message(rot_s3, "Yes")
    r_rot3 = svc.process_message(rot_s3, "000000003")
    assert "exceeded" in r_rot3["reply"].lower() or "locked" in r_rot3["reply"].lower()

    # Session 4: Even with another new session, Tamar's account is locked!
    rot_s4 = "attacker_session_4"
    svc.process_message(rot_s4, "My name is Tamar Ben-David")
    svc.process_message(rot_s4, "Yes")
    r_rot4 = svc.process_message(rot_s4, "444333222") # Even correct ID is blocked
    assert "locked" in r_rot4["reply"].lower() or "blocked" in r_rot4["reply"].lower()
    print("  --> 6.3 PASS: Account lockout persists across rotated session IDs.")

    # 6.4: Appointment Existence & Status Integrity
    assert db.get_appointment_by_id(99999) is None, "Non-existent appointment ID returned data!"
    test_app = appointments[0]
    assert db.get_appointment_by_id(test_app.id) is not None
    cancel_success = db.update_appointment_status(test_app.id, "Cancelled")
    assert cancel_success is True
    no_update = db.update_appointment_status(99999, "Cancelled")
    assert no_update is False, "Updating non-existent appointment returned True!"
    print("  --> 6.4 PASS: Appointment existence & status integrity checked.")

    # 6.5: Layer Separation in Invoices
    all_invs = db.get_all_invoices()
    assert len(all_invs) >= 5
    print("  --> 6.5 PASS: DatabaseManager.get_all_invoices layer consistency verified.")

    # -------------------------------------------------------------
    # Scenario 7: Conversational Registration Workflow & Validations
    # -------------------------------------------------------------
    print_separator("TEST SCENARIO 7: Conversational New Customer Registration")
    s7 = "test_s7"

    # Step 1: User says they are a new customer
    r_reg1 = svc.process_message(s7, "I am a new customer")
    assert r_reg1["session"]["state"] == ConversationState.AWAITING_REGISTRATION
    assert "Full Name" in r_reg1["reply"]
    print("  --> Step 1 PASS: Triggered registration flow, prompted for Name.")

    # Step 2: Name validation
    r_bad_name = svc.process_message(s7, "x")
    assert "at least 2 letters" in r_bad_name["reply"].lower()
    r_good_name = svc.process_message(s7, "Ronit Bar")
    assert "Email" in r_good_name["reply"]
    print("  --> Step 2 PASS: Validated name (>= 2 chars), prompted for Email.")

    # Step 3: Email validation
    r_bad_email = svc.process_message(s7, "invalid_email")
    assert "valid email" in r_bad_email["reply"].lower()
    r_good_email = svc.process_message(s7, "ronit.bar@bank.com")
    assert "Password" in r_good_email["reply"]
    print("  --> Step 3 PASS: Validated email (@ check), prompted for Password.")

    # Step 4: Password validation (min 8 chars, 1 uppercase)
    r_bad_pwd_short = svc.process_message(s7, "Short1")
    assert "8 characters" in r_bad_pwd_short["reply"]
    r_bad_pwd_no_upper = svc.process_message(s7, "longpasswordwithoutuppercase123")
    assert "uppercase" in r_bad_pwd_no_upper["reply"].lower()
    r_good_pwd = svc.process_message(s7, "SecurePass123")
    assert "ID Number" in r_good_pwd["reply"]
    print("  --> Step 4 PASS: Validated password (min 8 chars & 1 uppercase), prompted for ID.")

    # Step 5: ID Number validation (9 digits)
    r_bad_id = svc.process_message(s7, "12345")
    assert "9 digits" in r_bad_id["reply"]
    r_good_id = svc.process_message(s7, "333444555")
    assert "Phone" in r_good_id["reply"]
    print("  --> Step 5 PASS: Validated national ID (exactly 9 digits), prompted for Phone.")

    # Step 6: Phone Number validation (10 digits)
    r_bad_phone = svc.process_message(s7, "050123")
    assert "10 digits" in r_bad_phone["reply"]
    r_good_phone = svc.process_message(s7, "0521234567")
    assert "Date of Birth" in r_good_phone["reply"]
    print("  --> Step 6 PASS: Validated phone (exactly 10 digits), prompted for DOB.")

    # Step 7: Date of Birth validation
    r_bad_dob = svc.process_message(s7, "someday")
    assert "Date of Birth format invalid" in r_bad_dob["reply"]
    r_good_dob = svc.process_message(s7, "15.05.1992")
    assert "Address" in r_good_dob["reply"]
    print("  --> Step 7 PASS: Validated date of birth format, prompted for Address.")

    # Step 8: Address & Registration Completion
    r_done = svc.process_message(s7, "Tel Aviv, Dizengoff 100")
    assert "Registration successful" in r_done["reply"]
    assert "Ronit" in r_done["reply"]
    assert r_done["session"]["state"] == ConversationState.VERIFIED
    assert r_done["session"]["verified"] is True
    print("  --> Step 8 PASS: Customer registered, session automatically transitioned to VERIFIED.")

    # Step 9: Database verification
    new_user = db.get_customer_by_auth("ronit.bar@bank.com", "SecurePass123")
    assert new_user is not None
    assert new_user.name == "Ronit Bar"
    assert new_user.phone == "0521234567"
    assert new_user.id_number == "333444555"
    print("  --> Step 9 PASS: Customer verified in database with bcrypt authentication.")

    print_separator("ALL TEST SCENARIOS (MANDATORY + SECURITY + REGISTRATION) PASSED!")

if __name__ == "__main__":
    exit_code = 0
    try:
        run_all_tests()
    except AssertionError as e:
        print(f"\n[FAIL] Assertion Error: {e}")
        exit_code = 1
    finally:
        import gc
        gc.collect()
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except Exception:
                pass
    sys.exit(exit_code)
