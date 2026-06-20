"""
Matching engine.
Scores a job description against a user's profile (skills + experience text)
using TF-IDF cosine similarity, blended with a direct skill-overlap score.

Why this approach over a pure LLM call:
- Free, fast, no API cost - good for scoring many jobs at once
- Deterministic and explainable (you can show *why* a job scored well)
- The LLM is better spent on the *generation* step (resume/cover letter),
  where it adds the most value.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def skill_overlap_score(user_skills, job_text):
    """% of the user's skills that appear in the job description."""
    if not user_skills:
        return 0.0
    job_text_lower = job_text.lower()
    matched = [s for s in user_skills if s.lower() in job_text_lower]
    return len(matched) / len(user_skills), matched


def text_similarity_score(profile_text, job_text):
    """Cosine similarity between profile text and job description via TF-IDF."""
    if not profile_text.strip() or not job_text.strip():
        return 0.0
    vectorizer = TfidfVectorizer(stop_words="english", max_features=500)
    try:
        tfidf_matrix = vectorizer.fit_transform([profile_text, job_text])
        sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return float(sim)
    except ValueError:
        # happens if vocab is empty after stopword removal
        return 0.0


def compute_match_score(profile, job_title, job_description):
    """
    Returns (score_0_to_100, matched_skills_list, breakdown_dict)

    Blend: 60% skill overlap + 40% semantic similarity.
    Skill overlap is weighted higher because it's the more concrete,
    explainable signal for "am I qualified for this job".
    """
    user_skills = profile.get_skills()
    job_text = f"{job_title} {job_description}"

    overlap_pct, matched_skills = skill_overlap_score(user_skills, job_text)

    profile_text_parts = [profile.resume_raw_text or ""]
    profile_text_parts.extend(user_skills)
    profile_text = " ".join(profile_text_parts)

    similarity = text_similarity_score(profile_text, job_text)

    blended = (0.6 * overlap_pct) + (0.4 * similarity)
    score = round(blended * 100)
    score = max(0, min(100, score))

    breakdown = {
        "skill_overlap_pct": round(overlap_pct * 100),
        "semantic_similarity_pct": round(similarity * 100),
        "matched_skills": matched_skills,
    }

    return score, matched_skills, breakdown
