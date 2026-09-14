import re
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from nlu import NLULayer
from api_client import BankApiClient

class ConversationState:
    INIT = "INIT"
    AWAITING_NAME_CONFIRMATION = "AWAITING_NAME_CONFIRMATION"
    AWAITING_NAME_CLARIFICATION = "AWAITING_NAME_CLARIFICATION"
    AWAITING_ID_VERIFICATION = "AWAITING_ID_VERIFICATION"
    VERIFIED = "VERIFIED"
    AWAITING_CANCELLATION_CONFIRMATION = "AWAITING_CANCELLATION_CONFIRMATION"
    AWAITING_NEW_APPOINTMENT_DETAILS = "AWAITING_NEW_APPOINTMENT_DETAILS"
    AWAITING_RESCHEDULE_DETAILS = "AWAITING_RESCHEDULE_DETAILS"
    AWAITING_REGISTRATION = "AWAITING_REGISTRATION"
    BLOCKED = "BLOCKED"

class SessionData:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = ConversationState.INIT
        self.language: str = "en"
        self.claimed_name: Optional[str] = None
        self.claimed_date: Optional[str] = None
        self.candidate_customer: Optional[Dict[str, Any]] = None
        self.clarification_candidates: List[Dict[str, Any]] = []
        self.pending_cancellation_id: Optional[int] = None
        self.pending_reschedule_id: Optional[int] = None
        self.pending_booking_date: Optional[str] = None
        self.pending_booking_time: Optional[str] = None
        self.pending_booking_service: Optional[str] = None
        self.registration_data: Dict[str, Any] = {}
        self.registration_step: Optional[str] = None
        self.failed_attempts: int = 0
        self.max_attempts: int = 3
        self.verified: bool = False
        self.history: List[Dict[str, str]] = []
        self.last_activity: float = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state,
            "language": self.language,
            "claimed_name": self.claimed_name,
            "claimed_date": self.claimed_date,
            "candidate_customer": self.candidate_customer["name"] if self.candidate_customer else None,
            "failed_attempts": self.failed_attempts,
            "verified": self.verified,
            "registration_step": self.registration_step
        }

    def to_db_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state,
            "language": self.language,
            "claimed_name": self.claimed_name,
            "claimed_date": self.claimed_date,
            "candidate_customer": self.candidate_customer,
            "clarification_candidates": self.clarification_candidates,
            "pending_cancellation_id": self.pending_cancellation_id,
            "pending_reschedule_id": self.pending_reschedule_id,
            "pending_booking_date": self.pending_booking_date,
            "pending_booking_time": self.pending_booking_time,
            "pending_booking_service": self.pending_booking_service,
            "registration_data": self.registration_data,
            "registration_step": self.registration_step,
            "failed_attempts": self.failed_attempts,
            "verified": self.verified,
            "history": self.history,
            "last_activity": self.last_activity
        }

    @classmethod
    def from_db_dict(cls, data: Dict[str, Any]) -> 'SessionData':
        s = cls(data["session_id"])
        s.state = data.get("state", ConversationState.INIT)
        s.language = data.get("language", "en")
        s.claimed_name = data.get("claimed_name")
        s.claimed_date = data.get("claimed_date")
        s.candidate_customer = data.get("candidate_customer")
        s.clarification_candidates = data.get("clarification_candidates", [])
        s.pending_cancellation_id = data.get("pending_cancellation_id")
        s.pending_reschedule_id = data.get("pending_reschedule_id")
        s.pending_booking_date = data.get("pending_booking_date")
        s.pending_booking_time = data.get("pending_booking_time")
        s.pending_booking_service = data.get("pending_booking_service")
        s.registration_data = data.get("registration_data", {})
        s.registration_step = data.get("registration_step")
        s.failed_attempts = data.get("failed_attempts", 0)
        s.verified = bool(data.get("verified", False))
        s.history = data.get("history", [])
        s.last_activity = data.get("last_activity", time.time())
        return s

def _mask_extracted(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive PII such as national ID numbers from debug logging."""
    safe = dict(extracted)
    if safe.get("id_number"):
        safe["id_number"] = "[REDACTED]"
    return safe

HEBREW_TO_LATIN_NAMES = {
    "דנה שביט": "Dana Shavit",
    "דנה": "Dana",
    "דוד כהן": "David Cohen",
    "דוד לוי": "David Levi",
    "דוד": "David",
    "תמר בן דוד": "Tamar Ben-David",
    "תמר בן-דוד": "Tamar Ben-David",
    "תמר": "Tamar",
    "יוסי מזרחי": "Yossi Mizrahi",
    "יוסי": "Yossi",
}

SERVICE_NAMES_HE = {
    "New Account Opening": "פתיחת חשבון חדש",
    "Mortgage Consultation": "ייעוץ משכנתאות",
    "Investment Planning": "תכנון השקעות",
    "Personal Loan Application": "בקשת הלוואה אישית",
    "Account Review": "בדיקת חשבון"
}

def _detect_language(message: str) -> Optional[str]:
    """Detect language of incoming user message. Hebrew characters take precedence; Latin characters indicate English. Numbers/symbols return None to preserve session language."""
    if any('\u0590' <= c <= '\u05FF' for c in message):
        return "he"
    if any(('a' <= c <= 'z') or ('A' <= c <= 'Z') for c in message):
        return "en"
    return None

class ChatbotService:
    LOCKOUT_DURATION_SECONDS = 900  # 15 minutes lockout on 3 failed attempts
    SESSION_TTL_SECONDS = 3600       # 1 hour session TTL to prevent memory leaks

    def __init__(
        self,
        nlu: Optional[NLULayer] = None,
        api_client: Optional[BankApiClient] = None,
        db_manager: Optional[Any] = None
    ):
        self.nlu = nlu or NLULayer()
        self.api = api_client or BankApiClient()
        if db_manager is not None:
            self.db = db_manager
        else:
            from database import DatabaseManager
            self.db = DatabaseManager()

    def _save_session(self, session: SessionData):
        self.db.save_chat_session(session.to_db_dict())

    def get_session(self, session_id: str) -> SessionData:
        self.db.cleanup_stale_chat_sessions(self.SESSION_TTL_SECONDS)
        db_data = self.db.get_chat_session(session_id)
        if db_data:
            session = SessionData.from_db_dict(db_data)
            session.last_activity = time.time()
            self._save_session(session)
            return session
        else:
            session = SessionData(session_id)
            self._save_session(session)
            return session

    def reset_session(self, session_id: str) -> SessionData:
        session = SessionData(session_id)
        self._save_session(session)
        return session

    def process_message(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """
        Main conversation handling logic implementing the 4 layers:
        1. NLU (Extraction)
        2. Customer Search
        3. Identity Verification
        4. Response based on Real Data
        """
        session = self.get_session(session_id)
        session.history.append({"role": "user", "content": user_message})

        detected_lang = _detect_language(user_message)
        if detected_lang:
            session.language = detected_lang

        # Check if conversation is blocked
        if session.state == ConversationState.BLOCKED:
            if session.language == "he":
                reply = (
                    "שיחה זו ננעלה עקב חריגה ממספר ניסיונות האימות המותרים. "
                    "למען ביטחונך, אנא פנה/י לתמיכה בסניף בנק העובדים."
                )
            else:
                reply = (
                    "This conversation has been locked due to exceeding the maximum allowed verification attempts. "
                    "For your security, please contact Haovdim Bank branch support."
                )
            session.history.append({"role": "bot", "content": reply})
            self._save_session(session)
            return {"reply": reply, "session": session.to_dict()}

        # 1. NLU Layer
        extracted = self.nlu.extract_information(user_message, current_state=session.state)
        print(f"[DEBUG Session {session_id}] State={session.state}, Extracted={_mask_extracted(extracted)}")

        reply = ""

        # State Machine Dispatch
        if session.state == ConversationState.INIT:
            reply = self._handle_init_state(session, user_message, extracted)

        elif session.state == ConversationState.AWAITING_NAME_CONFIRMATION:
            reply = self._handle_name_confirmation_state(session, user_message, extracted)

        elif session.state == ConversationState.AWAITING_NAME_CLARIFICATION:
            reply = self._handle_name_clarification_state(session, user_message, extracted)

        elif session.state == ConversationState.AWAITING_ID_VERIFICATION:
            reply = self._handle_id_verification_state(session, user_message, extracted)

        elif session.state == ConversationState.VERIFIED:
            reply = self._handle_verified_state(session, user_message, extracted)

        elif session.state == ConversationState.AWAITING_CANCELLATION_CONFIRMATION:
            reply = self._handle_cancellation_confirmation_state(session, user_message, extracted)

        elif session.state == ConversationState.AWAITING_NEW_APPOINTMENT_DETAILS:
            reply = self._handle_new_appointment_details_state(session, user_message, extracted)

        elif session.state == ConversationState.AWAITING_RESCHEDULE_DETAILS:
            reply = self._handle_reschedule_details_state(session, user_message, extracted)

        elif session.state == ConversationState.AWAITING_REGISTRATION:
            reply = self._handle_registration_state(session, user_message, extracted)

        else:
            if session.language == "he":
                reply = "כיצד אוכל לסייע לך בנוגע לפגישות ושירותי בנק העובדים היום?"
            else:
                reply = "How may I assist you with your Haovdim Bank appointment today?"

        session.history.append({"role": "bot", "content": reply})
        self._save_session(session)
        return {"reply": reply, "session": session.to_dict()}

    def _handle_init_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        user_lower = user_message.lower().strip()
        lang = session.language

        # 0. Check if user wants to register as a new customer
        if extracted.get("intent") == "register" or any(w in user_lower for w in ["register", "new customer", "sign up", "create account", "create user", "new user", "open account", "הרשמה", "להירשם", "לקוח חדש", "פתיחת חשבון", "פתח חשבון"]):
            session.state = ConversationState.AWAITING_REGISTRATION
            session.registration_data = {}
            session.registration_step = "name"
            if lang == "he":
                return (
                    "👋 ברוכים הבאים להרשמה לבנק העובדים!\n\n"
                    "אדריך אותך ביצירת חשבון הלקוח החדש שלך צעד אחר צעד.\n"
                    "ראשית, מה שמך המלא? (לפחות 2 אותיות)"
                )
            return (
                "👋 Welcome to Haovdim Bank Registration!\n\n"
                "I will guide you through creating your new customer account step-by-step.\n"
                "First, what is your Full Name? (At least 2 characters)"
            )

        name = extracted.get("name")
        claimed_date = extracted.get("claimed_date")

        if claimed_date:
            session.claimed_date = claimed_date

        if not name:
            if lang == "he":
                return (
                    "ברוכים הבאים לעוזר הווירטואלי של בנק העובדים!\n\n"
                    "כדי לגשת לתורים ולשירותי הבנקאות האישיים שלך, אנא הצג/הציגי את עצמך עם שמך המלא.\n\n"
                    "עדיין אין לך חשבון? הקלד/י \"אני לקוח חדש\" או \"הרשמה\" לפתיחת חשבון!"
                )
            return (
                "Welcome to Haovdim Bank Virtual Assistant!\n\n"
                "To access your appointments and personal banking services, please introduce yourself with your full name.\n\n"
                "Don't have an account yet? Type \"I am a new customer\" or \"register\" to create one!"
            )

        session.claimed_name = name

        # 2. Customer Search Layer
        matches = self.api.search_customers(name)
        if not matches and name.strip() in HEBREW_TO_LATIN_NAMES:
            matches = self.api.search_customers(HEBREW_TO_LATIN_NAMES[name.strip()])

        if len(matches) == 0:
            # Edge Case: Name doesn't exist
            if lang == "he":
                return (
                    f"מצטערים, לא מצאנו לקוח התואם לשם '{name}' במערכת. "
                    "אנא ודא/י את שמך או פנה/י לשירות הלקוחות. "
                    "אם הינך לקוח חדש, השב/י 'הרשמה' כדי לפתוח חשבון."
                )
            return (
                f"I'm sorry, I couldn't find any customer matching '{name}' in our system. "
                "Please verify your name or contact customer support. "
                "If you are a new customer, reply 'register' to open an account."
            )

        elif len(matches) == 1:
            candidate = matches[0]
            cand_id = candidate.get("id")
            if cand_id:
                failed_attempts, locked_until = self.db.get_customer_lockout(cand_id)
                if locked_until > 0 and time.time() < locked_until:
                    session.candidate_customer = candidate
                    session.state = ConversationState.BLOCKED
                    if lang == "he":
                        return (
                            "האימות נכשל. חרגת ממספר ניסיונות האימות המרבי (3). "
                            "למען ביטחונך, השיחה ננעלה. אנא פנה לתמיכה בסניף בנק העובדים."
                        )
                    return (
                        "Verification failed. You have exceeded the maximum of 3 verification attempts. "
                        "For your protection, this session has been locked. Please contact Haovdim Bank branch support."
                    )
            session.candidate_customer = candidate
            session.state = ConversationState.AWAITING_NAME_CONFIRMATION
            if lang == "he":
                return f"האם שמך הוא {candidate['name']}?"
            return f"Your name is {candidate['name']}?"

        else:
            # Multiple matches: Ask for full name without leaking other customers' names
            session.clarification_candidates = matches
            session.state = ConversationState.AWAITING_NAME_CLARIFICATION
            if lang == "he":
                return (
                    f"נמצאו מספר חשבונות המתאימים לשם '{name}'. "
                    "למען פרטיותך וביטחונך, אנא ציין/צייני את שמך המלא (שם פרטי ושם משפחה)."
                )
            return (
                f"I found multiple accounts matching the name '{name}'. "
                "For your privacy and security, please provide your full name (first and last name)."
            )

    def _handle_name_confirmation_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        confirmation = extracted.get("confirmation")
        cand_name = session.candidate_customer["name"] if session.candidate_customer else ""
        user_lower = user_message.strip().lower()
        lang = session.language

        # Check if user wants to register instead
        if extracted.get("intent") == "register" or any(w in user_lower for w in ["register", "new customer", "sign up", "create user", "הרשמה", "להירשם", "לקוח חדש"]):
            session.state = ConversationState.AWAITING_REGISTRATION
            session.registration_data = {}
            session.registration_step = "name"
            if lang == "he":
                return (
                    "👋 ברוכים הבאים להרשמה לבנק העובדים!\n\n"
                    "אדריך אותך ביצירת חשבון הלקוח החדש שלך צעד אחר צעד.\n"
                    "ראשית, מה שמך המלא? (לפחות 2 אותיות)"
                )
            return (
                "👋 Welcome to Haovdim Bank Registration!\n\n"
                "I will guide you through creating your new customer account step-by-step.\n"
                "First, what is your Full Name? (At least 2 characters)"
            )

        # If user explicitly provides an ID number right away
        if extracted.get("id_number"):
            session.state = ConversationState.AWAITING_ID_VERIFICATION
            return self._handle_id_verification_state(session, user_message, extracted)

        if confirmation is True or user_lower in ["yes", "yeah", "yep", "correct", "that's me", "thats me", "true", "sure", "כן", "נכון", "זה אני", "אכן", "מדויק", "בדיוק"]:
            session.state = ConversationState.AWAITING_ID_VERIFICATION
            if lang == "he":
                return "מה מספר תעודת הזהות שלך? (לצורכי אימות בלבד)"
            return "What is your ID number? (For verification purposes only)"

        elif confirmation is False or user_lower in ["no", "nope", "wrong", "not me", "לא", "לא נכון", "לא אני", "טעות"]:
            session.state = ConversationState.INIT
            session.candidate_customer = None
            if lang == "he":
                return "אני מתנצל. תוכל/י למסור את שמך המלא כדי שאוכל לאתר את חשבונך?"
            return "I apologize. Could you please provide your full name so I can locate your account?"

        else:
            # Check if user repeated their full name matching the candidate (or Hebrew name)
            matched_name = False
            if cand_name and cand_name.lower() in user_message.lower():
                matched_name = True
            elif cand_name:
                for he_k, lat_v in HEBREW_TO_LATIN_NAMES.items():
                    if lat_v.lower() == cand_name.lower() and he_k in user_message:
                        matched_name = True
                        break

            if matched_name:
                session.state = ConversationState.AWAITING_ID_VERIFICATION
                if lang == "he":
                    return "מה מספר תעודת הזהות שלך? (לצורכי אימות בלבד)"
                return "What is your ID number? (For verification purposes only)"
            
            if lang == "he":
                return f"אנא אשר/י: האם שמך הוא {cand_name}? (כן / לא)"
            return f"Could you please confirm: Your name is {cand_name}? (Yes / No)"

    def _handle_registration_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        lang = session.language
        msg = user_message.strip()
        lower = msg.lower()
        if lower in ["cancel", "stop", "abort", "exit", "ביטול", "בטל", "עצור", "יציאה"]:
            session.state = ConversationState.INIT
            session.registration_data = {}
            session.registration_step = None
            if lang == "he":
                return "ההרשמה בוטלה. כיצד אוכל לסייע לך בנוגע לשירותי בנק העובדים היום?"
            return "Registration has been cancelled. How else may I assist you with Haovdim Bank services today?"

        step = session.registration_step or "name"

        if step == "name":
            clean_name = re.sub(r'^(?:my name is|i am|name is|שמי הוא|שמי|השם שלי|קוראים לי|אני)\s+', '', msg, flags=re.IGNORECASE).strip()
            if len(clean_name) < 2 or not any(c.isalpha() for c in clean_name):
                if lang == "he":
                    return "השם חייב להכיל לפחות 2 אותיות. אנא הזן/הזיני את שמך המלא:"
                return "Name must be at least 2 letters long. Please enter your Full Name:"
            session.registration_data["name"] = clean_name
            session.registration_step = "email"
            if lang == "he":
                return f"תודה, {clean_name}.\nמה כתובת האימייל שלך?"
            return f"Thank you, {clean_name}.\nWhat is your Email address?"

        elif step == "email":
            if "@" not in msg or "." not in msg or len(msg) < 5:
                if lang == "he":
                    return "נדרשת כתובת אימייל תקינה המכילה '@' ודומיין. אנא הזן/הזיני כתובת אימייל:"
                return "A valid email containing '@' and a domain is required. Please enter your Email address:"
            session.registration_data["email"] = msg.lower()
            session.registration_step = "password"
            if lang == "he":
                return (
                    "אנא בחר/י סיסמה מאובטחת.\n"
                    "דרישות: לפחות 8 תווים ולפחות אות גדולה אחת באנגלית (uppercase):"
                )
            return (
                "Please choose a secure Password.\n"
                "Requirement: At least 8 characters long and contain at least 1 uppercase letter:"
            )

        elif step == "password":
            if len(msg) < 8 or not any(c.isupper() for c in msg):
                if lang == "he":
                    return (
                        "הסיסמה אינה עומדת בדרישות. עליה להכיל לפחות 8 תווים "
                        "ולפחות אות אחת גדולה באנגלית (uppercase).\nאנא הזן/הזיני סיסמה תקינה:"
                    )
                return (
                    "Password does not meet requirements. It must be at least 8 characters long "
                    "and contain at least 1 uppercase letter.\nPlease enter a valid Password:"
                )
            session.registration_data["password"] = msg
            session.registration_step = "id_number"
            if lang == "he":
                return "מה מספר תעודת הזהות הישראלית שלך? בדיוק 9 ספרות:"
            return "What is your Israeli National ID Number? Exactly 9 digits:"

        elif step == "id_number":
            from auth_utils import validate_israeli_id
            clean_id = re.sub(r'\D', '', msg)
            if not validate_israeli_id(clean_id):
                if lang == "he":
                    return "מספר תעודת הזהות אינו תקין. עליו להכיל בדיוק 9 ספרות ולעבור אימות ספרת ביקורת (Luhn Modulo 10). אנא הזן/הזיני מספר תעודת זהות בן 9 ספרות:"
                return "ID number (Teudat Zehut) is invalid. It must be exactly 9 digits and pass the Luhn Modulo 10 check digit verification. Please enter your 9-digit ID number:"
            session.registration_data["id_number"] = clean_id
            session.registration_step = "phone"
            if lang == "he":
                return "מה מספר הטלפון שלך? בדיוק 10 ספרות:"
            return "What is your Phone Number? Exactly 10 digits:"

        elif step == "phone":
            clean_phone = re.sub(r'\D', '', msg)
            if len(clean_phone) != 10:
                if lang == "he":
                    return "מספר הטלפון חייב להכיל בדיוק 10 ספרות. אנא הזן/הזיני מספר טלפון בן 10 ספרות:"
                return "Phone number must be exactly 10 digits. Please enter your 10-digit Phone number:"
            session.registration_data["phone"] = clean_phone
            session.registration_step = "dob"
            if lang == "he":
                return "מה תאריך הלידה שלך? בפורמט: יום/חודש/שנה:"
            return "What is your Date of Birth? Format: Day/Month/Year:"

        elif step == "dob":
            clean_dob = None
            m_eu = re.search(r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})', msg)
            if m_eu:
                d, m, y = m_eu.groups()
                if 1 <= int(d) <= 31 and 1 <= int(m) <= 12 and 1900 <= int(y) <= 2026:
                    clean_dob = f"{y}-{int(m):02d}-{int(d):02d}"
            else:
                m_iso = re.search(r'(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})', msg)
                if m_iso:
                    y, m, d = m_iso.groups()
                    if 1 <= int(d) <= 31 and 1 <= int(m) <= 12 and 1900 <= int(y) <= 2026:
                        clean_dob = f"{y}-{int(m):02d}-{int(d):02d}"

            if not clean_dob:
                if lang == "he":
                    return "פורמט תאריך הלידה אינו תקין. אנא ציין/צייני תאריך לידה בפורמט יום/חודש/שנה (לדוגמה: 15/05/1992):"
                return "Date of Birth format invalid. Please provide your Date of Birth in Day/Month/Year format:"

            session.registration_data["dob"] = clean_dob
            session.registration_step = "address"
            if lang == "he":
                return "ולסיום, מה כתובת המגורים שלך? עיר ורחוב:"
            return "Finally, what is your Residential Address? City and Street:"

        elif step == "address":
            if len(msg) < 2:
                if lang == "he":
                    return "כתובת מגורים היא שדה חובה. אנא הזן/הזיני את כתובת המגורים שלך:"
                return "Address is required. Please enter your Residential Address:"
            session.registration_data["address"] = msg

            # All 7 fields collected! Perform registration
            reg = session.registration_data
            try:
                created_cust = self.api.create_customer(
                    name=reg["name"],
                    phone=reg["phone"],
                    email=reg["email"],
                    password=reg["password"],
                    dob=reg["dob"],
                    address=reg["address"],
                    id_number=reg["id_number"]
                )
                session.candidate_customer = created_cust
                session.claimed_name = created_cust["name"]
                session.verified = True
                session.state = ConversationState.VERIFIED
                session.registration_data = {}
                session.registration_step = None
                first_name = created_cust["name"].split()[0]
                if lang == "he":
                    return (
                        f"🎉 ההרשמה הושלמה בהצלחה! ברוכים הבאים לבנק העובדים, {first_name}!\n"
                        f"חשבון הלקוח שלך נוצר ואומת בהצלחה.\n\n"
                        f"{self._get_services_menu(created_cust['name'], language=lang)}"
                    )
                return (
                    f"🎉 Registration successful! Welcome to Haovdim Bank, {first_name}!\n"
                    f"Your customer account has been created and verified.\n\n"
                    f"{self._get_services_menu(created_cust['name'], language=lang)}"
                )
            except ValueError as e:
                session.registration_step = "email"
                if lang == "he":
                    return f"שגיאה בהרשמה: {e}\nאנא הזן/הזיני כתובת אימייל אחרת:"
                return f"Registration error: {e}\nPlease enter a different Email address:"
            except Exception as e:
                session.state = ConversationState.INIT
                session.registration_data = {}
                session.registration_step = None
                if lang == "he":
                    return f"אירעה שגיאה בלתי צפויה במהלך ההרשמה ({e}). אנא נסה/נסי שוב מאוחר יותר או פנה לתמיכת הבנק."
                return f"We encountered an unexpected error during registration ({e}). Please try again later or contact bank support."

    def _handle_name_clarification_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        lang = session.language
        # Check which candidate user selected
        selected_candidate = None
        user_lower = user_message.lower()

        for cand in session.clarification_candidates:
            if cand["name"].lower() in user_lower or cand["name"].split()[-1].lower() in user_lower:
                selected_candidate = cand
                break
            for he_k, lat_v in HEBREW_TO_LATIN_NAMES.items():
                if lat_v.lower() == cand["name"].lower() and he_k in user_message:
                    selected_candidate = cand
                    break
            if selected_candidate:
                break

        # Also check if user entered a full name directly
        if not selected_candidate:
            name_cand = extracted.get("name") or user_message.strip()
            new_matches = self.api.search_customers(name_cand)
            if not new_matches and name_cand.strip() in HEBREW_TO_LATIN_NAMES:
                new_matches = self.api.search_customers(HEBREW_TO_LATIN_NAMES[name_cand.strip()])
            if len(new_matches) == 1:
                selected_candidate = new_matches[0]

        if selected_candidate:
            cand_id = selected_candidate.get("id")
            if cand_id:
                failed_attempts, locked_until = self.db.get_customer_lockout(cand_id)
                if locked_until > 0 and time.time() < locked_until:
                    session.candidate_customer = selected_candidate
                    session.state = ConversationState.BLOCKED
                    if lang == "he":
                        return (
                            "האימות נכשל. חרגת ממספר ניסיונות האימות המרבי (3). "
                            "למען ביטחונך, השיחה ננעלה. אנא פנה לתמיכה בסניף בנק העובדים."
                        )
                    return (
                        "Verification failed. You have exceeded the maximum of 3 verification attempts. "
                        "For your protection, this session has been locked. Please contact Haovdim Bank branch support."
                    )
            session.candidate_customer = selected_candidate
            session.clarification_candidates = []
            session.state = ConversationState.AWAITING_ID_VERIFICATION
            if lang == "he":
                return "מה מספר תעודת הזהות שלך? (לצורכי אימות בלבד)"
            return "What is your ID number? (For verification purposes only)"
        else:
            if lang == "he":
                return "למען פרטיותך וביטחונך, אנא ציין/צייני את שמך המלא (שם פרטי ושם משפחה)."
            return "For your privacy and security, could you please state your full first and last name?"

    def _handle_id_verification_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        lang = session.language
        candidate = session.candidate_customer
        if not candidate:
            session.state = ConversationState.INIT
            if lang == "he":
                return "בוא נתחיל מחדש. מה שמך?"
            return "Let's start over. What is your name?"

        entered_id = extracted.get("id_number")
        if not entered_id:
            # Check for exactly 9 digits (with optional hyphens/spaces)
            m_hyphen = re.search(r'(?<!\d)(?:\d[- ]*){9}(?!\d)', user_message)
            if m_hyphen:
                entered_id = re.sub(r'[- ]', '', m_hyphen.group(0))

        # Check if the user entered a phone number or invalid digit count without burning an attempt
        if not entered_id:
            phone_match = re.search(r'\b0\d{8,9}\b', user_message) or re.search(r'\b\d{10}\b', user_message)
            if phone_match:
                if lang == "he":
                    return (
                        "נראה שהזנת מספר טלפון. "
                        "אנא הזן/הזיני את מספר תעודת הזהות הישראלית בן 9 ספרות (תעודת זהות) לצורך אימות."
                    )
                return (
                    "It looks like you provided a phone number. "
                    "Please provide your 9-digit Israeli ID number (Teudat Zehut) for verification."
                )
            if any(char.isdigit() for char in user_message):
                if lang == "he":
                    return (
                        "מספר תעודת זהות חייב להכיל בדיוק 9 ספרות. "
                        "אנא הזן/הזיני את מספר תעודת הזהות הישראלית (9 ספרות) לצורך אימות."
                    )
                return (
                    "National ID number must be exactly 9 digits. "
                    "Please provide your 9-digit Israeli ID number (Teudat Zehut) for verification."
                )
            if lang == "he":
                return "אנא הזן/הזיני את מספר תעודת הזהות כדי לאמת את זהותך (ספרות בלבד)."
            return "Please provide your ID number to verify your identity (numbers only)."

        cust_id = candidate.get("id")
        if cust_id is not None:
            failed_attempts, locked_until = self.db.get_customer_lockout(cust_id)
            if locked_until > 0 and time.time() < locked_until:
                session.state = ConversationState.BLOCKED
                if lang == "he":
                    return (
                        "האימות נכשל. חרגת ממספר ניסיונות האימות המרבי (3). "
                        "למען ביטחונך, השיחה ננעלה. אנא פנה לתמיכה בסניף בנק העובדים."
                    )
                return (
                    "Verification failed. You have exceeded the maximum of 3 verification attempts. "
                    "For your protection, this session has been locked. Please contact Haovdim Bank branch support."
                )

        # 3. Identity Verification Layer via Secure API / DB without PII exposure
        cleaned_entered_id = re.sub(r'[\s-]', '', str(entered_id).strip())
        is_valid = self.api.verify_customer_id(cust_id, cleaned_entered_id) if cust_id else False

        if is_valid:
            # Exact match! Verification successful
            session.verified = True
            session.state = ConversationState.VERIFIED
            session.failed_attempts = 0
            if cust_id:
                self.db.clear_customer_lockout(cust_id)

            # 4. Response Based on Real Data
            return self._formulate_appointment_details(session)
        else:
            # Mismatch: STRICT SECURITY - NEVER expose appointment info
            session.failed_attempts += 1
            curr_fails = session.failed_attempts
            is_locked = False
            if cust_id:
                db_fails, locked_until = self.db.get_customer_lockout(cust_id)
                curr_fails = max(session.failed_attempts, db_fails)
                if (locked_until > 0 and time.time() < locked_until) or curr_fails >= session.max_attempts:
                    is_locked = True

            if session.failed_attempts >= session.max_attempts or is_locked or curr_fails >= session.max_attempts:
                session.state = ConversationState.BLOCKED
                if lang == "he":
                    return (
                        "האימות נכשל. חרגת ממספר ניסיונות האימות המרבי (3). "
                        "למען ביטחונך, השיחה ננעלה. אנא פנה לתמיכה בסניף בנק העובדים."
                    )
                return (
                    "Verification failed. You have exceeded the maximum of 3 verification attempts. "
                    "For your protection, this session has been locked. Please contact Haovdim Bank branch support."
                )
            else:
                remaining = max(0, min(session.max_attempts - session.failed_attempts, session.max_attempts - curr_fails))
                if lang == "he":
                    attempt_word = "ניסיונות" if remaining > 1 else "ניסיון"
                    return (
                        f"מספר תעודת הזהות שהוזן אינו תואם את הרישומים שלנו. "
                        f"נותרו לך {remaining} {attempt_word}. "
                        f"מה מספר תעודת הזהות שלך? (לצורכי אימות בלבד)"
                    )
                return (
                    f"The ID number provided does not match our records. "
                    f"You have {remaining} attempt{'s' if remaining > 1 else ''} remaining. "
                    f"What is your ID number? (For verification purposes only)"
                )

    def _get_services_menu(self, customer_name: str, language: str = "en") -> str:
        first_name = customer_name.split()[0]
        if language == "he":
            return (
                f"במה אוכל לעזור לך היום, {first_name}?\n"
                "1. צפייה בתורים שלי - הצגת רשימת התורים שנקבעו לך\n"
                "2. קביעת תור חדש - תיאום פגישה חדשה עם בנקאי/יועץ\n"
                "3. הזזת תור קיים - שינוי תאריך או שעה של תור קיים\n"
                "4. ביטול תור - ביטול פגישה מתוכננת\n"
                "5. שירותי הבנק ושעות פעילות - מידע על שירותים ושעות פתיחת הסניף\n\n"
                "ניתן להשיב במספר (1-5) או לתאר את בקשתך בחופשיות."
            )
        return (
            f"What would you like me to do today, {first_name}?\n"
            "1. View My Appointments - Open your scheduled appointments list\n"
            "2. Create an Appointment - Schedule a new meeting with an advisor\n"
            "3. Move an Appointment - Reschedule an existing appointment to a new date/time\n"
            "4. Cancel an Appointment - Cancel an upcoming scheduled visit\n"
            "5. Bank Services & Hours - Information on services and branch opening hours\n\n"
            "Reply with a number (1-5) or simply type your request in plain English."
        )

    def _parse_app_datetime(self, date_str: str, time_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        parts = re.split(r'[-./]', str(date_str).strip())
        if len(parts) != 3:
            return None
        try:
            if len(parts[0]) == 4:  # YYYY-MM-DD
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            else:  # DD-MM-YYYY
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                if year < 100:
                    year += 2000
        except ValueError:
            return None

        hour, minute = 0, 0
        if time_str:
            t_parts = str(time_str).strip().split(':')
            if len(t_parts) >= 2:
                try:
                    hour, minute = int(t_parts[0]), int(t_parts[1])
                except ValueError:
                    pass

        try:
            return datetime(year, month, day, hour, minute)
        except ValueError:
            return None

    def _get_target_appointment(self, open_apps: List[Dict[str, Any]], claimed_date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not open_apps:
            return None
        if len(open_apps) == 1:
            return open_apps[0]

        now = datetime.now()

        # If user explicitly claimed a date, pick the appointment closest to that claimed date
        if claimed_date_str:
            claimed_dt = self._parse_app_datetime(claimed_date_str, "00:00")
            if claimed_dt:
                scored = []
                for a in open_apps:
                    a_dt = self._parse_app_datetime(a.get("date", ""), a.get("time", ""))
                    diff = abs((a_dt - claimed_dt).total_seconds()) if a_dt else float("inf")
                    scored.append((diff, a))
                scored.sort(key=lambda x: x[0])
                return scored[0][1]

        # Otherwise, pick the closest upcoming appointment to now
        parsed = []
        for a in open_apps:
            a_dt = self._parse_app_datetime(a.get("date", ""), a.get("time", ""))
            parsed.append((a_dt if a_dt else datetime.max, a))

        upcoming = [(dt, a) for dt, a in parsed if dt.date() >= now.date()]
        if upcoming:
            upcoming.sort(key=lambda x: x[0])
            return upcoming[0][1]
        else:
            # If all are in the past, pick the one closest to today
            parsed.sort(key=lambda x: abs((x[0] - now).total_seconds()))
            return parsed[0][1]

    def _formulate_appointment_details(self, session: SessionData) -> str:
        """Fetch real appointment from API and formulate response with correction if needed."""
        candidate = session.candidate_customer
        apps = self.api.get_customer_appointments(candidate["id"])
        open_apps = [a for a in apps if a.get("status") in ["Pending", "Confirmed"]]

        menu = self._get_services_menu(candidate["name"], language=session.language)

        if not open_apps:
            if session.language == "he":
                return (
                    f"איתרתי את חשבונך, {candidate['name']}. "
                    f"יחד עם זאת, כרגע אין לך תורים פתוחים או מתוכננים במערכת.\n\n"
                    f"{menu}"
                )
            return (
                f"I found your account, {candidate['name']}. "
                f"However, you currently do not have any open or scheduled appointments in the system.\n\n"
                f"{menu}"
            )

        # Always select the closest upcoming appointment (or closest to claimed date)
        app = self._get_target_appointment(open_apps, session.claimed_date)
        actual_date = app["date"]
        actual_time = app["time"]
        service_type = app["service_type"]

        response = self.nlu.format_appointment_response(
            customer_name=candidate["name"],
            claimed_date=session.claimed_date,
            actual_date=actual_date,
            actual_time=actual_time,
            service_type=service_type,
            language=session.language
        )
        return f"{response}\n\n{menu}"

    def _detect_verified_intent(self, msg: str) -> str:
        lower = msg.lower().strip()
        words = set(re.findall(r'[\w\u0590-\u05FF]+', lower))

        # 1. Cancel / Delete
        cancel_words = {"cancel", "delete", "remove", "drop", "discard", "בטל", "ביטול", "לבטל", "מחק", "למחוק", "מחיקה"}
        if (words & cancel_words) or lower in ["4", "4.", "4️⃣", "option 4"]:
            return "cancel"

        # 2. Move / Reschedule
        reschedule_words = {"move", "reschedule", "postpone", "delay", "shift", "הזז", "להזיז", "הזזה", "שנה", "לשנות", "שינוי", "דחה", "לדחות", "דחייה"}
        if (words & reschedule_words) or any(p in lower for p in [
            "change date", "change time", "different date", "different time", "change appointment", "move appointment",
            "לשנות תאריך", "לשנות שעה", "להזיז תור", "שינוי תור", "להעביר תור", "תאריך אחר", "שעה אחרת"
        ]) or lower in ["3", "3.", "3️⃣", "option 3"]:
            return "reschedule"

        # 3. Bank Services & Hours / Info
        service_hours_triggers = {
            "service", "services", "hour", "hours", "branch", "branches",
            "open", "opening", "closing", "location", "address", "offer",
            "info", "information", "help", "menu", "options", "support",
            "שירות", "שירותים", "שעה", "שעות", "סניף", "סניפים",
            "פתיחה", "סגירה", "כתובת", "מידע", "עזרה", "תפריט", "אפשרויות", "תמיכה"
        }
        if (words & service_hours_triggers) or any(p in lower for p in [
            "bank services", "services & hours", "services and hours",
            "שירותי הבנק", "שעות פעילות", "שעות פתיחה", "שירותים ושעות"
        ]) or lower in ["5", "5.", "5️⃣", "option 5"]:
            return "services_info"

        # 4. Create / Book
        create_words = {"create", "book", "schedule", "arrange", "קבע", "לקבוע", "קביעה", "תאם", "לתאם", "תיאום"}
        if (words & create_words) or any(p in lower for p in [
            "new appointment", "make an appointment", "set up", "want an appointment", "need an appointment",
            "תור חדש", "לקבוע תור", "פגישה חדשה", "תיאום תור", "לקבוע פגישה", "רוצה תור", "צריך תור"
        ]) or lower in ["2", "2.", "2️⃣", "option 2"]:
            return "create"

        # 5. View / List
        view_words = {"view", "list", "see", "show", "check", "display", "ראה", "לראות", "הצג", "להציג", "צפה", "לצפות", "בדוק", "לבדוק", "רשימה"}
        if (words & view_words) or any(p in lower for p in [
            "my appointment", "my appointments", "appointments list", "open your appointments", "open my appointments", "scheduled", "upcoming",
            "התור שלי", "התורים שלי", "רשימת תורים", "תורים קיימים", "תורים שנקבעו"
        ]) or lower in ["1", "1.", "1️⃣", "option 1"]:
            return "view"

        return "unknown"

    def _handle_view_appointments(self, candidate: Dict[str, Any], open_apps: List[Dict[str, Any]], language: str = "en") -> str:
        if not open_apps:
            if language == "he":
                return (
                    f"רשימת תורים:\n"
                    f"כרגע אין לך תורים פתוחים או מתוכננים, {candidate['name']}.\n\n"
                    "השב/י 2 או כתוב/כתבי 'קביעת תור חדש' לתיאום פגישה."
                )
            return (
                f"Appointments List:\n"
                f"You currently do not have any open or scheduled appointments, {candidate['name']}.\n\n"
                "Reply with 2 or say 'create an appointment' to book a visit."
            )
        sorted_apps = sorted(open_apps, key=lambda a: self._parse_app_datetime(a.get("date", ""), a.get("time", "")) or datetime.max)
        if language == "he":
            lines = [f"התורים שנקבעו עבורך, {candidate['name']}:"]
            status_map = {"Pending": "ממתין", "Confirmed": "מאושר", "Cancelled": "בוטל", "Completed": "הושלם"}
            for a in sorted_apps:
                disp_dt = self._to_display_date(a["date"])
                st = SERVICE_NAMES_HE.get(a.get("service_type", ""), a.get("service_type", ""))
                stat = status_map.get(a.get("status", ""), a.get("status", ""))
                lines.append(f"- {st}: {disp_dt} בשעה {a['time']} ({stat})")
            lines.append("\nמעוניין/ת לעדכן? הקלד/י 3 להזזה/שינוי, או 4 לביטול.")
            return "\n".join(lines)

        lines = [f"Your Scheduled Appointments, {candidate['name']}:"]
        for a in sorted_apps:
            disp_dt = self._to_display_date(a["date"])
            lines.append(f"- {a['service_type']}: {disp_dt} at {a['time']} ({a['status']})")
        lines.append("\nNeed to make changes? Type 3 to move/reschedule, or 4 to cancel.")
        return "\n".join(lines)

    def _handle_create_appointment(self, session: SessionData, candidate: Dict[str, Any], user_message: str) -> str:
        lang = session.language
        booking = self._parse_booking_details(user_message)
        if booking["date"] and booking["time"]:
            try:
                self.api.create_appointment(
                    customer_id=candidate["id"],
                    service_type=booking["service_type"],
                    date=booking["date"],
                    time=booking["time"]
                )
                display_dt = self._to_display_date(booking["date"])
                if lang == "he":
                    st = SERVICE_NAMES_HE.get(booking['service_type'], booking['service_type'])
                    return (
                        f"התור נקבע בהצלחה!\n"
                        f"התור שלך עבור {st} נקבע לתאריך {display_dt} בשעה {booking['time']}.\n\n"
                        "האם יש משהו נוסף שאוכל לעזור בו?"
                    )
                return (
                    f"Appointment Confirmed!\n"
                    f"Your appointment for {booking['service_type']} has been scheduled on {display_dt} at {booking['time']}.\n\n"
                    "Is there anything else I can help you with?"
                )
            except ValueError as e:
                if lang == "he":
                    return f"לא ניתן לתאם את הפגישה: {str(e)}. אנא בחר/י תאריך או שעה אחרים."
                return f"Could not schedule appointment: {str(e)}. Please choose another date or time."
        else:
            session.state = ConversationState.AWAITING_NEW_APPOINTMENT_DETAILS
            session.pending_booking_date = booking["date"]
            session.pending_booking_time = booking["time"]
            session.pending_booking_service = booking["service_type"]
            if lang == "he":
                return (
                    "קביעת תור חדש:\n"
                    "לאיזה תאריך, שעה וסוג שירות תרצה/תרצי לתאם?\n"
                    "(לדוגמה: 04.09.2026 בשעה 10:00 עבור פתיחת חשבון חדש, תכנון השקעות, ייעוץ משכנתאות או בקשת הלוואה אישית)"
                )
            return (
                "Schedule a New Appointment:\n"
                "What date, time, and service would you like?\n"
                "(e.g. 04.09.2026 at 10:00 for New Account Opening, Investment Planning, Mortgage Consultation, or Personal Loan Application)"
            )

    def _handle_reschedule_appointment(self, session: SessionData, candidate: Dict[str, Any], user_message: str, open_apps: List[Dict[str, Any]]) -> str:
        lang = session.language
        if not open_apps:
            if lang == "he":
                return (
                    f"כרגע אין לך תורים פתוחים להזזה, {candidate['name']}.\n"
                    "השב/י 2 אם ברצונך לקבוע תור חדש."
                )
            return (
                f"You currently do not have any open appointments to move, {candidate['name']}.\n"
                "Reply with 2 if you would like to schedule a new appointment."
            )

        app = self._get_target_appointment(open_apps)
        booking = self._parse_booking_details(user_message)
        if booking["date"] and booking["time"]:
            try:
                self.api.reschedule_appointment(app["id"], booking["date"], booking["time"], customer_id=candidate["id"])
                disp_new = self._to_display_date(booking["date"])
                if lang == "he":
                    st = SERVICE_NAMES_HE.get(app['service_type'], app['service_type'])
                    return (
                        f"התור הוזז בהצלחה!\n"
                        f"התור שלך עבור {st} נקבע מחדש לתאריך {disp_new} בשעה {booking['time']}.\n\n"
                        "האם יש משהו נוסף שאוכל לסייע בו?"
                    )
                return (
                    f"Appointment Moved Successfully!\n"
                    f"Your {app['service_type']} appointment has been rescheduled to {disp_new} at {booking['time']}.\n\n"
                    "Is there anything else I can assist you with?"
                )
            except ValueError as e:
                if lang == "he":
                    return f"לא ניתן להזיז את התור: {str(e)}. אנא בחר/י תאריך או שעה אחרים."
                return f"Could not move appointment: {str(e)}. Please choose another date or time."
        else:
            session.state = ConversationState.AWAITING_RESCHEDULE_DETAILS
            session.pending_reschedule_id = app["id"]
            disp_curr = self._to_display_date(app["date"])
            if lang == "he":
                st = SERVICE_NAMES_HE.get(app['service_type'], app['service_type'])
                return (
                    f"הזזה / שינוי מועד תור:\n"
                    f"התור הנוכחי שלך נקבע לתאריך {disp_curr} בשעה {app['time']} עבור {st}.\n"
                    "לאיזה תאריך ושעה תרצה/תרצי להעביר אותו? (לדוגמה: 15.09.2026 בשעה 11:00)"
                )
            return (
                f"Move / Reschedule Appointment:\n"
                f"Your current appointment is on {disp_curr} at {app['time']} for {app['service_type']}.\n"
                "What new date and time would you like to move it to? (e.g. 15.09.2026 at 11:00)"
            )

    def _handle_cancel_appointment(self, session: SessionData, candidate: Dict[str, Any], user_message: str, lower_msg: str, open_apps: List[Dict[str, Any]]) -> str:
        lang = session.language
        if not open_apps:
            if lang == "he":
                return f"כרגע אין לך תורים פתוחים לביטול, {candidate['name']}."
            return f"You currently do not have any open appointments to cancel, {candidate['name']}."

        app = self._get_target_appointment(open_apps)
        direct_cancels = [
            "cancel", "cancel that appointment", "cancel appointment", "cancel it", 
            "cancel my appointment", "please cancel", "delete appointment", "delete my appointment",
            "בטל", "לבטל", "תבטל", "תבטלי", "ביטול תור", "לבטל את התור", "תבטל לי את התור", "ביטול התור"
        ]
        if lower_msg in direct_cancels and lower_msg not in ["4", "4."]:
            self.api.cancel_appointment(app["id"], customer_id=candidate["id"])
            disp_dt = self._to_display_date(app["date"])
            if lang == "he":
                st = SERVICE_NAMES_HE.get(app['service_type'], app['service_type'])
                return (
                    f"התור שלך בתאריך {disp_dt} בשעה {app['time']} עבור {st} "
                    "בוטל בהצלחה.\n\n"
                    "האם יש משהו נוסף שאוכל לעזור בו?"
                )
            return (
                f"Your appointment on {disp_dt} at {app['time']} for {app['service_type']} "
                "has been successfully cancelled.\n\n"
                "Is there anything else I can help you with?"
            )
        else:
            session.state = ConversationState.AWAITING_CANCELLATION_CONFIRMATION
            session.pending_cancellation_id = app["id"]
            disp_dt = self._to_display_date(app["date"])
            if lang == "he":
                st = SERVICE_NAMES_HE.get(app['service_type'], app['service_type'])
                return (
                    f"האם תרצה/תרצי לבטל את התור ל-{st} בתאריך "
                    f"{disp_dt} בשעה {app['time']}? (אנא השב/י כן לאישור, או לא לשמירת התור)"
                )
            return (
                f"Would you like me to cancel your {app['service_type']} appointment on "
                f"{disp_dt} at {app['time']}? (Please reply Yes to confirm, or No to keep it)"
            )

    def _handle_verified_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        lower_msg = user_message.lower().strip()
        lang = session.language
        candidate = session.candidate_customer
        apps = self.api.get_customer_appointments(candidate["id"])
        open_apps = [a for a in apps if a.get("status") in ["Pending", "Confirmed"]]

        intent = self._detect_verified_intent(user_message)

        if intent == "view":
            return self._handle_view_appointments(candidate, open_apps, language=lang)
        elif intent == "create":
            return self._handle_create_appointment(session, candidate, user_message)
        elif intent == "reschedule":
            return self._handle_reschedule_appointment(session, candidate, user_message, open_apps)
        elif intent == "cancel":
            return self._handle_cancel_appointment(session, candidate, user_message, lower_msg, open_apps)
        elif intent == "services_info":
            if lang == "he":
                return (
                    "מידע על בנק העובדים:\n"
                    "שעות פעילות הסניף:\n"
                    "- ימים ראשון עד חמישי: 08:30 - 18:00\n"
                    "- יום שישי: 08:30 - 12:30\n\n"
                    "שירותי ייעוץ זמינים:\n"
                    "- פתיחת חשבון חדש\n"
                    "- ייעוץ משכנתאות\n"
                    "- תכנון השקעות\n"
                    "- בקשת הלוואה אישית\n\n"
                    f"{self._get_services_menu(candidate['name'], language=lang)}"
                )
            return (
                "Haovdim Bank Information:\n"
                "Branch Hours:\n"
                "- Sunday - Thursday: 08:30 - 18:00\n"
                "- Friday: 08:30 - 12:30\n\n"
                "Available Advisory Services:\n"
                "- Investment Planning\n"
                "- Mortgage Consultation\n"
                "- New Account Opening\n"
                "- Personal Loan Application\n\n"
                f"{self._get_services_menu(candidate['name'], language=lang)}"
            )

        # Thank you / Farewell
        if any(w in lower_msg for w in ["thank", "thanks", "bye", "goodbye", "תודה", "תודה רבה", "ביי", "להתראות", "יום טוב"]):
            if lang == "he":
                return f"בשמחה רבה, {candidate['name']}! שיהיה לך יום נפלא."
            return f"You're very welcome, {candidate['name']}! Have a wonderful day."

        # Use Gemini conversational assistant if available
        ai_reply = self.nlu.generate_conversational_reply(candidate["name"], user_message, open_apps, language=lang)
        if ai_reply:
            return ai_reply.replace("**", "").replace("*", "")

        # Default fallback: Re-show menu
        return self._get_services_menu(candidate["name"], language=lang)

    def _handle_cancellation_confirmation_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        lower_msg = user_message.lower().strip()
        confirmation = extracted.get("confirmation")
        lang = session.language

        if confirmation is True or any(w in lower_msg for w in ["yes", "yeah", "yep", "sure", "cancel", "confirm", "please do", "כן", "בטח", "נכון", "בטל", "לבטל", "אכן", "מאשר", "מאשרת", "בבקשה"]):
            app_id = session.pending_cancellation_id
            if app_id:
                cust_id = session.candidate_customer["id"] if session.candidate_customer else None
                self.api.cancel_appointment(app_id, customer_id=cust_id)
            session.pending_cancellation_id = None
            session.state = ConversationState.VERIFIED
            if lang == "he":
                return (
                    "התור שלך בוטל בהצלחה.\n\n"
                    "האם יש משהו נוסף שאוכל לעזור בו? הקלד/י 1 לצפייה בתורים או 2 לקביעת תור חדש."
                )
            return (
                "Your appointment has been successfully cancelled.\n\n"
                "Is there anything else I can help you with? Type 1 to view appointments or 2 to schedule a new one."
            )
        elif confirmation is False or any(w in lower_msg for w in ["no", "nope", "keep", "don't", "dont", "לא", "אל תבטל", "תשאיר", "להשאיר", "שמור", "לא לבטל"]):
            session.pending_cancellation_id = None
            session.state = ConversationState.VERIFIED
            if lang == "he":
                return "בסדר גמור, התור שלך לא בוטל ונשאר פעיל. כיצד עוד אוכל לעזור לך?"
            return "Alright, your appointment has not been cancelled and remains active. How else can I assist you?"
        else:
            if lang == "he":
                return "האם תרצה/תרצי לבטל את התור? אנא השב/י כן לאישור, או לא לשמירת התור."
            return "Would you like me to cancel your appointment? Please reply Yes to confirm, or No to keep it."

    def _handle_new_appointment_details_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        lang = session.language
        candidate = session.candidate_customer
        booking = self._parse_booking_details(user_message)

        date = booking["date"] or session.pending_booking_date
        time = booking["time"] or session.pending_booking_time
        service = booking["service_type"] or session.pending_booking_service or "New Account Opening"

        if date and time:
            try:
                self.api.create_appointment(
                    customer_id=candidate["id"],
                    service_type=service,
                    date=date,
                    time=time
                )
                session.state = ConversationState.VERIFIED
                session.pending_booking_date = None
                session.pending_booking_time = None
                session.pending_booking_service = None
                display_dt = self._to_display_date(date)
                if lang == "he":
                    st = SERVICE_NAMES_HE.get(service, service)
                    return (
                        f"התור נקבע בהצלחה!\n"
                        f"התור שלך עבור {st} נקבע לתאריך {display_dt} בשעה {time}.\n\n"
                        "האם יש משהו נוסף שאוכל לסייע בו?"
                    )
                return (
                    f"Appointment Successfully Booked!\n"
                    f"Your {service} appointment is scheduled for {display_dt} at {time}.\n\n"
                    "Is there anything else I can assist you with?"
                )
            except ValueError as e:
                if lang == "he":
                    return f"לא ניתן לתאם את הפגישה: {str(e)}. אנא בחר/י תאריך או שעה אחרים."
                return f"Could not schedule appointment: {str(e)}. Please choose a different date or time."
        elif date and not time:
            session.pending_booking_date = date
            if lang == "he":
                return f"הבנתי, לתאריך {self._to_display_date(date)}. באיזו שעה תעדיף/תעדיפי? (לדוגמה: 10:00, 11:30, 14:00)"
            return f"Understood, for {self._to_display_date(date)}. What time would you prefer? (e.g. 10:00, 11:30, 14:00)"
        elif time and not date:
            session.pending_booking_time = time
            if lang == "he":
                return f"הבנתי, בשעה {time}. באיזה תאריך תרצה/תרצי? (לדוגמה: 04.09.2026)"
            return f"Understood, at {time}. What date would you like? (e.g. 04.09.2026)"
        else:
            if lang == "he":
                return "אנא ציין/צייני תאריך ושעה לפגישה (לדוגמה: 04.09.2026 בשעה 10:00)."
            return "Please specify the date and time for the appointment (e.g. 04.09.2026 at 10:00)."

    def _handle_reschedule_details_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        lang = session.language
        candidate = session.candidate_customer
        booking = self._parse_booking_details(user_message)
        app_id = session.pending_reschedule_id

        if not app_id:
            session.state = ConversationState.VERIFIED
            return self._get_services_menu(candidate["name"], language=lang)

        date = booking["date"] or session.pending_booking_date
        time = booking["time"] or session.pending_booking_time

        if date and time:
            try:
                self.api.reschedule_appointment(app_id, date, time, customer_id=candidate["id"])
                session.state = ConversationState.VERIFIED
                session.pending_reschedule_id = None
                session.pending_booking_date = None
                session.pending_booking_time = None
                display_dt = self._to_display_date(date)
                if lang == "he":
                    return (
                        f"התור הוזז בהצלחה!\n"
                        f"התור שלך נקבע מחדש לתאריך {display_dt} בשעה {time}.\n\n"
                        "האם יש משהו נוסף שאוכל לסייע בו?"
                    )
                return (
                    f"Appointment Moved Successfully!\n"
                    f"Your appointment has been rescheduled to {display_dt} at {time}.\n\n"
                    "Is there anything else I can assist you with?"
                )
            except ValueError as e:
                if lang == "he":
                    return f"לא ניתן להזיז את התור: {str(e)}. אנא בחר/י תאריך או שעה אחרים."
                return f"Could not move appointment: {str(e)}. Please choose another date or time."
        elif date and not time:
            session.pending_booking_date = date
            if lang == "he":
                return f"הבנתי, לתאריך {self._to_display_date(date)}. באיזו שעה תעדיף/תעדיפי? (לדוגמה: 10:00, 11:30, 14:00)"
            return f"Got it, for {self._to_display_date(date)}. What time would you prefer? (e.g. 10:00, 11:30, 14:00)"
        elif time and not date:
            session.pending_booking_time = time
            if lang == "he":
                return f"הבנתי, בשעה {time}. באיזה תאריך תרצה/תרצי? (לדוגמה: 15.09.2026)"
            return f"Got it, at {time}. What date would you like? (e.g. 15.09.2026)"
        else:
            if lang == "he":
                return "אנא ציין/צייני את התאריך והשעה החדשים (לדוגמה: 15.09.2026 בשעה 11:00)."
            return "Please specify the new date and time (e.g. 15.09.2026 at 11:00)."

    def _to_display_date(self, dt_str: str) -> str:
        if not dt_str:
            return ""
        parts = re.split(r'[-./]', dt_str)
        if len(parts) == 3:
            if len(parts[0]) == 4:  # YYYY-MM-DD
                return f"{int(parts[2]):02d}.{int(parts[1]):02d}.{parts[0]}"
            else:
                return f"{int(parts[0]):02d}.{int(parts[1]):02d}.{parts[2]}"
        return dt_str

    def _parse_booking_details(self, text: str) -> Dict[str, Optional[str]]:
        dt = None
        m_date = re.search(r'\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b', text)
        if m_date:
            p1, p2, p3 = m_date.group(1), m_date.group(2), m_date.group(3)
            if len(p1) == 4:
                dt = f"{p1}-{int(p2):02d}-{int(p3):02d}"
            else:
                dt = f"{p3}-{int(p2):02d}-{int(p1):02d}"

        tm = None
        m_time = re.search(r'\b(\d{1,2}:\d{2})\b', text)
        if m_time:
            tm = m_time.group(1)
            if len(tm) == 4:
                tm = "0" + tm

        lower = text.lower()
        service = "New Account Opening"
        if "mortgage" in lower or "משכנת" in lower:
            service = "Mortgage Consultation"
        elif "invest" in lower or "השקע" in lower:
            service = "Investment Planning"
        elif "loan" in lower or "הלווא" in lower:
            service = "Personal Loan Application"
        elif "account" in lower or "חשבון" in lower:
            service = "New Account Opening"

        return {"date": dt, "time": tm, "service_type": service}
