"""
Database models for the CommunityWatch application.
"""

from typing import Dict, Any
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import JSON
from app import db

class User(UserMixin, db.Model):
    """
    User model for authentication and issue reporting.

    Attributes:
        id: Unique identifier for the user.
        username: Unique username for the user.
        email: Unique email address for the user.
        password_hash: Hashed password for authentication.
        reputation_points: User's reputation score based on contributions.
        is_moderator: Whether the user has moderator privileges.
        issues: Issues reported by the user.
        upvotes: Upvotes cast by the user.
        notifications: Notifications received by the user.
    """
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    reputation_points = db.Column(db.Integer, default=0)
    is_moderator = db.Column(db.Boolean, default=False)
    issues = db.relationship('Issue', back_populates='reporter', cascade='all, delete-orphan')  # Removed lazy='dynamic'
    upvotes = db.relationship('Upvote', back_populates='voter', lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password: str) -> None:
        """Set the user's password by hashing it."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify the provided password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    def add_notification(self, name: str, data: Dict[str, Any]) -> None:
        """
        Add a notification for the user.

        Args:
            name: The name/type of the notification.
            data: The notification data as a dictionary.
        """
        notification = Notification(name=name, data=data, user=self)
        db.session.add(notification)

    def get_notifications_since(self, since: float) -> list:
        """
        Retrieve notifications since a given timestamp.

        Args:
            since: Unix timestamp to filter notifications.

        Returns:
            List of notifications newer than the given timestamp.
        """
        return self.notifications.filter(Notification.timestamp > since).order_by(Notification.timestamp.asc()).all()

class Issue(db.Model):
    """
    Issue model for community-reported issues.

    Attributes:
        id: Unique identifier for the issue.
        category: Type of issue (e.g., Pothole, Graffiti).
        description: Detailed description of the issue.
        latitude: Latitude coordinate of the issue location.
        longitude: Longitude coordinate of the issue location.
        location_text: Optional human-readable location description.
        image_filename: Filename of the uploaded image (if any).
        timestamp: When the issue was reported.
        status: Current status of the issue (Reported, In Progress, Resolved).
        upvote_count: Number of upvotes received.
        embedding: AI-generated embedding for semantic search.
        geojson: Optional GeoJSON data for the issue location.
        reporter_id: Foreign key to the reporting user.
        reporter: The user who reported the issue.
        comments: Comments associated with the issue.
        upvotes: Upvotes associated with the issue.
    """
    __tablename__ = 'issue'

    VALID_CATEGORIES = ['Pothole', 'Graffiti', 'Streetlight', 'Litter', 'Other']

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    location_text = db.Column(db.String(200))
    image_filename = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(64), default='Reported', nullable=False)
    upvote_count = db.Column(db.Integer, default=0)
    embedding = db.Column(db.PickleType)
    geojson = db.Column(JSON)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reporter = db.relationship('User', back_populates='issues')
    comments = db.relationship('Comment', back_populates='issue', cascade='all, delete-orphan')
    upvotes = db.relationship('Upvote', back_populates='issue', cascade='all, delete-orphan')

    def generate_and_set_embedding(self) -> None:
        """
        Generate and set an AI embedding for the issue description.

        Note: Currently disabled due to performance concerns.
        """
        pass

class Comment(db.Model):
    """
    Comment model for user comments on issues.

    Attributes:
        id: Unique identifier for the comment.
        body: The comment text.
        timestamp: When the comment was posted.
        issue_id: Foreign key to the associated issue.
        author_id: Foreign key to the commenting user.
        issue: The associated issue.
        author: The user who posted the comment.
    """
    __tablename__ = 'comment'

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    issue_id = db.Column(db.Integer, db.ForeignKey('issue.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    issue = db.relationship('Issue', back_populates='comments')
    author = db.relationship('User')

class Upvote(db.Model):
    """
    Upvote model for user upvotes on issues.

    Attributes:
        id: Unique identifier for the upvote.
        voter_id: Foreign key to the user who upvoted.
        issue_id: Foreign key to the upvoted issue.
        voter: The user who upvoted.
        issue: The associated issue.
    """
    __tablename__ = 'upvote'

    id = db.Column(db.Integer, primary_key=True)
    voter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    issue_id = db.Column(db.Integer, db.ForeignKey('issue.id'), nullable=False)
    voter = db.relationship('User', back_populates='upvotes')
    issue = db.relationship('Issue', back_populates='upvotes')

class Notification(db.Model):
    """
    Notification model for user notifications.

    Attributes:
        id: Unique identifier for the notification.
        name: The type/name of the notification.
        data: JSON data associated with the notification.
        timestamp: When the notification was created.
        user_id: Foreign key to the user receiving the notification.
        user: The associated user.
    """
    __tablename__ = 'notification'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    data = db.Column(JSON, nullable=False)
    timestamp = db.Column(db.Float, default=lambda: datetime.utcnow().timestamp(), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', back_populates='notifications')

    def get_data(self) -> Dict[str, Any]:
        """Return the notification data as a dictionary."""
        return self.data or {}