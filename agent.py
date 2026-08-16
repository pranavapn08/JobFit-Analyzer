"""
Job-Fit Analyzer Agent

Given a job posting and a resume, this agent autonomously:
  1. Identifies the key required skills from the job posting
  2. For EACH skill, decides on its own whether to check the resume
     (using the check_resume_for_skill tool)
  3. For any skill it finds missing, decides on its own whether to look up
     a learning resource (using the recommend_learning_resource tool)
  4. Produces a final structured report: matched skills, gaps, and
     concrete next steps

This is genuinely agentic (not just one prompt) because the MODEL decides
which tools to call and when, based on what it finds in the job posting -
we don't hardcode "always check these 10 skills." Different job postings
will make the agent check different things.

Setup:
  1. pip install -r requirements.txt
  2. Get a free Gemini API key: https://aistudio.google.com/app/apikey
     (same place you got the key for SafeByte, if using the same account)
  3. Copy .env.example to .env and paste your key in
  4. Run: python3 agent.py

Usage:
  python3 agent.py --job sample_data/sample_soc_analyst_jd.txt --resume path/to/your_resume.pdf
  python3 agent.py --job "https://example.com/job-posting-url" --resume path/to/your_resume.pdf
"""

import os
import time
import argparse
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors

from tools import (
    load_resume,
    check_resume_for_skill,
    recommend_learning_resource,
    fetch_job_posting,
    extract_resume_text,
)

load_dotenv()

MAX_RETRIES = 4
INITIAL_BACKOFF_SECONDS = 5

SYSTEM_INSTRUCTION = """You are a Job-Fit Analysis Agent for a cybersecurity/SOC job candidate.

Given a job posting, your task is to:
1. Identify the key technical and soft skills required by the job posting.
2. For EACH skill you identify, call check_resume_for_skill to see if the candidate's
   resume already demonstrates it. Do this for every skill you find - don't skip any.
3. For any skill that comes back NOT found, call recommend_learning_resource to get a
   concrete, real resource for closing that gap.
4. Produce a final report with three sections:
   - MATCHED SKILLS: skills the resume already covers, with brief evidence
   - GAPS: skills missing from the resume, each with the learning resource you looked up
   - SUGGESTED RESUME ADDITIONS: 2-3 concrete bullet point ideas the candidate could add
     to their resume IF they already have informal experience with a gap skill, or
     honest note that they'd need to build a small project/complete a course first if
     they have zero experience with it. Never suggest claiming a skill the candidate
     doesn't actually have - only suggest making already-real experience more visible.

Be concise and practical. This is for a fresher job seeker, so be encouraging but honest
about real gaps rather than glossing over them.
"""


def build_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found. Copy .env.example to .env and add your key."
        )
    return genai.Client(api_key=api_key)


def send_message_with_retry(chat, prompt, max_retries=MAX_RETRIES, initial_backoff=INITIAL_BACKOFF_SECONDS):
    """
    Calls chat.send_message with automatic retry on transient server errors
    (503 UNAVAILABLE / high demand, and similar 5xx issues).

    Uses exponential backoff: waits 5s, then 10s, then 20s, then 40s between
    attempts, since retrying too fast into an overloaded server just makes
    the overload worse. Does NOT retry on 4xx client errors (like a bad API
    key or malformed request) - those won't fix themselves by waiting, so
    we fail fast on those instead of wasting time.
    """
    backoff = initial_backoff
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            return chat.send_message(prompt)
        except errors.ServerError as e:
            last_error = e
            if attempt == max_retries:
                break
            print(f"  Server busy (attempt {attempt}/{max_retries}): {e}")
            print(f"  Retrying in {backoff} seconds...")
            time.sleep(backoff)
            backoff *= 2  # exponential backoff
        except errors.ClientError:
            # 4xx errors (bad API key, invalid request, etc.) won't be fixed
            # by retrying - fail immediately with the real error instead of
            # wasting time and hiding the actual problem.
            raise

    raise RuntimeError(
        f"Gemini API is still unavailable after {max_retries} attempts. "
        f"This usually clears up within a few minutes - try again shortly. "
        f"Last error: {last_error}"
    )


def run_analysis(job_source: str, resume_path: str):
    print("Fetching job posting...")
    job_text = fetch_job_posting(job_source)
    print(f"  -> {len(job_text)} characters loaded")

    print("Extracting resume...")
    resume_text = extract_resume_text(resume_path)
    print(f"  -> {len(resume_text)} characters loaded")

    load_resume(resume_text)

    client = build_client()

    # Passing the tools list with automatic_function_calling enabled lets the
    # SDK handle the back-and-forth of "model requests a tool call -> we run
    # it -> feed result back to model" automatically. This is what makes the
    # workflow agentic rather than a single fixed prompt: the model decides
    # which skills to check and which resources to look up.
    # NOTE ON MODEL NAMES: Google deprecates and shuts down Gemini model
    # versions fairly often (gemini-2.0-flash was shut down June 1, 2026).
    # If this model string ever throws a 404 "no longer available" error,
    # check https://ai.google.dev/gemini-api/docs/models for the current
    # recommended replacement and swap it in here.
    chat = client.chats.create(
        model="gemini-3.6-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[check_resume_for_skill, recommend_learning_resource],
        ),
    )

    prompt = f"""Here is the job posting to analyze:

---
{job_text}
---

Analyze this against the candidate's resume (already loaded - use your tools to check it).
Produce the final report as described in your instructions."""

    print("\nAgent is analyzing (this may call multiple tools)...\n")
    response = chat.send_message(prompt)

    return response.text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job-Fit Analyzer Agent")
    parser.add_argument("--job", required=True, help="Job posting URL, or path to a .txt file with the posting")
    parser.add_argument("--resume", required=True, help="Path to your resume (PDF or .txt)")
    args = parser.parse_args()

    job_source = args.job
    if os.path.isfile(job_source):
        with open(job_source, "r", encoding="utf-8") as f:
            job_source = f.read()

    report = run_analysis(job_source, args.resume)

    print("=" * 70)
    print("  JOB-FIT ANALYSIS REPORT")
    print("=" * 70)
    print(report)
