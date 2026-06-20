"""
JobMatch - main Flask application.

Run with:
    export ANTHROPIC_API_KEY=sk-ant-...
    export GOOGLE_CLIENT_ID=...
    export GOOGLE_CLIENT_SECRET=...
    export FLASK_SECRET_KEY=some-random-string
    python app.py

See README.md for full setup instructions (Google OAuth, SMTP, etc.)
"""
import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth

from models import db, User, Profile, JobMatch
from resume_parser import parse_resume
from matching import compute_match_score
from ai_generation import generate_application_package
from job_search import search_jobs_for_query  # wraps the Indeed connector

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXTENSIONS = {"pdf", "docx"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///jobmatch.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB upload cap

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---- Google OAuth setup ----
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()

        if not email or not password:
            flash("Email and password are required.", "error")
            return redirect(url_for("signup"))

        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists. Try logging in.", "error")
            return redirect(url_for("login"))

        user = User(email=email, name=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Create an empty profile shell now; gets filled on resume upload
        profile = Profile(user_id=user.id)
        db.session.add(profile)
        db.session.commit()

        login_user(user)
        return redirect(url_for("upload_resume"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/login/google")
def login_google():
    redirect_uri = url_for("auth_google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def auth_google_callback():
    token = google.authorize_access_token()
    user_info = token.get("userinfo")
    if not user_info:
        flash("Google sign-in failed. Please try again.", "error")
        return redirect(url_for("login"))

    google_id = user_info["sub"]
    email = user_info["email"]
    name = user_info.get("name", "")

    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()

    if not user:
        user = User(email=email, name=name, google_id=google_id)
        db.session.add(user)
        db.session.commit()
        profile = Profile(user_id=user.id)
        db.session.add(profile)
        db.session.commit()
    elif not user.google_id:
        user.google_id = google_id
        db.session.commit()

    login_user(user)

    if not user.profile or not user.profile.resume_raw_text:
        return redirect(url_for("upload_resume"))
    return redirect(url_for("dashboard"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Resume upload + one-time extra details
# ---------------------------------------------------------------------------

@app.route("/upload-resume", methods=["GET", "POST"])
@login_required
def upload_resume():
    if request.method == "POST":
        file = request.files.get("resume")
        if not file or file.filename == "":
            flash("Please choose a file.", "error")
            return redirect(url_for("upload_resume"))

        if not allowed_file(file.filename):
            flash("Only PDF or DOCX files are supported.", "error")
            return redirect(url_for("upload_resume"))

        filename = secure_filename(f"user{current_user.id}_{file.filename}")
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        try:
            parsed = parse_resume(filepath)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("upload_resume"))

        profile = current_user.profile
        if not profile:
            profile = Profile(user_id=current_user.id)
            db.session.add(profile)

        profile.full_name = parsed["full_name"] or current_user.name
        profile.phone = parsed["phone"]
        profile.set_skills(parsed["skills"])
        profile.set_experience(parsed["experience"])
        profile.set_education(parsed["education"])
        profile.resume_raw_text = parsed["raw_text"]
        profile.resume_filename = filename
        db.session.commit()

        return redirect(url_for("extra_details"))

    return render_template("upload_resume.html")


@app.route("/extra-details", methods=["GET", "POST"])
@login_required
def extra_details():
    """
    One-time short form for fields resumes don't usually contain
    (preferred role, location, salary, notice period). Asked once,
    right after signup+upload, never again unless user edits profile.
    """
    profile = current_user.profile

    if request.method == "POST":
        profile.preferred_role = request.form.get("preferred_role", "").strip()
        profile.preferred_location = request.form.get("preferred_location", "").strip()
        profile.expected_salary = request.form.get("expected_salary", "").strip()
        profile.notice_period = request.form.get("notice_period", "").strip()
        profile.years_of_experience = request.form.get("years_of_experience", "").strip()
        profile.notify_email = bool(request.form.get("notify_email"))
        profile.match_threshold = int(request.form.get("match_threshold", 75))
        db.session.commit()
        return redirect(url_for("dashboard"))

    return render_template("extra_details.html", profile=profile)


@app.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    """Lets the user update skills/experience/preferences any time, without re-uploading."""
    profile = current_user.profile

    if request.method == "POST":
        skills_raw = request.form.get("skills", "")
        profile.set_skills([s.strip() for s in skills_raw.split(",") if s.strip()])
        profile.preferred_role = request.form.get("preferred_role", "").strip()
        profile.preferred_location = request.form.get("preferred_location", "").strip()
        profile.expected_salary = request.form.get("expected_salary", "").strip()
        profile.notice_period = request.form.get("notice_period", "").strip()
        profile.years_of_experience = request.form.get("years_of_experience", "").strip()
        profile.notify_email = bool(request.form.get("notify_email"))
        profile.match_threshold = int(request.form.get("match_threshold", 75))
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_profile.html", profile=profile, skills=", ".join(profile.get_skills()))


# ---------------------------------------------------------------------------
# Dashboard + search + matching
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    profile = current_user.profile
    if not profile or not profile.resume_raw_text:
        return redirect(url_for("upload_resume"))

    recent_matches = (
        JobMatch.query.filter_by(user_id=current_user.id)
        .order_by(JobMatch.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template("dashboard.html", profile=profile, matches=recent_matches)


@app.route("/search", methods=["POST"])
@login_required
def search():
    """
    User types a company name or role. We pull live jobs, score each
    against the saved profile, and return ranked results - no extra
    input needed from the user.
    """
    query = request.form.get("query", "").strip()
    if not query:
        return jsonify({"error": "Please enter a company name or role."}), 400

    profile = current_user.profile
    location = profile.preferred_location or "remote"

    try:
        jobs = search_jobs_for_query(query, location)
    except Exception as e:
        return jsonify({"error": f"Job search failed: {e}"}), 502

    results = []
    for job in jobs:
        score, matched_skills, breakdown = compute_match_score(
            profile, job["title"], job["description"]
        )
        match = JobMatch(
            user_id=current_user.id,
            job_id=job.get("id", ""),
            job_title=job["title"],
            company=job["company"],
            location=job.get("location", ""),
            apply_url=job.get("apply_url", ""),
            job_description=job["description"],
            match_score=score,
        )
        db.session.add(match)
        db.session.flush()  # get match.id without full commit yet

        results.append({
            "match_id": match.id,
            "title": job["title"],
            "company": job["company"],
            "location": job.get("location", ""),
            "apply_url": job.get("apply_url", ""),
            "score": score,
            "matched_skills": matched_skills,
        })

    db.session.commit()
    results.sort(key=lambda r: r["score"], reverse=True)
    return jsonify({"results": results})


@app.route("/generate/<int:match_id>", methods=["POST"])
@login_required
def generate(match_id):
    """
    The 'one click' step: generates a tailored resume summary + cover
    letter for this specific job, using the saved profile - no new
    input required from the user.
    """
    match = JobMatch.query.filter_by(id=match_id, user_id=current_user.id).first()
    if not match:
        return jsonify({"error": "Job not found."}), 404

    profile = current_user.profile
    matched_skills = [s for s in profile.get_skills() if s.lower() in match.job_description.lower()]

    try:
        package = generate_application_package(
            profile, match.job_title, match.company, match.job_description, matched_skills
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    match.generated_resume = package["resume_summary"]
    match.generated_cover_letter = package["cover_letter"]
    db.session.commit()

    return jsonify({
        "resume_summary": package["resume_summary"],
        "cover_letter": package["cover_letter"],
        "apply_url": match.apply_url,
    })


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
