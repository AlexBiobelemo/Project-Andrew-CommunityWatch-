# CommunityWatch: AI-Enhanced Civic Reporting Platform

CommunityWatch is a full-stack, map-based web application that empowers residents to report, track, and validate local civic issues. It uses generative AI to provide intelligent features like duplicate detection and geo-semantic search, turning community feedback into actionable, data-driven insights.

---

## ✨ Key Features

### Core Platform
* **Interactive Map Interface:** Built with **Leaflet.js**, allowing users to pinpoint issue locations, view existing reports with status-based colored markers, and navigate to specific addresses.
* **Secure User Authentication:** Full user registration, login, and session management, including a moderator role for issue management.
* **Issue Reporting & Management:** Users can report issues with a category, description, and an optional photo upload. Moderators can update the status of any issue ('Reported', 'In Progress', 'Resolved').

### Community & Engagement
* **Upvoting & Commenting:** Users can upvote issues to highlight their importance and engage in discussions on a detailed page for each issue.
* **In-App Notifications:** A real-time notification system alerts users in the navbar when the status of an issue they follow has been updated.
* **User Reputation System:** A gamification system awards points to users for positive contributions, such as reporting an issue that gets resolved.

### AI & Analytics
* **Geo-Semantic Search:** An advanced search engine that understands both keywords and location. It uses **vector embeddings** and **cosine similarity** to find issues by conceptual meaning, and **geocoding** to filter them within a specific geographic area.
* **AI Duplicate Detection:** Before a new issue is submitted, the AI checks for similar reports nearby to prevent duplicate entries and consolidate feedback.
* **AI-Generated Weekly Reports:** A public analytics dashboard features an AI-powered summary of the week's trends, top issues, and emerging hotspots.
* **Issue Hotspot Visualization:** The analytics dashboard includes a heatmap that visually displays the concentration of unresolved issues.

---

## 🛠️ Tech Stack

* **Backend:** Python, Flask, SQLAlchemy
* **Database:** SQLite, Flask-Migrate (Alembic)
* **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5, Jinja2
* **Mapping:** Leaflet.js, OpenStreetMap, Leaflet.heat, leaflet-geosearch
* **AI Integration:** Google Gemini API
* **Testing & Numerics:** PyTest, NumPy
* **Background Jobs:** APScheduler
* **Authentication & Forms:** Flask-Login, Flask-WTF

---

## 🚀 Setup and Installation

To run this project locally, follow these steps:

**1. Clone the Repository**
```bash
git clone https://github.com/AlexBiobelemo/Project-Andrew-CommunityWatch-/tree/main/Version%201

2. Create and Activate Virtual Environment
# Windows
python -m venv venv
.\venv\Scripts\activate

3. Install Dependencies
pip install -r requirements.txt

4. Set Up Environment Variables
 * Create a file named .env in the root directory.
 * Add your secret keys to this file.
<!-- end list -->
# .env file
SECRET_KEY='your-super-secret-key'
GEMINI_API_KEY='your-google-gemini-api-key'

5. Initialize the Database
flask db init
flask db migrate -m "Initial database schema"
flask db upgrade

6. Run the Application
flask run

The application will be available at http://127.0.0.1:5000.
🔧 Management & Maintenance
The following are useful scripts to run inside the Flask shell (flask shell) for administrative tasks.

Make a User a Moderator

This script finds a user by their username and sets their is_moderator flag to True.
# First, manually import what you need
from app.models import User
from app import db

# Find the user
user = User.query.filter_by(username='THE_USERNAME_HERE').first()

# If the user is found, update and save the change
if user:
    user.is_moderator = True
    db.session.commit()
    print(f"Success! User '{user.username}' is now a moderator.")
else:
    print("User not found.")

Generate Search Embeddings for All Existing Issues
If you add issues to the database manually or need to regenerate search data, this script will create embeddings for all issues that are missing them.

# First, manually import what you need
import sqlalchemy as sa
from app.models import Issue
from app import db

# Find all issues without an embedding
issues_to_update = db.session.scalars(sa.select(Issue).where(Issue.embedding == None)).all()

# Loop through them and generate the embedding
for issue in issues_to_update:
    print(f"Generating embedding for: '{issue.category}'")
    issue.generate_and_set_embedding()

# Commit all the changes to the database
db.session.commit()

print(f"Updated {len(issues_to_update)} issues with search data!")


