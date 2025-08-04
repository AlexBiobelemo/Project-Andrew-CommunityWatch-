"""Handles all interactions with the external Google Gemini API."""

import json
import PIL.Image
import google.generativeai as genai
from flask import current_app


def analyze_issue_image(image_path):
    """
    Analyzes an image of a community issue using Gemini Vision.

    Args:
        image_path (str): The file path to the image to analyze.

    Returns:
        dict: A dictionary with 'category' and 'severity', or an error message.
    """
    try:
        genai.configure(api_key=current_app.config['GEMINI_API_KEY'])

        img = PIL.Image.open(image_path)
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

        json_response = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_response)

    except Exception as e:
        current_app.logger.error(f"Gemini Vision API error: {e}")
        return {'error': 'Could not analyze image.'}


def find_duplicate_issue(new_description, existing_issues):
    """
    Uses AI to determine if a new issue is a duplicate of existing nearby issues.

    Args:
        new_description (str): The description of the new issue report.
        existing_issues (list): A list of dictionaries of nearby issues.

    Returns:
        dict: A dictionary indicating if a duplicate was found and its ID.
    """
    if not existing_issues:
        return {'is_duplicate': False}

    try:
        genai.configure(api_key=current_app.config['GEMINI_API_KEY'])
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")

        existing_reports_str = json.dumps(existing_issues)

        prompt = (
            "You are an issue analysis expert. Based on the text descriptions, is the "
            "'new_report' a duplicate of any of the 'existing_reports'? Be strict in your matching; "
            "only identify a duplicate if it clearly describes the exact same problem. If you find a "
            "duplicate, return a single, minified JSON object: {\"is_duplicate\": true, \"duplicate_id\": ID_OF_THE_DUPLICATE}. "
            "If none match, return {\"is_duplicate\": false}.\n\n"
            f"NEW REPORT: \"{new_description}\"\n\n"
            f"EXISTING REPORTS: {existing_reports_str}"
        )

        response = model.generate_content(prompt)
        json_response = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_response)

    except Exception as e:
        current_app.logger.error(f"Gemini API error (duplicate check): {e}")
        return {'is_duplicate': False}


def generate_weekly_report(data_summary):
    """
    Uses AI to generate a natural language report from structured data.

    Args:
        data_summary (str): A string containing the data to be summarized.

    Returns:
        str: An AI-generated report in Markdown format.
    """
    try:
        genai.configure(api_key=current_app.config['GEMINI_API_KEY'])
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")

        prompt = (
            "You are an analyst for a city council. Based ONLY on the following data summary, "
            "write a concise, professional briefing in Markdown format. "
            "The title of your report MUST be 'Civic Issue Report' followed by the exact 'Date Range' provided in the data. "
            "Do not make up any information. Highlight key trends and the most critical issue mentioned.\n\n"
            f"DATA:\n{data_summary}"
        )

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        current_app.logger.error(f"Gemini API error (report): {e}")
        return "Error: Could not generate the weekly report."


def generate_embedding(text_to_embed, task_type="RETRIEVAL_DOCUMENT"):
    """
    Generates a vector embedding for a block of text.

    Args:
        text_to_embed (str): The text to create an embedding for.
        task_type (str): The type of task ('RETRIEVAL_DOCUMENT' for storing,
                         'RETRIEVAL_QUERY' for searching).

    Returns:
        list: A list of floats representing the vector embedding, or None on error.
    """
    try:
        genai.configure(api_key=current_app.config['GEMINI_API_KEY'])

        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text_to_embed,
            task_type=task_type
        )
        return result['embedding']

    except Exception as e:
        current_app.logger.error(f"Gemini API error (embedding): {e}")
        return None
