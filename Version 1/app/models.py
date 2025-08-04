"""Defines the database models for the CommunityWatch application."""

import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager

# A central list of valid issue categories
VALID_CATEGORIES = [
    'Blocked Drainage', 'Broken Park Bench', 'Broken Streetlight',
    'Broken Traffic Light', 'Damaged Public Property', 'Faded Road Markings',
    'Fallen Tree', 'Flooding', 'Graffiti', 'Leaking Pipe',
    'Overgrown Vegetation', 'Pothole', 'Power Line Down',
    'Stray Animal Concern', 'Waste Dumping', 'Other'
]


@login_manager.user_loader
def load_user(user_id):
    """User loader callback for Flask-Login."""
    return db.session.get(User, int(user_id))


class User(UserMixin, db.Model):
    """User model for the database."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(256))
    is_moderator = db.Column(db.Boolean, default=False)
    reputation_points = db.Column(db.Integer, nullable=False, default=0)

    issues = db.relationship('Issue', backref='reporter', lazy='dynamic')
    upvotes = db.relationship('Upvote', backref='voter', lazy='dynamic')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def add_notification(self, name, data):
        """Adds a new notification for the user."""
        n = Notification(name=name, payload_json=json.dumps(data), user=self)
        db.session.add(n)
        return n


class Notification(db.Model):
    """Represents an in-app notification for a user."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.Float, index=True, default=datetime.utcnow().timestamp)
    payload_json = db.Column(db.Text)

    def get_data(self):
        return json.loads(str(self.payload_json))


class Upvote(db.Model):
    """Association table for user upvotes on issues."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    issue_id = db.Column(db.Integer, db.ForeignKey('issue.id'))


class Comment(db.Model):
    """Comment model for discussions on issues."""
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    issue_id = db.Column(db.Integer, db.ForeignKey('issue.id'))


class Issue(db.Model):
    """Issue model for map pins."""
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    upvote_count = db.Column(db.Integer, default=0)
    image_filename = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), index=True, default='Reported')
    embedding = db.Column(db.JSON, nullable=True)
    geojson = db.Column(db.JSON, nullable=True)
    location_text = db.Column(db.String(250), nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    comments = db.relationship('Comment', backref='issue', lazy='dynamic', cascade="all, delete-orphan")

    def generate_and_set_embedding(self):
        """Generates and saves a vector embedding for the issue."""
        from app import ai_services
        text_to_embed = f"Category: {self.category}\nDescription: {self.description}"
        self.embedding = ai_services.generate_embedding(text_to_embed)
