import google.genai as genai
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class AIService:
    def __init__(self):
        self.model_name = "gemini-2.5-flash"

    def classify_incident(self, description):
        prompt = f"""
        You are an incident classification agent. 
        Classify the following report into one of these categories:
        [Accident, Fire, Theft, Medical, Traffic, Other]

        Also provide a short summary in plain English. 
        Assign priority for the complaint among Low, Medium, and High.

        Report: "{description}"
        Respond ONLY in JSON with keys: category, summary, priority.
        """

        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )

        raw_text = response.text.strip()
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text, flags=re.MULTILINE).strip()

        try:
            return json.loads(cleaned)
        except Exception:
            return {"category": "Other", "summary": description[:100], "priority": "Low"}
