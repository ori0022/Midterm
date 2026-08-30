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

    def _extract_with_fallback(self, message: str, current_state: str) -> Dict[str, Any]:
        """Robust rule-based parser for offline/test reliability."""
        msg = message.strip()
        result: Dict[str, Any] = {
            "name": None,
            "claimed_date": None,
            "id_number": None,
            "confirmation": None,
            "intent": "general"
        }

        # 1. ID Number extraction (sequence of 5 to 10 digits)
        id_match = re.search(r'\b\d{5,10}\b', msg)
        if id_match:
            result["id_number"] = id_match.group(0)
            result["intent"] = "provide_id"

        # 2. Confirmation (yes/no)
        lower_msg = msg.lower()
        if lower_msg in ["yes", "yeah", "yep", "correct", "that's me", "thats me", "true", "sure", "right"]:
            result["confirmation"] = True
            result["intent"] = "confirm_name"
        elif lower_msg in ["no", "nope", "not me", "wrong", "false"]:
            result["confirmation"] = False
            result["intent"] = "confirm_name"

        # 3. Date extraction (e.g. 18.01.2027, 18/01/2027, 2027-01-18)
        date_match = re.search(r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})', msg)
        if date_match:
            d, m, y = date_match.groups()
            result["claimed_date"] = f"{y}-{int(m):02d}-{int(d):02d}"
        else:
            iso_match = re.search(r'(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})', msg)
            if iso_match:
                y, m, d = iso_match.groups()
                result["claimed_date"] = f"{y}-{int(m):02d}-{int(d):02d}"

        # 4. Name extraction
        # e.g., "My name is Dana and I have an appointment", "I am Dana Shavit", "David"
        stop_words = r"(?:\s+(?:and|i|have|has|an|a|with|for|on|at|my|appointment|please|to|the))\b"
        # Match phrase after "my name is", "i am", etc.
        m_intro = re.search(r"(?:my name is|i am|i'm|name is|this is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)", msg, re.IGNORECASE)
        if m_intro:
            raw_name = m_intro.group(1).strip()
            # Split if a stop word was included
            cleaned = re.split(stop_words, raw_name, flags=re.IGNORECASE)[0].strip()
            if cleaned.lower() not in ["yes", "no", "hello", "hi", "hey", "appointment", "help"]:
                result["name"] = cleaned
                if result["intent"] == "general":
                    result["intent"] = "check_appointment"
        elif not result["id_number"] and not result["claimed_date"] and result["confirmation"] is None:
            # Standalone name match if whole message is 1-3 words
            m_standalone = re.match(r"^([A-Za-z]+(?:\s+[A-Za-z]+)?)$", msg)
            if m_standalone:
                word = m_standalone.group(1).strip()
                if word.lower() not in ["yes", "no", "hello", "hi", "hey", "help", "cancel", "thanks", "thank you"]:
                    result["name"] = word

        # Check for cancel intent
        if "cancel" in lower_msg:
            result["intent"] = "cancel_appointment"

        return result

    def format_appointment_response(
        self,
        customer_name: str,
        claimed_date: Optional[str],
        actual_date: str,
        actual_time: str,
        service_type: str
    ) -> str:
        """
        Formulate natural-language response highlighting discrepancy if present.
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

        # If Gemini is available, use it to formulate response
        if self.client:
            try:
                system_prompt = (
                    "You are the virtual assistant of Haovdim Bank. You have successfully verified the customer's identity.\n"
                    "Formulate a polite, clear, natural response to the customer informing them of their closest appointment details (e.g. 'Your closest appointment is scheduled on...').\n"
                    "If the user claimed a different date, you MUST clearly point out the discrepancy and correct them politely.\n"
                    "Keep the response professional, concise, and friendly."
                )
                user_ctx = (
                    f"Customer Name: {customer_name}\n"
                    f"Claimed Date: {display_claimed_date or 'Not specified'}\n"
                    f"Actual Date: {display_actual_date}\n"
                    f"Actual Time: {actual_time}\n"
                    f"Service Type: {service_type}\n"
                    f"Discrepancy: {'YES, claimed ' + display_claimed_date + ' but actual is ' + display_actual_date if has_discrepancy else 'NO'}"
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
        open_appointments: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Generate a natural conversational response using Gemini for verified customers."""
        if not self.client:
            return None
        try:
            apps_summary = (
                ", ".join([f"{a['service_type']} on {a['date']} at {a['time']}" for a in open_appointments])
                if open_appointments else "None"
            )
            system_prompt = (
                f"You are the virtual assistant of Haovdim Bank talking to verified customer {customer_name}.\n"
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
