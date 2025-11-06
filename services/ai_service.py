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

    def _call_gemini(self, prompt):
        response = client.models.generate_content(
                model=self.model_name,
                contents=prompt
        )
        text = response.text.strip()
        return text

    def classification_agent(self, description):
        prompt = f"""
        You are an expert incident classifier. You will be given a report of an incident complained about by a human user. 
        Classify if this report into one of: [Accident, Fire, Theft, Medical, Traffic, Other].

        Example 1: 
        Report: Heavy traffic congestion observed near Tambaram Bus Stand during peak hours. The area experiences frequent vehicle pile-ups due to narrow lanes, improper parking by autos and buses, and poor traffic signal coordination. Pedestrian movement is also hindered as buses occupy most of the road space, causing long delays and safety concerns for commuters. Immediate attention is needed to improve signal timing, enforce parking rules, and streamline bus movement to reduce congestion.
        Output: Traffic

        Example 2:
        Report: Few jewelry were stolen at around 10 pm by 4 people wearing mask from my house. They threatened my family with a knife and took away all the valuables including gold and cash. The incident has left us traumatized and we request immediate action to catch the culprits and recover our stolen items.
        Output: Theft

        Example 3:
        Report: A major accident occurred on the highway involving multiple vehicles. Several cars collided due to slippery road conditions caused by heavy rain. Emergency services were called to the scene, and several individuals sustained injuries ranging from minor cuts to serious fractures. Traffic was severely disrupted, leading to long delays. Authorities are investigating the cause of the accident and urging drivers to exercise caution in adverse weather conditions.
        Output: "Accident"

        Example 4:
        Report: A pothole on Main Street has caused several vehicles to swerve dangerously, leading to minor accidents. The pothole has been present for weeks and is worsening with each passing day. Residents are concerned about the safety hazards it poses, especially during nighttime when visibility is low. Immediate repair is necessary to prevent further incidents.
        Output: "Other"

        Respond ONLY in one word. Return onlt the category (no explanations).
        Report: "{description}"
        """
        return self._call_gemini(prompt)

    def summary_agent(self, description):
        prompt = f"""
        You are an expert incident summarizer. You will be given a report of an incident complained about by a human user.
        Provide a concise summary of the report in 1-2 sentences.
        Summary should capture the key details of the incident like location,time,etc. so that authorities can quickly understand the situation.
        Focus on only facts, avoid opinions or unnecessary details.

        Example 1:
        Report: Heavy traffic congestion observed near Tambaram Bus Stand during peak hours. The area experiences frequent vehicle pile-ups due to narrow lanes, improper parking by autos and buses, and poor traffic signal coordination. Pedestrian movement is also hindered as buses occupy most of the road space, causing long delays and safety concerns for commuters. Immediate attention is needed to improve signal timing, enforce parking rules, and streamline bus movement to reduce congestion.
        Summary: Severe traffic congestion at Tambaram Bus Stand to narrow lanes, improper parking, and poor signal coordination.

        Example 2:
        Report: Few jewelry were stolen at around 10 pm by 4 people wearing mask from my house. They threatened my family with a knife and took away all the valuables including gold and cash. The incident has left us traumatized and we request immediate action to catch the culprits and recover our stolen items.
        Summary: Four masked individuals stole jewelry and cash from a home at 10 pm with a knife threat.

        Example 3:
        Report: A major accident occurred on the highway involving multiple vehicles. Several cars collided due to slippery road conditions caused by heavy rain. Emergency services were called to the scene, and several individuals sustained injuries ranging from minor cuts to serious fractures. Traffic was severely disrupted, leading to long delays. Authorities are investigating the cause of the accident and urging drivers to exercise caution in adverse weather conditions.
        Summary: Multi-vehicle accident on highway due to slippery roads from heavy rain, causing injuries.

        Summarize this report in 1-2 sentences: {description}
        """
        return self._call_gemini(prompt)

    def priority_agent(self, description):
        prompt = f"""
        You are an expert incident prioritization agent. You will be given a report of an incident complained about by a human user.
        Based on the severity and urgency of the incident, assign a priority level of Low, Medium, or High.
        High priority should be assigned to incidents that pose immediate danger to life or property, require urgent attention from emergency services, or have significant impact on public safety.
        Medium priority is for incidents that are serious but not immediately life-threatening
        Low priority is for minor incidents that do not require urgent attention but should be dealt with in time.

        Example 1:
        Report: Heavy traffic congestion observed near Tambaram Bus Stand during peak hours. The area experiences frequent vehicle pile-ups due to narrow lanes, improper parking by autos and buses, and poor traffic signal coordination. Pedestrian movement is also hindered as buses occupy most of the road space, causing long delays and safety concerns for commuters. Immediate attention is needed to improve signal timing, enforce parking rules, and streamline bus movement to reduce congestion.
        Priority: Medium

        Example 2:
        Report: Few jewelry were stolen at around 10 pm by 4 people wearing mask from my house. They threatened my family with a knife and took away all the valuables including gold and cash. The incident has left us traumatized and we request immediate action to catch the culprits and recover our stolen items.
        Priority: High

        Example 3:
        Report: A major accident occurred on the highway involving multiple vehicles. Several cars collided due to slippery road conditions caused by heavy rain. Emergency services were called to the scene, and several individuals sustained injuries ranging from minor cuts to serious fractures. Traffic was severely disrupted, leading to long delays. Authorities are investigating the cause of the accident and urging drivers to exercise caution in adverse weather conditions.
        Priority: High

        Example 4:
        Report: A streetlight on 5th Avenue has been flickering intermittently for the past week. While it does not pose an immediate danger, it affects visibility for pedestrians and drivers at night. The local authorities should schedule maintenance to fix the issue and ensure proper lighting in the area.
        Priority: Low

        Respond ONLY with one word: Low, Medium, or High.
        Assign priority (Low, Medium, High) for this incident: {description}
        """
        return self._call_gemini(prompt)

    def classify_incident(self, description):
        category = self.classification_agent(description)
        summary = self.summary_agent(description)
        priority = self.priority_agent(description)
        return {
            "category": category,
            "summary": summary,
            "priority": priority
        }
