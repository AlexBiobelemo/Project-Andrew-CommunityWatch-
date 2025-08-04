"""Defines the forms used in the CommunityWatch application."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, PasswordField, BooleanField, SubmitField,
                   TextAreaField, SelectField, HiddenField)
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length
import sqlalchemy as sa

from app import db
from app.models import User, VALID_CATEGORIES


class RegistrationForm(FlaskForm):
    """Form for user registration."""
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(
            User.username == username.data))
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = db.session.scalar(sa.select(User).where(
            User.email == email.data))
        if user is not None:
            raise ValidationError('Please use a different email address.')


class LoginForm(FlaskForm):
    """Form for user login."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class IssueForm(FlaskForm):
    """Form for reporting a new issue."""
    category = SelectField('Category', choices=[
        (cat, cat) for cat in VALID_CATEGORIES
    ], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    photo = FileField('Upload Photo (Optional)', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')
    ])
    location_text = StringField('Address')
    geojson = HiddenField('GeoJSON')
    submit = SubmitField('Report Issue')


class CommentForm(FlaskForm):
    """Form for submitting comments."""
    body = TextAreaField('Comment', validators=[DataRequired()])
    submit = SubmitField('Submit')
