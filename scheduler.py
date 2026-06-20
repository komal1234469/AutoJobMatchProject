"""
Background scheduler — checks for new high-match jobs and emails users.

WHY THIS IS A SEPARATE SCRIPT:
The web app (app.py) only does work when a user visits a page or clicks
something. Sending you an email about a job you haven't searched for yet
requires something running on its own, on a schedule, even when nobody
has the site open. That's what this script does.

HOW TO RUN IT:
- For testing: just run `python scheduler.py` and leave the terminal open.
- For real 24/7 use: deploy this as a "worker" process on a free host
  like Render or Railway, or run it via cron on a machine that's always on.
  It is NOT something that runs inside claude.ai or a browser tab.

WHAT IT DOES:
For every user with notify_email=True, it re-searches jobs for their
preferred_role, scores them, and if a job scores at/above their
match_threshold AND hasn't been emailed before, sends one email and
marks it as notified so they don't get duplicate alerts.
"""
import time
import schedule
from dotenv import load_dotenv
load_dotenv()

from app import app
from models import db, User, Profile, JobMatch
from matching import compute_match_score
from job_search import search_jobs_for_query
from email_notify import send_match_alert

CHECK_INTERVAL_MINUTES = 1  # how often to check for new matches


def check_all_users():
    with app.app_context():
        users = User.query.join(Profile).filter(Profile.notify_email == True).all()
        print(f"[scheduler] Checking {len(users)} users for new matches...")

        for user in users:
            profile = user.profile
            if not profile or not profile.resume_raw_text or not profile.preferred_role:
                continue

            try:
                jobs = search_jobs_for_query(profile.preferred_role, profile.preferred_location or "")
            except Exception as e:
                print(f"[scheduler] Search failed for user {user.id}: {e}")
                continue

            for job in jobs:
                # Skip if we've already recorded this exact job for this user
                existing = JobMatch.query.filter_by(user_id=user.id, job_id=str(job.get("id", ""))).first()
                if existing:
                    continue

                score, matched_skills, _ = compute_match_score(profile, job["title"], job["description"])

                match = JobMatch(
                    user_id=user.id,
                    job_id=str(job.get("id", "")),
                    job_title=job["title"],
                    company=job["company"],
                    location=job.get("location", ""),
                    apply_url=job.get("apply_url", ""),
                    job_description=job["description"],
                    match_score=score,
                )
                db.session.add(match)

                if score >= profile.match_threshold:
                    try:
                        send_match_alert(
                            to_email=user.email,
                            job_title=job["title"],
                            company=job["company"],
                            score=score,
                            apply_url=job.get("apply_url", ""),
                            matched_skills=matched_skills,
                        )
                        match.notified = True
                        print(f"[scheduler] Emailed {user.email} about {job['title']} ({score}%)")
                    except Exception as e:
                        print(f"[scheduler] Email failed for user {user.id}: {e}")

            db.session.commit()


if __name__ == "__main__":
    print("[scheduler] Starting. Checking every", CHECK_INTERVAL_MINUTES, "minutes.")
    check_all_users()  # run once immediately on startup
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_all_users)

    while True:
        schedule.run_pending()
        time.sleep(30)
