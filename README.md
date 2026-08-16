# Job-Fit Analyzer Agent

An autonomous AI agent that reads a job posting, checks it against your resume, and tells you exactly what's missing — and how to close the gap — using Gemini's function-calling so the model decides for itself which checks to run.

## Why this exists

Most "AI resume checkers" are a single prompt: paste your resume and a job description, get back a paragraph. This project takes a different approach — the model is given real tools it can call on its own, mid-reasoning, and decides which ones to use based on what it actually finds in the posting. A SOC analyst job posting makes it check completely different things than a Full Stack Developer posting would, without any hardcoded logic telling it to.

I built this while job hunting for SOC/cybersecurity analyst roles, and use it on real job postings as part of my own application process.

## How it works

1. **Fetches the job posting** — either from a URL (scraped and cleaned) or pasted text
2. **Extracts resume text** — from a PDF or plain text file
3. **The agent reasons through the posting** and identifies required skills
4. For **each** skill it identifies, it decides whether to call `check_resume_for_skill()` — a tool that searches the actual resume text
5. For any skill that comes back missing, it decides whether to call `recommend_learning_resource()` — a tool backed by a curated list of real learning resources (TryHackMe rooms, certification courses, etc.), not a hallucinated link
6. Produces a structured report: matched skills (with evidence), gaps (with real resources to close them), and honest suggestions for resume additions — the agent is explicitly instructed never to suggest claiming a skill the candidate doesn't actually have

## Tech stack

- **Python 3**
- **Google Gemini API** (`google-genai`) — function-calling / tool use
- **pdfplumber** — resume PDF text extraction
- **BeautifulSoup + requests** — job posting URL scraping
- **python-dotenv** — environment config

## Setup

```bash
git clone <this-repo-url>
cd jobfit-agent
pip install -r requirements.txt
cp .env.example .env
```

Get a free Gemini API key at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) and add it to `.env`:

```
GEMINI_API_KEY=your_actual_key_here
```

## Usage

```bash
# Against the included sample job posting
python3 agent.py --job sample_data/sample_soc_analyst_jd.txt --resume path/to/your_resume.pdf

# Against a real job posting URL
python3 agent.py --job "https://example.com/some-job-posting" --resume path/to/your_resume.pdf
```

Works with PDF or plain text resumes.

## Sample output

```
### MATCHED SKILLS
- Scripting Knowledge (Python) & Automation
  Evidence: Found in the SafeByte project ("Python, Flask...").

### GAPS
1. SIEM (Splunk / QRadar)
   Resource: Splunk Fundamentals 1 (free, self-paced)
2. Wireshark & Network Traffic Analysis
   Resource: TryHackMe 'Wireshark: The Basics' room
...

### SUGGESTED RESUME ADDITIONS
...
```

## Reliability

The Gemini API occasionally returns transient server errors under high load. `agent.py` automatically retries with exponential backoff (up to 4 attempts) on server-side failures, while failing fast on client errors (like an invalid API key or exhausted quota) that retrying wouldn't fix.

## Testing & validation

Tested against 10 real job postings spanning SOC analyst and software development roles. Flagged results were manually spot-checked against a subset of these postings, with all spot-checked gap/match flags confirmed accurate. This wasn't a formal, statistically rigorous benchmark — it's an honest reflection of testing done during development, not a claim of exhaustive validation across every run.

## Known limitations

- Free-tier Gemini API quota (20 requests/day at time of writing) can be hit quickly during heavy testing, since each analysis makes multiple tool-calling requests, not just one
- The curated learning-resource list currently covers common SOC/security skills; unlisted skills fall back to a generic suggestion
- Not a formal benchmark — accuracy was manually verified on a sample of runs, not every run

## Possible extensions

- Batch mode to analyze and rank several saved job postings at once
- Track closed skill gaps over time across repeated runs
- Compare against multiple resume versions and recommend which fits a given posting best

## License

MIT
