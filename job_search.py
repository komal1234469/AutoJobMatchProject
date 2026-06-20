"""
Job search integration - Adzuna API.

Why Adzuna and not scraping LinkedIn/Indeed directly:
- It's a real, free, official API meant for exactly this use case
- Scraping or automating submissions on LinkedIn/Indeed/Naukri violates
  their Terms of Service and risks your account being banned - this app
  deliberately avoids that path
- Adzuna aggregates listings from many boards (including some that
  originate on Indeed/LinkedIn) and gives back a clean structured JSON

Sign up free at https://developer.adzuna.com to get APP_ID + APP_KEY.
"""
import os
import requests

ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY")
ADZUNA_COUNTRY = os.environ.get("ADZUNA_COUNTRY", "in")  # "in" = India, "us" = USA, "gb" = UK, etc.

BASE_URL = f"https://api.adzuna.com/v1/api/jobs/{ADZUNA_COUNTRY}/search/1"


def search_jobs_for_query(query, location="", results_per_page=15):
    """
    query: company name OR role/keyword (e.g. "Google" or "Python developer")
    location: city/region, or "remote" (Adzuna doesn't have a strict remote
              filter - we just pass it through as a location term, which
              works reasonably well since many remote postings mention it)

    Returns a list of dicts: {id, title, company, location, description, apply_url}
    """
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        raise RuntimeError(
            "ADZUNA_APP_ID / ADZUNA_APP_KEY are not set. "
            "Sign up free at https://developer.adzuna.com and set these "
            "as environment variables."
        )

    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": query,
        "results_per_page": results_per_page,
        "content-type": "application/json",
    }
    if location and location.lower() != "remote":
        params["where"] = location

    response = requests.get(BASE_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    jobs = []
    for item in data.get("results", []):
        jobs.append({
            "id": str(item.get("id", "")),
            "title": item.get("title", "").strip(),
            "company": item.get("company", {}).get("display_name", "Unknown"),
            "location": item.get("location", {}).get("display_name", ""),
            "description": item.get("description", ""),
            "apply_url": item.get("redirect_url", ""),
            "salary_min": item.get("salary_min"),
            "salary_max": item.get("salary_max"),
        })
    return jobs
