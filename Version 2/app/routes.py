"""
Defines routes and view functions for the CommunityWatch application.
"""

import os
import json
from datetime import datetime, timedelta
import numpy as np
from sqlalchemy import select, or_, func
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app, jsonify, \
    send_from_directory
from flask_login import current_user, login_user, logout_user, login_required
from flask_limiter.util import get_remote_address
from app import db, ai_services, limiter, cache
from app.forms import RegistrationForm, LoginForm, IssueForm, CommentForm
from app.models import User, Issue, Upvote, Comment, Notification
from app.utils import get_coords_for_location, get_location_for_coords

bp = Blueprint('main', __name__)


def user_or_ip_key():
    """Return user ID for authenticated users or IP address for rate limiting."""
    return str(current_user.id) if current_user.is_authenticated else get_remote_address()


@bp.errorhandler(429)
def ratelimit_handler(e):
    """
    Handle 429 Too Many Requests errors from rate limiting.

    Args:
        e: The rate limit error object.

    Returns:
        JSON response with a user-friendly error message.
    """
    current_app.logger.warning(f"Rate limit exceeded: {e.description}")
    return jsonify({'error': 'Too many requests, please try again later'}), 429

# --- MOVED analytics FUNCTION HERE ---
@bp.route('/analytics')
@cache.cached(timeout=3600, key_prefix='analytics')  # Cache for 1 hour
def analytics():
    """Render the public community analytics dashboard."""
    status_counts = dict(db.session.query(Issue.status, func.count(Issue.status)).group_by(Issue.status).all())
    top_issues = db.session.scalars(
        select(Issue).where(Issue.status != 'Resolved').options(joinedload(Issue.reporter)).order_by(
            Issue.upvote_count.desc()).limit(5)
    ).all()
    unresolved_issues = db.session.scalars(
        select(Issue).where(Issue.status != 'Resolved').options(joinedload(Issue.reporter))
    ).all()
    heatmap_data = [[issue.latitude, issue.longitude] for issue in unresolved_issues]

    return render_template(
        'analytics.html',
        title='Community Analytics',
        status_counts=status_counts,
        top_issues=top_issues,
        heatmap_data=heatmap_data
    )
# --- END MOVED SECTION ---

@bp.route('/')
def index():
    """Render the homepage with an interactive map of issues."""
    issue_form = IssueForm()
    issues = db.session.scalars(
        select(Issue).options(joinedload(Issue.reporter))
    ).all()
    upvoted_issue_ids = {uv.issue_id for uv in current_user.upvotes.all()} if current_user.is_authenticated else set()

    issues_data = [
        {
            'id': issue.id,
            'lat': issue.latitude,
            'lng': issue.longitude,
            'title': issue.category,
            'upvotes': issue.upvote_count or 0,
            'user_has_voted': issue.id in upvoted_issue_ids,
            'status': issue.status
        }
        for issue in issues
    ]

    return render_template(
        'index.html',
        title='CommunityWatch',
        issue_form=issue_form,
        issues_data=issues_data
    )


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with form validation."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('main.login'))

        login_user(user, remember=form.remember_me.data)
        return redirect(url_for('main.index'))

    return render_template('login.html', title='Sign In', form=form)


@bp.route('/logout')
def logout():
    """Log out the current user."""
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration with form validation."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please sign in.', 'success')
        return redirect(url_for('main.login'))

    return render_template('register.html', title='Register', form=form)


@bp.route('/uploads/<filename>')
def uploaded_file(filename: str):
    """Serve an uploaded file from the upload folder."""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@bp.route('/report-issue', methods=['POST'])
@login_required
@limiter.limit("10 per minute", key_func=user_or_ip_key)
def report_issue():
    """Submit a new issue report with optional photo upload."""
    form = IssueForm()
    if not form.validate_on_submit():
        return jsonify({'success': False, 'errors': form.errors}), 400

    lat = request.form.get('lat', type=float)
    lng = request.form.get('lng', type=float)
    if lat is None or lng is None:
        return jsonify({'success': False, 'error': 'Missing coordinates'}), 400

    filename = None
    if form.photo.data:
        file_data = form.photo.data
        filename = secure_filename(file_data.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file_data.save(file_path)

    issue = Issue(
        category=form.category.data,
        description=form.description.data,
        latitude=lat,
        longitude=lng,
        reporter=current_user,
        location_text=form.location_text.data,
        image_filename=filename,
        geojson=json.loads(form.geojson.data) if form.geojson.data else None
    )
    issue.reporter.reputation_points = (issue.reporter.reputation_points or 0) + 5
    db.session.add(issue)
    db.session.commit()

    # Invalidate analytics cache when a new issue is reported
    cache.delete_memoized(analytics)

    return jsonify({
        'success': True,
        'issue': {
            'id': issue.id,
            'title': issue.category,
            'lat': issue.latitude,
            'lng': issue.longitude
        }
    })


@bp.route('/upvote/<int:issue_id>', methods=['POST'])
@login_required
@limiter.limit("20 per minute", key_func=user_or_ip_key)
def upvote(issue_id: int):
    """Toggle upvote for an issue and update reputation points."""
    issue = db.session.get(Issue, issue_id)
    if not issue:
        return jsonify({'success': False, 'error': 'Issue not found'}), 404

    issue.upvote_count = issue.upvote_count or 0
    issue.reporter.reputation_points = issue.reporter.reputation_points or 0

    existing_upvote = current_user.upvotes.filter_by(issue_id=issue_id).first()
    if existing_upvote:
        db.session.delete(existing_upvote)
        issue.upvote_count -= 1
        issue.reporter.reputation_points -= 2
        voted = False
    else:
        new_upvote = Upvote(voter=current_user, issue_id=issue_id)
        db.session.add(new_upvote)
        issue.upvote_count += 1
        issue.reporter.reputation_points += 2
        voted = True

    db.session.commit()

    # Invalidate analytics cache when upvote count changes
    cache.delete_memoized(analytics)

    return jsonify({'success': True, 'upvote_count': issue.upvote_count, 'voted': voted})


@bp.route('/issue/<int:issue_id>', methods=['GET', 'POST'])
@login_required
def view_issue(issue_id: int):
    """Display an issue and handle comment submission."""
    issue = db.session.get(Issue, issue_id, options=[
        joinedload(Issue.comments).joinedload(Comment.author),
        joinedload(Issue.reporter)
    ])
    if not issue:
        flash('Issue not found.', 'danger')
        return redirect(url_for('main.index'))

    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(
            body=form.body.data,
            issue=issue,
            author=current_user
        )
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been published.', 'success')
        return redirect(url_for('main.view_issue', issue_id=issue.id))

    comments = sorted(issue.comments, key=lambda c: c.timestamp)
    return render_template('view_issue.html', title=issue.category, issue=issue, form=form, comments=comments)


@bp.route('/issue/<int:issue_id>/update_status', methods=['POST'])
@login_required
def update_status(issue_id: int):
    """Update issue status and notify relevant users (moderator only)."""
    if not current_user.is_moderator:
        flash('Permission denied.', 'danger')
        return redirect(url_for('main.index'))

    issue = db.session.get(Issue, issue_id, options=[joinedload(Issue.reporter)])
    if not issue:
        flash('Issue not found.', 'danger')
        return redirect(url_for('main.view_issue', issue_id=issue_id))

    new_status = request.form.get('status')
    valid_statuses = {'Reported', 'In Progress', 'Resolved'}
    if new_status not in valid_statuses:
        flash('Invalid status.', 'danger')
        return redirect(url_for('main.view_issue', issue_id=issue_id))

    issue.status = new_status
    if new_status == 'Resolved':
        issue.reporter.reputation_points = (issue.reporter.reputation_points or 0) + 20

    recipients = {issue.reporter}
    upvoters = db.session.scalars(
        select(User).join(Upvote).where(Upvote.issue_id == issue.id).options(joinedload(User.upvotes))
    ).all()
    recipients.update(upvoters)

    for user in recipients:
        user.add_notification(
            'status_update',
            {'issue_id': issue.id, 'issue_category': issue.category, 'status': new_status}
        )

    db.session.commit()

    # Invalidate analytics cache when status changes
    cache.delete_memoized(analytics)

    return redirect(url_for('main.view_issue', issue_id=issue_id))


@bp.route('/search')
def search():
    """Handle geo-semantic search for issues."""
    query = request.args.get('q', '', type=str).strip()
    location_query = request.args.get('loc', '', type=str).strip()

    if not query and not location_query:
        return redirect(url_for('main.index'))

    base_query = select(Issue).options(joinedload(Issue.reporter))
    if location_query:
        coords = get_coords_for_location(location_query)
        if coords:
            lat, lng = coords
            radius = 0.05
            base_query = base_query.where(
                Issue.latitude.between(lat - radius, lat + radius),
                Issue.longitude.between(lng - radius, lng + radius)
            )
        else:
            flash(f"Could not find location: {location_query}", 'warning')
            return render_template('search_results.html', title='Search Results', results=[], query=query,
                                   location=location_query)

    issues = db.session.scalars(base_query).all()
    if query and issues:
        query_embedding = ai_services.generate_embedding(query, task_type='RETRIEVAL_QUERY')
        if query_embedding:
            query_vector = np.array(query_embedding)

            def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
                """Calculate cosine similarity between two vectors."""
                return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

            similarities = {
                issue.id: cosine_similarity(query_vector, np.array(issue.embedding))
                for issue in issues if issue.embedding
            }

            threshold = 0.6
            relevant_ids = {sid: score for sid, score in similarities.items() if score > threshold}
            sorted_ids = sorted(relevant_ids, key=relevant_ids.get, reverse=True)
            issue_map = {issue.id: issue for issue in issues}
            issues = [issue_map[sid] for sid in sorted_ids if sid in issue_map]
        else:
            issues = []

    return render_template('search_results.html', title='Search Results', results=issues, query=query,
                           location=location_query)


@bp.route('/notification-history')
@login_required
def notification_history():
    """Render the user's notification history with pagination."""
    page = request.args.get('page', 1, type=int)
    notifications = current_user.notifications.order_by(Notification.timestamp.desc()).paginate(
        page=page, per_page=15, error_out=False
    )
    return render_template('notification_history.html', title='Notification History', notifications=notifications)


@bp.route('/notifications')
@login_required
@limiter.limit("30 per minute", key_func=user_or_ip_key)
def notifications():
    """Fetch user notifications since a given timestamp."""
    since = request.args.get('since', 0.0, type=float)
    notifications = current_user.notifications.filter(Notification.timestamp > since).order_by(
        Notification.timestamp.asc()).all()

    return jsonify([
        {
            'name': n.name,
            'data': n.get_data(),
            'timestamp': n.timestamp
        }
        for n in notifications
    ])


@bp.route('/user/<username>')
@login_required
def user_profile(username: str):
    """Display a user's profile and their reported issues."""
    user = db.session.scalar(
        select(User).where(User.username == username).options(joinedload(User.issues))
    )
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('main.index'))

    issues = sorted(user.issues, key=lambda i: i.timestamp, reverse=True)  # Sort issues in Python
    return render_template('user_profile.html', title=f"{user.username}'s Profile", user=user, issues=issues)


@bp.route('/reverse-geocode', methods=['POST'])
@login_required
@limiter.limit("30 per minute", key_func=user_or_ip_key)
def reverse_geocode():
    """Get an address from coordinates via reverse geocoding."""
    data = request.get_json() or {}
    lat = data.get('lat')
    lng = data.get('lng')
    if lat is None or lng is None:
        return jsonify({'error': 'Missing coordinates'}), 400

    address = get_location_for_coords(lat, lng)
    return jsonify({'address': address or 'Unknown address'})


@bp.route('/check-duplicates', methods=['POST'])
@login_required
@limiter.limit("10 per minute", key_func=user_or_ip_key)
def check_duplicates():
    """Check if a new issue is a duplicate of nearby issues."""
    data = request.get_json() or {}
    try:
        lat = float(data.get('lat'))
        lng = float(data.get('lng'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid coordinates'}), 400

    description = data.get('description', '')
    radius = 0.001
    nearby_issues = db.session.scalars(
        select(Issue).where(
            Issue.latitude.between(lat - radius, lat + radius),
            Issue.longitude.between(lng - radius, lng + radius)
        ).options(joinedload(Issue.reporter))
    ).all()

    if not nearby_issues:
        return jsonify({'is_duplicate': False})

    existing_issues_data = [
        {'id': issue.id, 'title': issue.category, 'description': issue.description}
        for issue in nearby_issues
    ]
    result = ai_services.find_duplicate_issue(description, existing_issues_data)

    if result.get('is_duplicate'):
        duplicate_issue = db.session.get(Issue, result.get('duplicate_id'), options=[joinedload(Issue.reporter)])
        if duplicate_issue:
            result['duplicate_title'] = duplicate_issue.category

    return jsonify(result)


@bp.route('/generate-report', methods=['POST'])
@limiter.limit("5 per day", key_func=user_or_ip_key)
def generate_report():
    """Generate a weekly AI summary report of recent issues."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)

    recent_issues = db.session.scalars(
        select(Issue).where(Issue.timestamp.between(start_date, end_date)).options(joinedload(Issue.reporter))
    ).all()

    if not recent_issues:
        return jsonify({'report': 'No new issues reported in the last 7 days'})

    issues_by_cat = {}
    for issue in recent_issues:
        issues_by_cat[issue.category] = issues_by_cat.get(issue.category, 0) + 1

    top_issue = max(recent_issues, key=lambda issue: issue.upvote_count or 0)
    date_format = '%B %d, %Y'
    data_summary = (
        f"Date Range: {start_date.strftime(date_format)} to {end_date.strftime(date_format)}\n"
        f"- Total new issues: {len(recent_issues)}\n"
        f"- Breakdown by category: {issues_by_cat}\n"
        f"- Most upvoted new issue: '{top_issue.category}' with {top_issue.upvote_count or 0} upvotes"
    )

    report = ai_services.generate_weekly_report(data_summary)
    return jsonify({'report': report})

