"""
Tools available to the Job-Fit Analysis Agent.

Each function here is exposed to the Gemini model as something it can
choose to call on its own, mid-reasoning, rather than us hardcoding when
each one runs. This is what makes it an "agent" rather than a single
prompt-and-response script: the model decides, for each skill it finds
in the job posting, whether to check the resume and whether to look up
a learning resource.
"""

import re
import requests
from bs4 import BeautifulSoup
import pdfplumber

# Global state the tools read from - set once per run by load_resume().
# (Kept simple/global rather than passed as arguments because the Gemini
# SDK's automatic function-calling only passes the arguments the MODEL
# decides to supply - it won't know to pass us the resume text itself.)
_RESUME_TEXT = ""

# A small curated knowledge base mapping common SOC/security skills to
# real learning resources. This is intentionally NOT an LLM call - it's
# a fast, reliable lookup tool, which is exactly the kind of thing real
# agents use tools for instead of relying on the model to "remember"
# accurate URLs (LLMs are unreliable at recalling exact links).
LEARNING_RESOURCES = {
    "siem": "TryHackMe 'SOC Level 1' path - covers Splunk and SIEM fundamentals",
    "splunk": "Splunk Fundamentals 1 (free, self-paced on Splunk's own training site)",
    "wireshark": "TryHackMe 'Wireshark: The Basics' room",
    "incident response": "TryHackMe 'SOC Level 1' path, Incident Response module",
    "threat intelligence": "TryHackMe 'Threat Intelligence Tools' room",
    "vulnerability assessment": "TryHackMe 'Vulnerability Research' module + Nessus Essentials (free)",
    "network security": "Google Cybersecurity Certificate, 'Networking' course",
    "nmap": "TryHackMe 'Nmap' room",
    "linux": "TryHackMe 'Linux Fundamentals' path",
    "python": "You already have this - no action needed",
    "log analysis": "TryHackMe 'SOC Level 1' path, Log Analysis module",
    "phishing": "TryHackMe 'Phishing Analysis Fundamentals' room",
    "malware analysis": "TryHackMe 'Intro to Malware Analysis' room",
    "compliance": "Google Cybersecurity Certificate, 'Play It Safe: Manage Security Risks' course",
    "cloud security": "AWS Cloud Practitioner Essentials (free) or Azure Fundamentals (AZ-900)",
}


def load_resume(resume_text: str):
    """Loads resume text into module state so tools can check against it."""
    global _RESUME_TEXT
    _RESUME_TEXT = resume_text.lower()


def check_resume_for_skill(skill: str) -> dict:
    """
    Checks whether a given skill/keyword appears in the candidate's resume.

    Args:
        skill: The skill or keyword to search for, e.g. "SIEM" or "Python".

    Returns:
        A dict with 'found' (bool) and, if found, the surrounding context
        so the agent can judge how substantively it's mentioned (a bullet
        point vs. just a passing word).
    """
    skill_lower = skill.lower().strip()
    if skill_lower in _RESUME_TEXT:
        idx = _RESUME_TEXT.find(skill_lower)
        start = max(0, idx - 60)
        end = min(len(_RESUME_TEXT), idx + 60)
        context = _RESUME_TEXT[start:end].strip()
        return {"found": True, "context": f"...{context}..."}
    return {"found": False, "context": None}


def recommend_learning_resource(skill: str) -> dict:
    """
    Looks up a curated, real learning resource for a given skill gap.

    Args:
        skill: The skill the candidate is missing, e.g. "SIEM".

    Returns:
        A dict with a 'resource' string - either a specific recommendation
        or a generic fallback if the skill isn't in the curated list.
    """
    skill_lower = skill.lower().strip()
    for key, resource in LEARNING_RESOURCES.items():
        if key in skill_lower or skill_lower in key:
            return {"resource": resource}
    return {"resource": f"Search TryHackMe or the Google Cybersecurity Certificate for '{skill}' - no curated resource on file yet."}


def fetch_job_posting(source: str) -> str:
    """
    Fetches job posting text from either a URL or treats the input as
    already-pasted raw text if it doesn't look like a URL.

    Args:
        source: Either a job posting URL, or the pasted job description text.

    Returns:
        Plain text of the job posting, with HTML stripped if it was a URL.
    """
    if source.strip().lower().startswith(("http://", "https://")):
        headers = {"User-Agent": "Mozilla/5.0 (JobFitAgent/1.0)"}
        response = requests.get(source, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
        return text
    else:
        return source


def extract_resume_text(path: str) -> str:
    """
    Extracts plain text from a resume file. Supports PDF and plain .txt.

    Args:
        path: File path to the resume.

    Returns:
        The extracted text content.
    """
    if path.lower().endswith(".pdf"):
        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    else:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
