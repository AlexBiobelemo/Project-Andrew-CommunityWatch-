"""Defines the routes and view functions for the CommunityWatch application."""

import os
import json
from datetime import datetime, timedelta
import numpy as np
import sqlalchemy as sa
from sqlalchemy import or_, func
from werkzeug.utils import secure_filename
from flask import (Blueprint, render_template, flash, redirect, url_for,
                   request, current_app, jsonify, send_from_directory)
from flask_login import current_user, login_user, logout_user, login_required

from app import db, ai_services
from app.forms import (RegistrationForm, LoginForm, IssueForm,
                       CommentForm)
from app.models import User, Issue, Upvote, Comment, Notification
from app.utils import get_coords_for_location, get_location_for_coords

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """Renders the homepage map."""
    issue_form = IssueForm()
    issues = db.session.scalars(sa.select(Issue)).all()
    upvoted_issue_ids = []
    if current_user.is_authenticated:
        upvoted_issue_ids = [uv.issue_id for uv in current_user.upvotes.all()]
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
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('main.login'))
        login_user(user, remember=form.remember_me.data)
        return redirect(url_for('main.index'))
    return render_template('login.html', title='Sign In', form=form)


@bp.route('/logout')
def logout():
    """Handles user logout."""
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', title='Register', form=form)


@bp.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serves an uploaded file."""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@bp.route('/report-issue', methods=['POST'])
@login_required
def report_issue():
    """Endpoint for submitting a new issue report."""
    form = IssueForm()
    if form.validate_on_submit():
        lat = request.form.get('lat', type=float)
        lng = request.form.get('lng', type=float)
        if lat is None or lng is None:
            return jsonify({'success': False, 'error': 'Missing coordinates.'}), 400

        filename = None
        if form.photo.data:
            file_data = form.photo.data
            filename = secure_filename(file_data.filename)
            file_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'], filename)
            file_data.save(file_path)

        issue = Issue(
            category=form.category.data,
            description=form.description.data,
            latitude=lat,
            longitude=lng,
            reporter=current_user,
            location_text=form.location_text.data,
            image_filename=filename,
            geojson=json.loads(request.form.get('geojson')) if request.form.get('geojson') else None
        )
        # issue.generate_and_set_embedding()
        issue.reporter.reputation_points = (issue.reporter.reputation_points or 0) + 5
        db.session.add(issue)
        db.session.commit()

        return jsonify({'success': True, 'issue': {'id': issue.id, 'title': issue.category, 'lat': issue.latitude,
                                                   'lng': issue.longitude}})
    return jsonify({'success': False, 'errors': form.errors}), 400


@bp.route('/upvote/<int:issue_id>', methods=['POST'])
@login_required
def upvote(issue_id):
    """Endpoint to handle upvoting an issue."""
    issue = db.session.get(Issue, issue_id)
    if issue is None:
        return jsonify({'success': False, 'error': 'Issue not found.'}), 404

    if issue.upvote_count is None:
        issue.upvote_count = 0
    if issue.reporter.reputation_points is None:
        issue.reporter.reputation_points = 0

    existing_upvote = db.session.scalar(
        current_user.upvotes.where(Upvote.issue_id == issue_id))

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
    return jsonify({'success': True, 'upvote_count': issue.upvote_count, 'voted': voted})


@bp.route('/issue/<int:issue_id>', methods=['GET', 'POST'])
@login_required
def view_issue(issue_id):
    """Page for viewing a single issue and its comments."""
    issue = db.session.get(Issue, issue_id)
    if issue is None:
        flash('Issue not found.', 'danger')
        return redirect(url_for('main.index'))

    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(
            body=form.body.data, issue=issue, author=current_user)
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been published.', 'success')
        return redirect(url_for('main.view_issue', issue_id=issue.id))

    comments = issue.comments.order_by(Comment.timestamp.asc()).all()
    return render_template('view_issue.html', title=issue.category, issue=issue, form=form, comments=comments)


@bp.route('/issue/<int:issue_id>/update_status', methods=['POST'])
@login_required
def update_status(issue_id):
    """Updates the status of an issue and sends in-app notifications."""
    if not current_user.is_moderator:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('main.index'))

    issue = db.session.get(Issue, issue_id)
    if issue:
        new_status = request.form.get('status')
        if new_status in ['Reported', 'In Progress', 'Resolved']:
            issue.status = new_status
            if new_status == 'Resolved' and issue.reporter.reputation_points is not None:
                issue.reporter.reputation_points += 20

            recipients = {issue.reporter}
            upvoters = db.session.scalars(sa.select(User).join(Upvote).where(Upvote.issue_id == issue.id)).all()
            for user in upvoters:
                recipients.add(user)

            for user in recipients:
                user.add_notification(
                    'status_update',
                    {'issue_id': issue.id, 'issue_category': issue.category, 'status': new_status}
                )

            db.session.commit()
            flash('Issue status has been updated and followers notified.', 'success')
        else:
            flash('Invalid status.', 'danger')

    return redirect(url_for('main.view_issue', issue_id=issue_id))


@bp.route('/analytics')
def analytics():
    """Renders the public community analytics dashboard."""
    status_counts = db.session.query(
        Issue.status, func.count(Issue.status)).group_by(Issue.status).all()
    top_issues = db.session.scalars(sa.select(Issue).where(
        Issue.status != 'Resolved').order_by(Issue.upvote_count.desc()).limit(5)).all()

    unresolved_issues = db.session.scalars(sa.select(Issue).where(Issue.status != 'Resolved')).all()
    heatmap_data = [[issue.latitude, issue.longitude] for issue in unresolved_issues]

    return render_template('analytics.html', title="Community Analytics",
                           status_counts=dict(status_counts),
                           top_issues=top_issues,
                           heatmap_data=heatmap_data)


@bp.route('/search')
def search():
    """Handles geo-semantic search for issues."""
    query = request.args.get('q', '', type=str)
    location_query = request.args.get('loc', '', type=str)

    if not query and not location_query:
        return redirect(url_for('main.index'))

    base_query = sa.select(Issue)

    if location_query:
        coords = get_coords_for_location(location_query)
        if coords:
            lat, lng = coords
            RADIUS = 0.05
            base_query = base_query.where(
                Issue.latitude.between(lat - RADIUS, lat + RADIUS),
                Issue.longitude.between(lng - RADIUS, lng + RADIUS)
            )
        else:
            flash(f"Could not find location: {location_query}", "warning")
            return render_template('search_results.html', title="Search Results",
                                   results=[], query=query, location=location_query)

    issues = db.session.scalars(base_query).all()

    if query and issues:
        query_embedding = ai_services.generate_embedding(
            query, task_type="RETRIEVAL_QUERY")
        if query_embedding:
            query_vector = np.array(query_embedding)

            def cosine_similarity(v1, v2):
                return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

            similarities = {}
            for issue in issues:
                if issue.embedding:
                    issue_vector = np.array(issue.embedding)
                    similarities[issue.id] = cosine_similarity(
                        query_vector, issue_vector)

            print("Similarity Scores:", similarities)

            THRESHOLD = 0.6
            relevant_ids = {
                sid: score for sid, score in similarities.items() if score > THRESHOLD}

            sorted_ids = sorted(
                relevant_ids, key=relevant_ids.get, reverse=True)

            issue_map = {issue.id: issue for issue in issues}
            issues = [issue_map[sid] for sid in sorted_ids]
        else:
            issues = []

    return render_template('search_results.html', title="Search Results",
                           results=issues, query=query, location=location_query)


@bp.route('/notification-history')
@login_required
def notification_history():
    """Renders the user's full notification history."""
    page = request.args.get('page', 1, type=int)
    notifications = current_user.notifications.order_by(
        Notification.timestamp.desc()
    ).paginate(
        page=page, per_page=15, error_out=False
    )
    return render_template('notification_history.html', notifications=notifications)


@bp.route('/notifications')
@login_required
def notifications():
    """API endpoint to fetch user notifications."""
    since = request.args.get('since', 0.0, type=float)
    notifications = current_user.notifications.where(
        Notification.timestamp > since).order_by(Notification.timestamp.asc()).all()

    return jsonify([{
        'name': n.name,
        'data': n.get_data(),
        'timestamp': n.timestamp
    } for n in notifications])


@bp.route('/user/<username>')
@login_required
def user_profile(username):
    """Displays a user's profile page."""
    user = db.session.scalar(sa.select(User).where(User.username == username))
    if user is None:
        flash('User not found.', 'danger')
        return redirect(url_for('main.index'))

    issues = user.issues.order_by(Issue.timestamp.desc()).all()
    return render_template('user_profile.html', user=user, issues=issues)


@bp.route('/reverse-geocode', methods=['POST'])
@login_required
def reverse_geocode():
    """API endpoint to get an address from coordinates."""
    data = request.get_json()
    lat = data.get('lat')
    lng = data.get('lng')
    address = get_location_for_coords(lat, lng)
    return jsonify({'address': address})

@bp.route('/check-duplicates', methods=['POST'])
@login_required
def check_duplicates():
    """API endpoint to check for duplicate issues."""
    data = request.get_json()
    try:
        lat = float(data.get('lat'))
        lng = float(data.get('lng'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid coordinates provided.'}), 400

    description = data.get('description')
    RADIUS = 0.001
    nearby_issues = db.session.scalars(sa.select(Issue).where(
        Issue.latitude.between(lat - RADIUS, lat + RADIUS),
        Issue.longitude.between(lng - RADIUS, lng + RADIUS)
    )).all()

    if not nearby_issues:
        return jsonify({'is_duplicate': False})

    existing_issues_data = [
        {'id': issue.id, 'title': issue.category, 'description': issue.description}
        for issue in nearby_issues
    ]
    result = ai_services.find_duplicate_issue(
        description, existing_issues_data)

    if result.get('is_duplicate'):
        duplicate_issue = db.session.get(Issue, result.get('duplicate_id'))
        if duplicate_issue:
            result['duplicate_title'] = duplicate_issue.category

    return jsonify(result)


@bp.route('/generate-report', methods=['POST'])
def generate_report():
    """API endpoint to generate a weekly AI summary report."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)

    recent_issues = db.session.scalars(sa.select(Issue).where(
        Issue.timestamp.between(start_date, end_date)
    )).all()

    if not recent_issues:
        return jsonify({'report': 'No new issues reported in the last 7 days.'})

    # --- This section creates a short, efficient summary ---
    total_new = len(recent_issues)
    issues_by_cat = {}
    for issue in recent_issues:
        issues_by_cat[issue.category] = issues_by_cat.get(issue.category, 0) + 1

    top_issue = max(recent_issues, key=lambda issue: issue.upvote_count or 0)

    date_format = "%B %d, %Y"

    data_summary = (
        f"Date Range: {start_date.strftime(date_format)} to {end_date.strftime(date_format)}\n"
        f"- Total new issues: {total_new}\n"
        f"- Breakdown by category: {issues_by_cat}\n"
        f"- Most upvoted new issue: '{top_issue.category}' with {top_issue.upvote_count} upvotes."
    )
    # --- End of summary section ---

    report = ai_services.generate_weekly_report(data_summary)

    return jsonify({'report': report})

