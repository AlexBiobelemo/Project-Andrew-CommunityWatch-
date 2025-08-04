import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    """Set Flask configuration variables."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-super-secret-key-you-should-change'

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'app.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')

    POSTS_PER_PAGE = 10
