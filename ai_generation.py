"""
AI generation module.
Calls the Claude API to generate a tailored resume summary + cover letter
for a specific job, using the user's existing profile/resume as the source
of truth (the AI is told not to invent experience the user doesn't have).
"""
import os
import requests
import google.generativeai as genai





def _call_claude(system_prompt, user_prompt, max_tokens=1500):
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system_prompt
    )
    response = model.generate_content(user_prompt)
    return response.text


def generate_cover_letter(profile, job_title, company, job_description, matched_skills):
    system_prompt = (
        "You write concise, honest, specific cover letters. You NEVER invent "
        "experience, employers, job titles, or skills that aren't in the "
        "candidate's provided background. If the background is thin for this "
        "role, focus on genuine transferable strengths rather than fabricating "
        "anything. Keep it to 3-4 short paragraphs, professional tone, no "
        "generic filler like 'I am writing to express my interest'."
    )

    user_prompt = f"""Candidate background (resume text):
{profile.resume_raw_text[:3000]}

Candidate's known skills: {', '.join(profile.get_skills())}
Years of experience: {profile.years_of_experience or 'not specified'}

Job applying for: {job_title} at {company}
Job description:
{job_description[:2000]}

Skills from the job that the candidate already has: {', '.join(matched_skills) if matched_skills else 'none directly matched - find genuine transferable strengths'}

Write a tailored cover letter for this specific job using only the candidate's real background above."""

    return _call_claude(system_prompt, user_prompt)


def generate_tailored_resume_summary(profile, job_title, company, job_description, matched_skills):
    """
    Generates a tailored professional summary + reordered/emphasized skills
    section to put at the top of the candidate's resume for this specific job.
    This is NOT a full resume rewrite - it's the high-impact part that's
    worth tailoring per application, layered on top of their real resume.
    """
    system_prompt = (
        "You write tailored resume professional summaries. You NEVER invent "
        "experience, metrics, employers, or skills not present in the "
        "candidate's actual background. You only re-emphasize and rephrase "
        "what's genuinely true, choosing what to highlight based on the "
        "target job."
    )

    user_prompt = f"""Candidate's real resume text:
{profile.resume_raw_text[:3000]}

Candidate's known skills: {', '.join(profile.get_skills())}

Target job: {job_title} at {company}
Job description:
{job_description[:2000]}

Matched skills already confirmed present: {', '.join(matched_skills) if matched_skills else 'none directly matched'}

Produce:
1. A 3-sentence professional summary tailored to this job (using only real background)
2. A reordered list of the candidate's skills, most-relevant-to-this-job first (only from their actual skill list, do not add new ones)

Format as plain text with two clear sections."""

    return _call_claude(system_prompt, user_prompt)


def generate_application_package(profile, job_title, company, job_description, matched_skills):
    """Convenience wrapper that generates both pieces in one call point."""
    cover_letter = generate_cover_letter(profile, job_title, company, job_description, matched_skills)
    resume_summary = generate_tailored_resume_summary(profile, job_title, company, job_description, matched_skills)
    return {
        "cover_letter": cover_letter,
        "resume_summary": resume_summary,
    }
