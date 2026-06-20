# JobMatch

Upload your resume once. Search for a company or role. Get every result
scored against your real skills, generate a tailored resume summary +
cover letter in one click, and get emailed when something matches strongly.

## What this is — and isn't

This **does**:
- Pull live job listings via the Adzuna API (free, legitimate, no scraping)
- Score every job against your saved profile automatically
- Generate a tailored resume summary + cover letter per job using AI
- Email you when a new job matches above your chosen threshold
- Let you log in with Google or email/password
- Remember everything after one resume upload — no retyping

This **does not**:
- Auto-submit applications on LinkedIn/Indeed/Naukri on your behalf.
  Those platforms block automated submissions and doing this risks your
  account. The final "submit" click on the job site is always yours.

## Project structure

```
backend/
  app.py              Main Flask app - routes, auth
  models.py           Database models (User, Profile, JobMatch)
  resume_parser.py     Extracts skills/experience/education from PDF/DOCX
  matching.py          Scores jobs against your profile
  job_search.py         Adzuna API integration
  ai_generation.py     Generates tailored resume summary + cover letter
  email_notify.py      Sends match-alert emails
  scheduler.py         Background worker - checks for new matches periodically
  templates/           HTML pages
  static/style.css      All styling
  uploads/             Uploaded resumes (gitignore this in real use)
requirements.txt
```

## 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

## 2. Set environment variables

Create a `.env` file or export these in your terminal before running:

```bash
# Required - Flask session security
export FLASK_SECRET_KEY="any-long-random-string"

# Required - AI generation (resume summary + cover letter)
export ANTHROPIC_API_KEY="sk-ant-..."
# Get one at https://console.anthropic.com

# Required - job search data source
export ADZUNA_APP_ID="..."
export ADZUNA_APP_KEY="..."
export ADZUNA_COUNTRY="in"   # "in" for India, "us", "gb", etc.
# Sign up free at https://developer.adzuna.com (instant approval)

# Required for "Continue with Google" login
export GOOGLE_CLIENT_ID="...apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="..."

# Required for email match alerts
export SMTP_USER="youraddress@gmail.com"
export SMTP_PASSWORD="16-char-app-password"
```

### Getting a Google OAuth Client ID (free, ~5 minutes)

1. Go to https://console.cloud.google.com/
2. Create a new project (top-left dropdown → New Project)
3. Go to **APIs & Services → OAuth consent screen** → choose "External" → fill app name + your email → save
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
5. Application type: **Web application**
6. Under **Authorized redirect URIs**, add:
   - `http://localhost:5000/auth/google/callback` (for local testing)
   - `https://yourdomain.com/auth/google/callback` (once deployed)
7. Copy the **Client ID** and **Client Secret** into your environment variables

### Getting an Adzuna API key (free, instant)

1. Go to https://developer.adzuna.com
2. Sign up — you get an `app_id` and `app_key` immediately, no approval wait
3. Free tier covers generous request volume for personal use

### Getting a Gmail App Password (for email alerts)

1. Turn on 2-Step Verification on your Google account (required first)
2. Go to https://myaccount.google.com/apppasswords
3. Create an app password for "Mail" — copy the 16-character code
4. Use your Gmail address as `SMTP_USER` and that code as `SMTP_PASSWORD`
   (not your real Gmail password)

## 3. Run the web app

```bash
cd backend
python app.py
```

Visit `http://localhost:5000`. Sign up, upload a resume, fill the
one-time extra-details form, and you'll land on the dashboard.

## 4. Run the background email-alert worker (separate process)

This is **not** part of the web app request/response cycle — it has to
run continuously on its own, since it checks for new matching jobs even
when nobody has the site open.

```bash
cd backend
python scheduler.py
```

Leave this running in a separate terminal (or deploy it as a "worker"
process on a host like Render/Railway, or set it up with `cron` on a
machine that stays on). It checks every 60 minutes by default — change
`CHECK_INTERVAL_MINUTES` in `scheduler.py` if you want a different cadence.

## Notes on the matching algorithm

`matching.py` blends two signals:
- **60% skill overlap** — how many of your detected skills appear in the
  job description (concrete, explainable)
- **40% semantic similarity** — TF-IDF cosine similarity between your
  resume text and the job description (catches relevant context that
  isn't an exact skill-keyword match)

This is intentionally not a pure LLM call for scoring — it's free, fast,
and good enough to rank many jobs at once. The LLM (Claude) is reserved
for the generation step, where tailored writing actually benefits from it.

## Extending this

Ideas if you want to keep building:
- Add a "Download as Word doc" button using the docx generation skill,
  so the tailored resume/cover letter can be exported as a real .docx
- Add pagination / more filters to the search (salary range, remote-only)
- Track application status (Applied / Interviewing / Rejected) per job
- Swap the rule-based resume parser for an LLM-based extraction call if
  you want more robust parsing of unusually formatted resumes
