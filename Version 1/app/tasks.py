from datetime import datetime, timedelta
from app import db
from app.models import Issue


def delete_old_issues(app):
    """
    Finds and deletes issues that are older than a set period.
    """
    with app.app_context():
        # Calculate the cutoff date
        ninety_days_ago = datetime.utcnow() - timedelta(days=90)

        # Find and delete old issues
        issues_to_delete = db.session.scalars(
            db.select(Issue).where(Issue.timestamp < ninety_days_ago)
        ).all()

        if issues_to_delete:
            print(f"Deleting {len(issues_to_delete)} old issues...")
            for issue in issues_to_delete:
                db.session.delete(issue)
            db.session.commit()
            print("Cleanup complete.")
        else:
            print("No old issues to delete.")