import re
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
    BLOCKED = "BLOCKED"

class SessionData:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = ConversationState.INIT
        self.claimed_name: Optional[str] = None
        self.claimed_date: Optional[str] = None
        self.candidate_customer: Optional[Dict[str, Any]] = None
        self.clarification_candidates: List[Dict[str, Any]] = []
        self.pending_cancellation_id: Optional[int] = None
        self.pending_reschedule_id: Optional[int] = None
        self.pending_booking_date: Optional[str] = None
        self.pending_booking_time: Optional[str] = None
        self.pending_booking_service: Optional[str] = None
        self.failed_attempts: int = 0
        self.max_attempts: int = 3
        self.verified: bool = False
        self.history: List[Dict[str, str]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state,
            "claimed_name": self.claimed_name,
            "claimed_date": self.claimed_date,
            "candidate_customer": self.candidate_customer["name"] if self.candidate_customer else None,
            "failed_attempts": self.failed_attempts,
            "verified": self.verified
        }

class ChatbotService:
    def __init__(self, nlu: Optional[NLULayer] = None, api_client: Optional[BankApiClient] = None):
        self.nlu = nlu or NLULayer()
        self.api = api_client or BankApiClient()
        self.sessions: Dict[str, SessionData] = {}

    def get_session(self, session_id: str) -> SessionData:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionData(session_id)
        return self.sessions[session_id]

    def reset_session(self, session_id: str) -> SessionData:
        self.sessions[session_id] = SessionData(session_id)
        return self.sessions[session_id]

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

        # Check if conversation is blocked
        if session.state == ConversationState.BLOCKED:
            reply = (
                "This conversation has been locked due to exceeding the maximum allowed verification attempts. "
                "For your security, please contact Haovdim Bank branch support or start a new session."
            )
            session.history.append({"role": "bot", "content": reply})
            return {"reply": reply, "session": session.to_dict()}

        # 1. NLU Layer
        extracted = self.nlu.extract_information(user_message, current_state=session.state)
        print(f"[DEBUG Session {session_id}] State={session.state}, Extracted={extracted}")

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

        else:
            reply = "How may I assist you with your Haovdim Bank appointment today?"

        session.history.append({"role": "bot", "content": reply})
        return {"reply": reply, "session": session.to_dict()}

    def _handle_init_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        name = extracted.get("name")
        claimed_date = extracted.get("claimed_date")

        if claimed_date:
            session.claimed_date = claimed_date

        if not name:
            return (
                "Welcome to Haovdim Bank Virtual Assistant!\n\n"
                "To access your appointments and personal banking services, please introduce yourself with your full name "
                "(e.g. My name is [Your Name])."
            )

        session.claimed_name = name

        # 2. Customer Search Layer
        matches = self.api.search_customers(name)

        if len(matches) == 0:
            # Edge Case: Name doesn't exist
            return (
                f"I'm sorry, I couldn't find any customer matching '{name}' in our system. "
                "Please verify your name or contact customer support."
            )

        elif len(matches) == 1:
            candidate = matches[0]
            session.candidate_customer = candidate
            session.state = ConversationState.AWAITING_NAME_CONFIRMATION
            return f"Your name is {candidate['name']}?"

        else:
            # Multiple matches: Ask for full name without leaking other customers' names
            session.clarification_candidates = matches
            session.state = ConversationState.AWAITING_NAME_CLARIFICATION
            return (
                f"I found multiple accounts matching the name '{name}'. "
                "For your privacy and security, please provide your full name (first and last name)."
            )

    def _handle_name_confirmation_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        confirmation = extracted.get("confirmation")
        cand_name = session.candidate_customer["name"] if session.candidate_customer else ""

        # If user explicitly provides an ID number right away
        if extracted.get("id_number"):
            session.state = ConversationState.AWAITING_ID_VERIFICATION
            return self._handle_id_verification_state(session, user_message, extracted)

        if confirmation is True or user_message.strip().lower() in ["yes", "yeah", "yep", "correct", "that's me", "thats me", "true", "sure"]:
            session.state = ConversationState.AWAITING_ID_VERIFICATION
            return "What is your ID number? (For verification purposes only)"

        elif confirmation is False or user_message.strip().lower() in ["no", "nope", "wrong", "not me"]:
            session.state = ConversationState.INIT
            session.candidate_customer = None
            return "I apologize. Could you please provide your full name so I can locate your account?"

        else:
            # Check if user repeated their full name matching the candidate
            if cand_name and cand_name.lower() in user_message.lower():
                session.state = ConversationState.AWAITING_ID_VERIFICATION
                return "What is your ID number? (For verification purposes only)"
            
            return f"Could you please confirm: Your name is {cand_name}? (Yes / No)"

    def _handle_name_clarification_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        # Check which candidate user selected
        selected_candidate = None
        user_lower = user_message.lower()

        for cand in session.clarification_candidates:
            if cand["name"].lower() in user_lower or cand["name"].split()[-1].lower() in user_lower:
                selected_candidate = cand
                break

        # Also check if user entered a full name directly
        if not selected_candidate:
            name_cand = extracted.get("name") or user_message.strip()
            new_matches = self.api.search_customers(name_cand)
            if len(new_matches) == 1:
                selected_candidate = new_matches[0]

        if selected_candidate:
            session.candidate_customer = selected_candidate
            session.clarification_candidates = []
            session.state = ConversationState.AWAITING_ID_VERIFICATION
            return "What is your ID number? (For verification purposes only)"
        else:
            return "For your privacy and security, could you please state your full first and last name?"

    def _handle_id_verification_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        candidate = session.candidate_customer
        if not candidate:
            session.state = ConversationState.INIT
            return "Let's start over. What is your name?"

        entered_id = extracted.get("id_number")
        if not entered_id:
            # Try to grab any digits from the raw message
            digit_match = re.search(r'\b\d{5,10}\b', user_message)
            if digit_match:
                entered_id = digit_match.group(0)

        if not entered_id:
            return "Please provide your ID number to verify your identity (numbers only)."

        # 3. Identity Verification Layer
        expected_id_number = str(candidate.get("id_number") or candidate.get("id")).strip()
        cleaned_entered_id = str(entered_id).strip()

        if cleaned_entered_id == expected_id_number:
            # Exact match! Verification successful
            session.verified = True
            session.state = ConversationState.VERIFIED

            # 4. Response Based on Real Data
            return self._formulate_appointment_details(session)
        else:
            # Mismatch: STRICT SECURITY - NEVER expose appointment info
            session.failed_attempts += 1
            remaining = session.max_attempts - session.failed_attempts

            if session.failed_attempts >= session.max_attempts:
                session.state = ConversationState.BLOCKED
                return (
                    "Verification failed. You have exceeded the maximum of 3 verification attempts. "
                    "For your protection, this session has been locked. Please contact Haovdim Bank branch support."
                )
            else:
                return (
                    f"The ID number provided does not match our records. "
                    f"You have {remaining} attempt{'s' if remaining > 1 else ''} remaining. "
                    f"What is your ID number? (For verification purposes only)"
                )

    def _get_services_menu(self, customer_name: str) -> str:
        first_name = customer_name.split()[0]
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

        menu = self._get_services_menu(candidate["name"])

        if not open_apps:
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
            service_type=service_type
        )
        return f"{response}\n\n{menu}"

    def _detect_verified_intent(self, msg: str) -> str:
        lower = msg.lower().strip()
        words = set(re.findall(r'\b\w+\b', lower))

        # 1. Cancel / Delete
        cancel_words = {"cancel", "delete", "remove", "drop", "discard"}
        if (words & cancel_words) or lower in ["4", "4.", "4️⃣", "option 4"]:
            return "cancel"

        # 2. Move / Reschedule
        reschedule_words = {"move", "reschedule", "postpone", "delay", "shift"}
        if (words & reschedule_words) or any(p in lower for p in ["change date", "change time", "different date", "different time", "change appointment", "move appointment"]) or lower in ["3", "3.", "3️⃣", "option 3"]:
            return "reschedule"

        # 3. Bank Services & Hours / Info
        service_hours_triggers = {
            "service", "services", "hour", "hours", "branch", "branches",
            "open", "opening", "closing", "location", "address", "offer",
            "info", "information", "help", "menu", "options", "support"
        }
        if (words & service_hours_triggers) or any(p in lower for p in ["bank services", "services & hours", "services and hours"]) or lower in ["5", "5.", "5️⃣", "option 5"]:
            return "services_info"

        # 4. Create / Book
        create_words = {"create", "book", "schedule", "arrange"}
        if (words & create_words) or any(p in lower for p in ["new appointment", "make an appointment", "set up", "want an appointment", "need an appointment"]) or lower in ["2", "2.", "2️⃣", "option 2"]:
            return "create"

        # 5. View / List
        view_words = {"view", "list", "see", "show", "check", "display"}
        if (words & view_words) or any(p in lower for p in ["my appointment", "my appointments", "appointments list", "open your appointments", "open my appointments", "scheduled", "upcoming"]) or lower in ["1", "1.", "1️⃣", "option 1"]:
            return "view"

        return "unknown"

    def _handle_verified_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        lower_msg = user_message.lower().strip()
        candidate = session.candidate_customer
        apps = self.api.get_customer_appointments(candidate["id"])
        open_apps = [a for a in apps if a.get("status") in ["Pending", "Confirmed"]]

        intent = self._detect_verified_intent(user_message)

        # --- OPTION 1: View Appointments List ---
        if intent == "view":
            if not open_apps:
                return (
                    f"Appointments List:\n"
                    f"You currently do not have any open or scheduled appointments, {candidate['name']}.\n\n"
                    "Reply with 2 or say 'create an appointment' to book a visit."
                )
            sorted_apps = sorted(open_apps, key=lambda a: self._parse_app_datetime(a.get("date", ""), a.get("time", "")) or datetime.max)
            lines = [f"Your Scheduled Appointments, {candidate['name']}:"]
            for a in sorted_apps:
                disp_dt = self._to_display_date(a["date"])
                lines.append(f"- {a['service_type']}: {disp_dt} at {a['time']} ({a['status']})")
            lines.append("\nNeed to make changes? Type 3 to move/reschedule, or 4 to cancel.")
            return "\n".join(lines)

        # --- OPTION 2: Create / Book an Appointment ---
        elif intent == "create":
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
                    return (
                        f"Appointment Confirmed!\n"
                        f"Your appointment for {booking['service_type']} has been scheduled on {display_dt} at {booking['time']}.\n\n"
                        "Is there anything else I can help you with?"
                    )
                except ValueError as e:
                    return f"Could not schedule appointment: {str(e)}. Please choose another date or time."
            else:
                session.state = ConversationState.AWAITING_NEW_APPOINTMENT_DETAILS
                session.pending_booking_date = booking["date"]
                session.pending_booking_time = booking["time"]
                session.pending_booking_service = booking["service_type"]
                return (
                    "Schedule a New Appointment:\n"
                    "What date, time, and service would you like?\n"
                    "(e.g. 04.09.2026 at 10:00 for New Account Opening, Investment Planning, Mortgage Consultation, or Personal Loan Application)"
                )

        # --- OPTION 3: Move / Reschedule an Appointment ---
        elif intent == "reschedule":
            if not open_apps:
                return (
                    f"You currently do not have any open appointments to move, {candidate['name']}.\n"
                    "Reply with 2 if you would like to schedule a new appointment."
                )

            app = self._get_target_appointment(open_apps)
            booking = self._parse_booking_details(user_message)
            if booking["date"] and booking["time"]:
                try:
                    self.api.reschedule_appointment(app["id"], booking["date"], booking["time"])
                    disp_new = self._to_display_date(booking["date"])
                    return (
                        f"Appointment Moved Successfully!\n"
                        f"Your {app['service_type']} appointment has been rescheduled to {disp_new} at {booking['time']}.\n\n"
                        "Is there anything else I can assist you with?"
                    )
                except ValueError as e:
                    return f"Could not move appointment: {str(e)}. Please choose another date or time."
            else:
                session.state = ConversationState.AWAITING_RESCHEDULE_DETAILS
                session.pending_reschedule_id = app["id"]
                disp_curr = self._to_display_date(app["date"])
                return (
                    f"Move / Reschedule Appointment:\n"
                    f"Your current appointment is on {disp_curr} at {app['time']} for {app['service_type']}.\n"
                    "What new date and time would you like to move it to? (e.g. 15.09.2026 at 11:00)"
                )

        # --- OPTION 4: Cancel / Delete an Appointment ---
        elif intent == "cancel":
            if not open_apps:
                return f"You currently do not have any open appointments to cancel, {candidate['name']}."

            app = self._get_target_appointment(open_apps)
            direct_cancels = [
                "cancel", "cancel that appointment", "cancel appointment", "cancel it", 
                "cancel my appointment", "please cancel", "delete appointment", "delete my appointment"
            ]
            if lower_msg in direct_cancels and lower_msg not in ["4", "4."]:
                self.api.cancel_appointment(app["id"])
                disp_dt = self._to_display_date(app["date"])
                return (
                    f"Your appointment on {disp_dt} at {app['time']} for {app['service_type']} "
                    "has been successfully cancelled.\n\n"
                    "Is there anything else I can help you with?"
                )
            else:
                session.state = ConversationState.AWAITING_CANCELLATION_CONFIRMATION
                session.pending_cancellation_id = app["id"]
                disp_dt = self._to_display_date(app["date"])
                return (
                    f"Would you like me to cancel your {app['service_type']} appointment on "
                    f"{disp_dt} at {app['time']}? (Please reply Yes to confirm, or No to keep it)"
                )

        # --- OPTION 5: Bank Services & Hours / Menu / Help ---
        elif intent == "services_info":
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
                f"{self._get_services_menu(candidate['name'])}"
            )

        # Thank you / Farewell
        if any(w in lower_msg for w in ["thank", "thanks", "bye", "goodbye"]):
            return f"You're very welcome, {candidate['name']}! Have a wonderful day."

        # Use Gemini conversational assistant if available
        ai_reply = self.nlu.generate_conversational_reply(candidate["name"], user_message, open_apps)
        if ai_reply:
            return ai_reply.replace("**", "").replace("*", "")

        # Default fallback: Re-show menu
        return self._get_services_menu(candidate["name"])

    def _handle_cancellation_confirmation_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        lower_msg = user_message.lower().strip()
        confirmation = extracted.get("confirmation")

        if confirmation is True or any(w in lower_msg for w in ["yes", "yeah", "yep", "sure", "cancel", "confirm", "please do"]):
            app_id = session.pending_cancellation_id
            if app_id:
                self.api.cancel_appointment(app_id)
            session.pending_cancellation_id = None
            session.state = ConversationState.VERIFIED
            return (
                "Your appointment has been successfully cancelled.\n\n"
                "Is there anything else I can help you with? Type 1 to view appointments or 2 to schedule a new one."
            )
        elif confirmation is False or any(w in lower_msg for w in ["no", "nope", "keep", "don't", "dont"]):
            session.pending_cancellation_id = None
            session.state = ConversationState.VERIFIED
            return "Alright, your appointment has not been cancelled and remains active. How else can I assist you?"
        else:
            return "Would you like me to cancel your appointment? Please reply Yes to confirm, or No to keep it."

    def _handle_new_appointment_details_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
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
                return (
                    f"Appointment Successfully Booked!\n"
                    f"Your {service} appointment is scheduled for {display_dt} at {time}.\n\n"
                    "Is there anything else I can assist you with?"
                )
            except ValueError as e:
                return f"Could not schedule appointment: {str(e)}. Please choose a different date or time."
        elif date and not time:
            session.pending_booking_date = date
            return f"Understood, for {self._to_display_date(date)}. What time would you prefer? (e.g. 10:00, 11:30, 14:00)"
        elif time and not date:
            session.pending_booking_time = time
            return f"Understood, at {time}. What date would you like? (e.g. 04.09.2026)"
        else:
            return "Please specify the date and time for the appointment (e.g. 04.09.2026 at 10:00)."

    def _handle_reschedule_details_state(self, session: SessionData, user_message: str, extracted: Dict[str, Any]) -> str:
        candidate = session.candidate_customer
        booking = self._parse_booking_details(user_message)
        app_id = session.pending_reschedule_id

        if not app_id:
            session.state = ConversationState.VERIFIED
            return self._get_services_menu(candidate["name"])

        date = booking["date"] or session.pending_booking_date
        time = booking["time"] or session.pending_booking_time

        if date and time:
            try:
                self.api.reschedule_appointment(app_id, date, time)
                session.state = ConversationState.VERIFIED
                session.pending_reschedule_id = None
                session.pending_booking_date = None
                session.pending_booking_time = None
                display_dt = self._to_display_date(date)
                return (
                    f"Appointment Moved Successfully!\n"
                    f"Your appointment has been rescheduled to {display_dt} at {time}.\n\n"
                    "Is there anything else I can assist you with?"
                )
            except ValueError as e:
                return f"Could not move appointment: {str(e)}. Please choose another date or time."
        elif date and not time:
            session.pending_booking_date = date
            return f"Got it, for {self._to_display_date(date)}. What time would you prefer? (e.g. 10:00, 11:30, 14:00)"
        elif time and not date:
            session.pending_booking_time = time
            return f"Got it, at {time}. What date would you like? (e.g. 15.09.2026)"
        else:
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
        if "mortgage" in lower:
            service = "Mortgage Consultation"
        elif "invest" in lower:
            service = "Investment Planning"
        elif "loan" in lower:
            service = "Personal Loan Application"
        elif "account" in lower:
            service = "New Account Opening"

        return {"date": dt, "time": tm, "service_type": service}
