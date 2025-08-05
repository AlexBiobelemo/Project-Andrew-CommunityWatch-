"""
Background tasks for the CommunityWatch application.
"""

from datetime import datetime, timedelta
from sqlalchemy import select
from app import db
from app.models import Issue

def delete_old_issues(app) -> None:
    """
    Delete issues older than 90 days from the database.

    Args:
        app: Flask application instance for context.

    Logs:
        Information about the number of issues deleted or if none are found.
    """
    with app.app_context():
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        issues_to_delete = db.session.scalars(
            select(Issue).where(Issue.timestamp < cutoff_date)
        ).all()

        if issues_to_delete:
            count = len(issues_to_delete)
            for issue in issues_to_delete:
                db.session.delete(issue)
            db.session.commit()
            app.logger.info(f"Deleted {count} issues older than 90 days.")
        else:
            app.logger.info("No issues older than 90 days found.")