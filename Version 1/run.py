from app import create_app, db
from app.models import User, Issue, Comment, Upvote, Notification
import sqlalchemy as sa

app = create_app()

@app.shell_context_processor
def make_shell_context():
    """Provides a shell context for the 'flask shell' command."""
    return {
        'sa': sa,
        'db': db,
        'User': User,
        'Issue': Issue,
        'Comment': Comment,
        'Upvote': Upvote,
        'Notification': Notification
    }
