"""
Handles interactions with the Google Gemini API for image analysis, duplicate detection,
report generation, and text embedding.
"""
from __future__ import annotations

import json
from PIL import Image
import google.generativeai as genai
from flask import current_app

def _configure_genai():
    """Configure the Gemini API with the API key from the Flask app config."""
    genai.configure(api_key=current_app.config['GEMINI_API_KEY'])

def analyze_issue_image(image_path: str) -> dict:
    """
    Analyze an image of a community issue using Gemini Vision.

    Args:
        image_path: File path to the image to analyze.

    Returns:
        A dictionary with 'category' (from predefined list) and 'severity' (Low, Medium, High),
        or an error message if analysis fails.
    """
    try:
        _configure_genai()
        img = Image.open(image_path)
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")

        prompt = (
            "You are an expert at identifying municipal issues from images. "
            "Analyze this image and return a single, minified JSON object with two keys: "
            "'category' (choose one from: 'Pothole', 'Waste Dumping', 'Broken Streetlight', "
            "'Fallen Tree', 'Graffiti', 'Damaged Public Property', 'Other'), and "
            "'severity' (choose one from: 'Low', 'Medium', 'High'). "
            "Do not provide any other text or explanation."
        )

        response = model.generate_content([prompt, img])
        return json.loads(response.text.strip().replace('```json', '').replace('```', ''))

    except Exception as e:
        current_app.logger.error(f"Gemini Vision API error: {str(e)}")
        return {'error': 'Could not analyze image'}

def find_duplicate_issue(new_description: str, existing_issues: list) -> dict:
    """
    Use AI to determine if a new issue is a duplicate of existing nearby issues.

    Args:
        new_description: Description of the new issue report.
        existing_issues: List of dictionaries containing nearby issue details.

    Returns:
        A dictionary with 'is_duplicate' (bool) and optional 'duplicate_id' if a duplicate is found.
    """
    if not existing_issues:
        return {'is_duplicate': False}

    try:
        _configure_genai()
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        existing_reports_str = json.dumps(existing_issues, ensure_ascii=False)

        prompt = (
            "You are an issue analysis expert. Based on the text descriptions, determine if the "
            "'new_report' is a duplicate of any 'existing_reports'. Be strict; only identify a "
            "duplicate if it clearly describes the same problem. Return a single, minified JSON "
            "object: {'is_duplicate': true, 'duplicate_id': ID} for duplicates, or "
            "{'is_duplicate': false} if none match.\n\n"
            f"NEW REPORT: {new_description}\n\n"
            f"EXISTING REPORTS: {existing_reports_str}"
        )

        response = model.generate_content(prompt)
        return json.loads(response.text.strip().replace('```json', '').replace('```', ''))

    except Exception as e:
        current_app.logger.error(f"Gemini API error (duplicate check): {str(e)}")
        return {'is_duplicate': False}

def generate_weekly_report(data_summary: str) -> str:
    """
    Generate a natural language report from structured data using AI.

    Args:
        data_summary: String containing the data to summarize.

    Returns:
        A Markdown-formatted report or an error message if generation fails.
    """
    try:
        _configure_genai()
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")

        prompt = (
            "You are an analyst for a city council. Based ONLY on the provided data summary, "
            "write a concise, professional briefing in Markdown format. The title MUST be "
            "'Civic Issue Report' followed by the exact 'Date Range' from the data. Highlight "
            "key trends and the most critical issue. Do not add unprovided information.\n\n"
            f"DATA:\n{data_summary}"
        )

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        current_app.logger.error(f"Gemini API error (report generation): {str(e)}")
        return "Error: Could not generate the weekly report"

def generate_embedding(text_to_embed: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list | None:
    """
    Generate a vector embedding for a block of text.

    Args:
        text_to_embed: Text to create an embedding for.
        task_type: Task type ('RETRIEVAL_DOCUMENT' for storing, 'RETRIEVAL_QUERY' for searching).

    Returns:
        A list of floats representing the vector embedding, or None if an error occurs.
    """
    try:
        _configure_genai()
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text_to_embed,
            task_type=task_type
        )
        return result['embedding']

    except Exception as e:
        current_app.logger.error(f"Gemini API error (embedding): {str(e)}")
        return None