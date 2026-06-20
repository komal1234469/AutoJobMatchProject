"""
Database models for JobMatch.
Uses SQLite via SQLAlchemy - simple, file-based, zero setup.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Core user account - supports both email/password and Google OAuth login."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)  # null if Google-only signup
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One-to-one relationship with profile
    profile = db.relationship("Profile", backref="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class Profile(db.Model):
    """
    Holds everything extracted from the resume + any extra fields
    collected once at signup. This is the data reused for every
    search / match / generation - the user should never have to
    retype this.
    """
    __tablename__ = "profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    full_name = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    location = db.Column(db.String(255))

    # Stored as JSON text - flexible lists
    skills = db.Column(db.Text, default="[]")          # e.g. ["Python", "SQL", "React"]
    experience = db.Column(db.Text, default="[]")        # list of {title, company, duration, description}
    education = db.Column(db.Text, default="[]")         # list of {degree, institution, year}

    resume_raw_text = db.Column(db.Text)                  # full extracted text, used for AI generation
    resume_filename = db.Column(db.String(255))

    # Extra fields collected once, since resumes don't usually contain these
    preferred_role = db.Column(db.String(255))
    preferred_location = db.Column(db.String(255))
    expected_salary = db.Column(db.String(100))
    notice_period = db.Column(db.String(100))
    years_of_experience = db.Column(db.String(50))

    # Notification preference
    notify_email = db.Column(db.Boolean, default=True)
    match_threshold = db.Column(db.Integer, default=75)  # % threshold for email alerts

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_skills(self):
        return json.loads(self.skills or "[]")

    def set_skills(self, skills_list):
        self.skills = json.dumps(skills_list)

    def get_experience(self):
        return json.loads(self.experience or "[]")

    def set_experience(self, exp_list):
        self.experience = json.dumps(exp_list)

    def get_education(self):
        return json.loads(self.education or "[]")

    def set_education(self, edu_list):
        self.education = json.dumps(edu_list)

    def is_complete(self):
        """Check if the extra fields (not in resume) have been filled."""
        return bool(self.preferred_role and self.years_of_experience)


class JobMatch(db.Model):
    """
    Stores jobs that were seen + their match score, so we:
    1. Don't re-email the user about the same job twice
    2. Can show match history in the dashboard
    """
    __tablename__ = "job_matches"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    job_id = db.Column(db.String(255))          # Indeed job id
    job_title = db.Column(db.String(255))
    company = db.Column(db.String(255))
    location = db.Column(db.String(255))
    apply_url = db.Column(db.Text)
    job_description = db.Column(db.Text)

    match_score = db.Column(db.Integer)          # 0-100
    notified = db.Column(db.Boolean, default=False)

    generated_resume = db.Column(db.Text, nullable=True)
    generated_cover_letter = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
