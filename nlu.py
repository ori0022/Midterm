import os
import re
import json
from typing import Optional, Dict, Any, List
def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

_load_env()

class NLULayer:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[NLU] Warning: Failed to initialize Google GenAI client: {e}")
                self.client = None

    def extract_information(self, user_message: str, current_state: str = "INIT") -> Dict[str, Any]:
        """
        Extract structured entities from user input.
        Returns a dict:
        {
            "name": Optional[str],
            "claimed_date": Optional[str],
            "id_number": Optional[str],
            "confirmation": Optional[bool],
            "intent": str
        }
        """
        # If Gemini client is available, use Gemini for information extraction
        if self.client:
            try:
                extracted = self._extract_with_gemini(user_message, current_state)
                if extracted:
                    return extracted
            except Exception as e:
                print(f"[NLU] Gemini API extraction failed, using fallback: {e}")

        # Fallback heuristic extraction
        return self._extract_with_fallback(user_message, current_state)

    def _extract_with_gemini(self, user_message: str, current_state: str) -> Optional[Dict[str, Any]]:
        system_instruction = (
            "You are an expert Natural Language Understanding (NLU) component for Haovdim Bank's appointment bot.\n"
            "Analyze the user's message and extract key information into a STRICT JSON object with these exact keys:\n"
            "- \"name\": string or null (the customer's name if mentioned, e.g. 'Dana', 'Dana Shavit', 'David')\n"
            "- \"claimed_date\": string in YYYY-MM-DD format or null (any appointment date claimed by the user)\n"
            "- \"id_number\": string of digits or null (national ID number entered by user, e.g. '123456789')\n"
            "- \"confirmation\": boolean or null (true if the user is confirming/agreeing like 'yes', 'correct', 'that's me'; false if denying like 'no', 'wrong')\n"
            "- \"intent\": string ('check_appointment', 'provide_id', 'confirm_name', 'select_name', 'general')\n\n"
            f"Current conversation state: {current_state}\n"
            "Return ONLY raw JSON, with no markdown code blocks and no surrounding commentary."
        )

        prompt = f"User message: \"{user_message}\""

        from google.genai import types
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.0
            )
        )

        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        data = json.loads(text)
        return {
            "name": data.get("name"),
            "claimed_date": data.get("claimed_date"),
            "id_number": str(data["id_number"]).strip() if data.get("id_number") else None,
            "confirmation": data.get("confirmation"),
            "intent": data.get("intent", "general")
        }

    def _extract_with_fallback(self, message: str, current_state: str = "INIT") -> Dict[str, Any]:
        """Robust rule-based parser for offline/test reliability with Hebrew and complex entity support."""
        msg = message.strip()
        result: Dict[str, Any] = {
            "name": None,
            "claimed_date": None,
            "id_number": None,
            "confirmation": None,
            "intent": "general"
        }

        lower_msg = msg.lower()

        # 1. Registration intent (English and Hebrew)
        reg_keywords = [
            "new customer", "register", "sign up", "create account", "create user", "new user", "open account",
            "לקוח חדש", "הרשמה", "להירשם", "פתח חשבון", "פתיחת חשבון", "משתמש חדש", "חשבון חדש"
        ]
        if any(term in lower_msg for term in reg_keywords):
            result["intent"] = "register"
            return result

        # 2. ID Number extraction (9 digits with optional hyphens/spaces for Israeli ID)
        id_match = re.search(r'(?<!\d)(?:\d[\s-]*){9}(?!\d)', msg)
        if id_match:
            clean_digits = re.sub(r'[\s-]', '', id_match.group(0))
            if len(clean_digits) == 9 and clean_digits.isdigit():
                result["id_number"] = clean_digits
                result["intent"] = "provide_id"

        # 3. Confirmation and Denial (English and Hebrew)
        # 3. Confirmation and Denial (English and Hebrew)
        tokens = re.findall(r'[\w\u0590-\u05FF]+', lower_msg)
        if any(term in tokens for term in ["no", "nope", "wrong", "false", "לא", "טעות", "שגוי", "שלילי"]) or any(phrase in lower_msg for phrase in ["not me", "לא נכון", "לא אני"]):
            result["confirmation"] = False
            result["intent"] = "confirm_name"
        elif any(term in tokens for term in ["yes", "yeah", "yep", "correct", "true", "sure", "right", "exactly", "כן", "נכון", "אכן", "מדויק", "בדיוק", "חיובי", "אמת"]) or any(phrase in lower_msg for phrase in ["that's me", "thats me", "זה אני"]):
            result["confirmation"] = True
            result["intent"] = "confirm_name"

        # 4. Date extraction (e.g. 18.01.2027, 18/01/2027, 2027-01-18)
        date_match = re.search(r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})', msg)
        if date_match:
            d, m, y = date_match.groups()
            result["claimed_date"] = f"{y}-{int(m):02d}-{int(d):02d}"
        else:
            iso_match = re.search(r'(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})', msg)
            if iso_match:
                y, m, d = iso_match.groups()
                result["claimed_date"] = f"{y}-{int(m):02d}-{int(d):02d}"

        # 5. Name extraction (Complex names: hyphens, honorific titles, Hebrew & English)
        LETTERS = r"[A-Za-z\u0590-\u05FF]"
        TOKEN = rf"{LETTERS}+(?:[-]{LETTERS}+)?"
        FULL_NAME = rf"{TOKEN}(?:\s+{TOKEN}){{0,3}}"
        TITLES = r"(?:(?:Dr|Prof|Mr|Mrs|Ms)\.?|ד\"ר|דר'|דר|פרופ'?|מר|גב'|גברת)"
        INTRO_PREFIX = r"(?:my name is|i am|i'm|name is|this is|שמי הוא|השם שלי הוא|השם שלי|שמי|אני|מדבר|מדברת|זה|זאת|קוראים לי)"
        stop_words = r"(?:\s+(?:and|i|have|has|an|a|with|for|on|at|my|appointment|please|to|the|ויש|יש|לי|תור|פגישה|בבקשה|אצל))\b"
        blacklist = [
            "yes", "no", "hello", "hi", "hey", "help", "cancel", "thanks", "thank you",
            "כן", "לא", "שלום", "היי", "תודה", "תור", "עזרה", "ביטול", "לבטל", "לשנות", "להזיז", "לקבוע",
            "רוצה", "מעוניין", "מעוניינת", "מבקש", "מבקשת",
            "מה", "נשמע", "קורה", "המצב", "הולך", "אח", "יקר", "אחי", "גבר", "חבר",
            "בוקר", "טוב", "ערב", "צהריים", "לילה", "אהלן", "הלו", "איך", "איתך"
        ]

        # Filter out common greetings from being treated as names
        greeting_patterns = [
            r"מה נשמע", r"מה קורה", r"מה המצב", r"מה הולך", r"איך הולך",
            r"בוקר טוב", r"ערב טוב", r"צהריים טובים", r"לילה טוב", r"אח יקר", r"מה איתך"
        ]
        is_greeting_phrase = any(re.search(pat, lower_msg) for pat in greeting_patterns)

        m_intro = re.search(rf"(?:{INTRO_PREFIX}\s+)(?:{TITLES}\s+)?({FULL_NAME})", msg, re.IGNORECASE)
        if m_intro and not is_greeting_phrase:
            raw_name = m_intro.group(1).strip()
            cleaned = re.split(stop_words, raw_name, flags=re.IGNORECASE)[0].strip()
            words_in_name = [w.lower() for w in cleaned.split()]
            if not any(w in blacklist for w in words_in_name) and len(cleaned) >= 2:
                result["name"] = cleaned
                if result["intent"] == "general":
                    result["intent"] = "check_appointment"
        elif not result["id_number"] and not result["claimed_date"] and result["confirmation"] is None and not is_greeting_phrase:
            m_standalone = re.match(rf"^(?:{TITLES}\s+)?({FULL_NAME})$", msg, re.IGNORECASE)
            if m_standalone:
                word = m_standalone.group(1).strip()
                words_in_name = [w.lower() for w in word.split()]
                if not any(w in blacklist for w in words_in_name) and len(word) >= 2:
                    result["name"] = word

        # 6. Action Intent extraction (cancellation, reschedule, etc.)
        cancel_keywords = ["cancel", "ביטול", "לבטל", "בטל", "מחיקת", "למחוק"]
        if any(term in lower_msg for term in cancel_keywords):
            result["intent"] = "cancel_appointment"

        resched_keywords = ["reschedule", "move appointment", "change appointment", "move", "להזיז", "שינוי", "לשנות", "הזזה", "לדחות"]
        if any(term in lower_msg for term in resched_keywords):
            result["intent"] = "reschedule_appointment"

        return result

    def format_appointment_response(
        self,
        customer_name: str,
        claimed_date: Optional[str],
        actual_date: str,
        actual_time: str,
        service_type: str,
        language: str = "en"
    ) -> str:
        """
        Formulate natural-language response highlighting discrepancy if present.
        Supports both English and Hebrew based on language.
        """
        # Convert dates to standard display format DD.MM.YYYY
        def to_display_date(dt_str: str) -> str:
            if not dt_str: return ""
            parts = re.split(r'[-./]', dt_str)
            if len(parts) == 3:
                if len(parts[0]) == 4: # YYYY-MM-DD
                    return f"{int(parts[2]):02d}.{int(parts[1]):02d}.{parts[0]}"
                else: # DD-MM-YYYY
                    return f"{int(parts[0]):02d}.{int(parts[1]):02d}.{parts[2]}"
            return dt_str

        display_actual_date = to_display_date(actual_date)
        display_claimed_date = to_display_date(claimed_date) if claimed_date else None

        has_discrepancy = display_claimed_date and (display_claimed_date != display_actual_date)

        service_he_map = {
            "New Account Opening": "פתיחת חשבון חדש",
            "Mortgage Consultation": "ייעוץ משכנתאות",
            "Investment Planning": "תכנון השקעות",
            "Personal Loan Application": "בקשת הלוואה אישית",
            "Account Review": "בדיקת חשבון"
        }
        service_display = service_he_map.get(service_type, service_type) if language == "he" else service_type

        # If Gemini is available, use it to formulate response
        if self.client:
            try:
                lang_rule = "You MUST reply in Hebrew." if language == "he" else "You MUST reply in English."
                system_prompt = (
                    f"You are the virtual assistant of Haovdim Bank. You have successfully verified the customer's identity.\n"
                    f"{lang_rule}\n"
                    "Formulate a polite, clear, natural response to the customer informing them of their closest appointment details (e.g. 'Your closest appointment is scheduled on...').\n"
                    "If the user claimed a different date, you MUST clearly point out the discrepancy and correct them politely.\n"
                    "Keep the response professional, concise, and friendly."
                )
                user_ctx = (
                    f"Customer Name: {customer_name}\n"
                    f"Claimed Date: {display_claimed_date or 'Not specified'}\n"
                    f"Actual Date: {display_actual_date}\n"
                    f"Actual Time: {actual_time}\n"
                    f"Service Type: {service_display}\n"
                    f"Discrepancy: {'YES, claimed ' + str(display_claimed_date) + ' but actual is ' + display_actual_date if has_discrepancy else 'NO'}"
                )
                from google.genai import types
                resp = self.client.models.generate_content(
                    model=self.model_name,
                    contents=user_ctx,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.2
                    )
                )
                if resp.text:
                    return resp.text.strip()
            except Exception as e:
                print(f"[NLU] Gemini response generation failed, using standard template: {e}")

        # Deterministic standard template matching the project specification
        if language == "he":
            if has_discrepancy:
                return (
                    f"מצאתי אותך! שים/שימי לב: התור שלך בפועל נקבע לתאריך "
                    f"{display_actual_date} בשעה {actual_time} עבור {service_display} "
                    f"(ולא ב-{display_claimed_date} כפי שציינת)."
                )
            else:
                return (
                    f"מצאתי אותך! התור הקרוב ביותר שלך נקבע לתאריך "
                    f"{display_actual_date} בשעה {actual_time} עבור {service_display}."
                )
        else:
            if has_discrepancy:
                return (
                    f"I found you! Please note: your actual appointment is on "
                    f"{display_actual_date} at {actual_time} for {service_type} "
                    f"(not {display_claimed_date} as you stated)."
                )
            else:
                return (
                    f"I found you! Your closest appointment is scheduled on "
                    f"{display_actual_date} at {actual_time} for {service_type}."
                )

    def generate_conversational_reply(
        self,
        customer_name: str,
        user_message: str,
        open_appointments: List[Dict[str, Any]],
        language: str = "en"
    ) -> Optional[str]:
        """Generate a natural conversational response using Gemini for verified customers."""
        if not self.client:
            return None
        try:
            apps_summary = (
                ", ".join([f"{a['service_type']} on {a['date']} at {a['time']}" for a in open_appointments])
                if open_appointments else "None"
            )
            lang_rule = "You MUST reply in natural, polite Hebrew." if language == "he" else "Reply in English."
            system_prompt = (
                f"You are the virtual assistant of Haovdim Bank talking to verified customer {customer_name}.\n"
                f"{lang_rule}\n"
                f"Customer's open appointments: {apps_summary}\n"
                "Respond helpfully, politely, and concisely to the customer.\n"
                "If they ask to cancel an appointment, answer whether it can be cancelled.\n"
                "Do NOT repeat the initial greeting or appointment statement unless explicitly asked."
            )
            from google.genai import types
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3
                )
            )
            if resp.text:
                return resp.text.strip()
        except Exception:
            return None
        return None
