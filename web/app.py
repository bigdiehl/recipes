import json
import logging
import os
import os.path as osp
from pathlib import Path
import re
import random
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import BytesIO

import markdown
import yaml
from flask import Flask, abort, jsonify, render_template, request, send_from_directory, send_file, session, redirect
from weasyprint import HTML, CSS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from recipe_core.recipe_lib import RecipeData
from recipe_core.shopping_list import (
    find_recipe_dirs,
    generate_shopping_list_md,
    get_merged_shopping_list,
    get_shopping_list_data
)
from recipe_core.mailer import build_message, send_email
from recipe_core.gemini_importer import extract_recipe, ImportResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_this_dir = os.path.dirname(__file__)
with open(os.path.join(_this_dir, "config.yaml")) as f:
    config = yaml.safe_load(f)

RECIPES_DIR = os.path.join(_this_dir, config["app"]["recipes_dir"])
PENDING_DIR = os.path.join(_this_dir, config["app"]["pending_dir"])
STATE_FILE  = os.path.join(_this_dir, config["app"]["state_file"])
OUTPUT_DIR  = os.path.join(_this_dir, config["app"]["output_dir"])

# Email configuration
EMAIL_CONFIG = config.get("email", {})
SMTP_SERVER = EMAIL_CONFIG.get("smtp_server", "smtp.gmail.com")
SMTP_PORT = EMAIL_CONFIG.get("smtp_port", 587)

# ---------------------------------------------------------------------------
# Recipe dataclass
# ---------------------------------------------------------------------------

@dataclass
class Recipe:
    slug:             str
    name:             str
    md_filename:      str
    path:             str
    category:         str  = ""
    meal:             str  = ""
    selected:         bool = False
    weeks_since_last: int  = 1

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# ---------------------------------------------------------------------------
# State file (JSON) — persists stateful data like 'selected' and 'weeks_since_last'
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    """Load state from JSON file. Returns empty dict if file doesn't exist."""
    if osp.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def _save_state(state: dict):
    """Write state dict to JSON file."""
    os.makedirs(osp.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ---------------------------------------------------------------------------
# Recipe store — filesystem + state file
# ---------------------------------------------------------------------------

def _find_md_file(recipe_dir: str) -> str:
    """Return the first markdown file found in recipe_dir, or empty string."""
    for f in os.listdir(recipe_dir):
        if f.endswith(".md"):
            return f
    return ""

def get_all_recipes() -> list[Recipe]:
    """
    Build the current recipe list from the filesystem, enriched with
    stateful fields (selected, weeks_since_last) from the state file.
    Slugs present in the state file but no longer on disk are ignored.
    """
    state = _load_state()
    recipes = []

    for recipe_dir in find_recipe_dirs(RECIPES_DIR):
        path = Path(recipe_dir).relative_to(RECIPES_DIR)
        slug = osp.basename(recipe_dir)
        entry = state.get(slug, {})

        # Load recipe metadata from recipe.yaml
        category = ""
        meal = ""
        yaml_path = osp.join(recipe_dir, "recipe.yaml")
        if osp.exists(yaml_path):
            try:
                recipe_data = RecipeData.from_yaml(yaml_path)
                category = recipe_data.category.value
                meal = recipe_data.meal.value
            except Exception as e:
                logger.warning(f"Failed to load recipe data for {slug}: {e}")

        recipes.append(Recipe(
            slug             = slug,
            path             = str(path),
            name             = slug.replace("_", " ").title(),
            md_filename      = _find_md_file(recipe_dir),
            category         = category,
            meal             = meal,
            selected         = entry.get("selected", False),
            weeks_since_last = entry.get("weeks_since_last", 1),
        ))

    return recipes

def _update_state(slug: str, **kwargs):
    """Merge kwargs into the state entry for slug and save."""
    state = _load_state()
    entry = state.get(slug, {})
    entry.update(kwargs)
    state[slug] = entry
    _save_state(state)

# ---------------------------------------------------------------------------
# Schedule configuration
# ---------------------------------------------------------------------------

def _get_schedule_config() -> dict:
    """Get the schedule configuration from state file."""
    state = _load_state()
    return state.get("_schedule_config", {
        "enabled": False,
        "num_recipes": 3,
        "day_of_week": 0,  # Monday
        "send_time": "09:00",
        "recipients": ""
    })

def _save_schedule_config(config: dict):
    """Save schedule configuration to state file."""
    state = _load_state()
    state["_schedule_config"] = config
    _save_state(state)

def _is_recipe_available(slug: str, min_period_weeks: int) -> bool:
    """
    Check if a recipe is available for selection based on when it was last used.

    Args:
        slug: Recipe slug
        min_period_weeks: Minimum weeks to wait before selecting again

    Returns:
        True if recipe can be selected
    """
    state = _load_state()
    entry = state.get(slug, {})
    last_used = entry.get("last_used_date")

    if not last_used:
        return True

    last_used_date = datetime.fromisoformat(last_used).date()
    weeks_since = (date.today() - last_used_date).days / 7

    return weeks_since >= min_period_weeks

def select_recipes_for_schedule(num_recipes: int) -> list[str]:
    """
    Select recipes for scheduled email, using currently selected recipes first,
    then filling with random available recipes.

    Args:
        num_recipes: Total number of recipes to select

    Returns:
        List of recipe slugs
    """
    all_recipes = get_all_recipes()

    # Get currently selected recipes
    selected_slugs = [r.slug for r in all_recipes if r.selected]

    # If we already have enough, just use those
    if len(selected_slugs) >= num_recipes:
        return selected_slugs[:num_recipes]

    # Load recipe metadata to get min_period_weeks
    _, metas = _get_shopping_list_data()

    # Get available recipes (not currently selected and past min period)
    available = []
    for recipe in all_recipes:
        if recipe.slug not in selected_slugs:
            recipe_data = metas.get(recipe.slug)
            if recipe_data and recipe_data.enabled:
                min_period = recipe_data.min_period_weeks
                if _is_recipe_available(recipe.slug, min_period):
                    available.append(recipe.slug)

    # Randomly select from available recipes
    num_needed = num_recipes - len(selected_slugs)
    if available and num_needed > 0:
        random.shuffle(available)
        selected_slugs.extend(available[:num_needed])

    return selected_slugs

def update_recipe_usage(slugs: list[str]):
    """Mark recipes as used today."""
    today = date.today().isoformat()
    for slug in slugs:
        _update_state(slug, last_used_date=today)

def send_scheduled_shopping_list():
    """
    Scheduled task to send weekly shopping list email.
    Selects recipes, generates PDF, and sends via email.
    """
    try:
        config = _get_schedule_config()

        if not config.get("enabled"):
            logger.info("Scheduled email disabled, skipping")
            return

        recipients_str = config.get("recipients", "").strip()
        if not recipients_str:
            logger.warning("No recipients configured for scheduled email")
            return

        recipients = [e.strip() for e in recipients_str.replace(";", ",").split(",") if e.strip()]
        num_recipes = config.get("num_recipes", 3)

        # Select recipes
        selected_slugs = select_recipes_for_schedule(num_recipes)

        if not selected_slugs:
            logger.warning("No recipes available for scheduled email")
            return

        # Update recipe usage tracking
        update_recipe_usage(selected_slugs)

        # Generate PDF
        lists, metas = _get_shopping_list_data()
        main, secondary = get_merged_shopping_list(selected_slugs, lists)
        names = [metas[slug].name for slug in selected_slugs]
        md = generate_shopping_list_md(names, selected_slugs, main, secondary, show_sources=False)

        html_content = markdown.markdown(md, extensions=["tables", "fenced_code", "nl2br", "sane_lists"])

        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{ size: letter; margin: 0.75in; }}
                body {{ font-family: Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #000; }}
                h1 {{ font-size: 20pt; font-weight: bold; color: #000; margin-top: 0; margin-bottom: 0.5em; padding-bottom: 0.3em; border-bottom: 2px solid #333; }}
                h2 {{ font-size: 16pt; font-weight: bold; color: #000; margin-top: 1em; margin-bottom: 0.4em; padding-bottom: 0.2em; border-bottom: 1px solid #666; page-break-after: avoid; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 1em; page-break-inside: avoid; }}
                th, td {{ padding: 6px 10px; border: 1px solid #999; text-align: left; }}
                th {{ background-color: #f0f0f0; font-weight: bold; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        pdf_bytes = HTML(string=full_html).write_pdf()

        # Send email
        sender = os.environ.get("GMAIL_SENDER")
        password = os.environ.get("GMAIL_APP_PASSWORD")

        if not sender or not password:
            logger.error("Email credentials not configured")
            return

        today = date.today().isoformat()
        filename = f"shopping-list-{today}.pdf"
        temp_pdf_path = osp.join(OUTPUT_DIR, filename)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_bytes)

        subject = f"Weekly Shopping List - {today}"
        body = f"Your weekly shopping list for {len(selected_slugs)} recipes.\n\nRecipes:\n" + "\n".join(f"- {metas[slug].name}" for slug in selected_slugs)

        message = build_message(
            sender=sender,
            recipients=recipients,
            subject=subject,
            body=body,
            attachments=[temp_pdf_path]
        )

        send_email(
            sender=sender,
            password=password,
            recipients=recipients,
            message=message,
            server=SMTP_SERVER,
            port=SMTP_PORT
        )

        if osp.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

        logger.info("Scheduled shopping list sent to: %s", ", ".join(recipients))

    except Exception as e:
        logger.error("Failed to send scheduled shopping list: %s", e, exc_info=True)

# ---------------------------------------------------------------------------
# Shopping list helpers
# ---------------------------------------------------------------------------

_shopping_list_cache: dict = {}

def _get_shopping_list_data():
    """Return cached shopping list data, loading from disk if needed."""
    if not _shopping_list_cache:
        lists, metas = get_shopping_list_data(RECIPES_DIR)
        _shopping_list_cache["lists"] = lists
        _shopping_list_cache["metas"] = metas
    return _shopping_list_cache["lists"], _shopping_list_cache["metas"]

def _invalidate_shopping_list_cache():
    _shopping_list_cache.clear()

def get_shopping_list_html(show_sources: bool = False) -> str:
    selected_slugs = [r.slug for r in get_all_recipes() if r.selected]

    if not selected_slugs:
        return "<em>Select recipes to generate shopping list.</em>"

    lists, metas = _get_shopping_list_data()
    
    main, secondary = get_merged_shopping_list(selected_slugs, lists)
    
    names = [metas[slug].name for slug in selected_slugs]
    md = generate_shopping_list_md(names, selected_slugs, main, secondary, show_sources=show_sources)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(osp.join(OUTPUT_DIR, "shopping_list.md"), "w") as f:
        f.write(md)

    return markdown.markdown(md, extensions=[
        "tables",
        "fenced_code",
        "nl2br",
        "sane_lists"
    ])

# ---------------------------------------------------------------------------
# Routes — home
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    recipes = get_all_recipes()
    selected = sorted([r for r in recipes if r.selected], key=lambda r: r.name)
    return render_template(
        "index.html",
        active_page="home",
        recipes=selected,
        shopping_list_html=get_shopping_list_html(),
    )

@app.route("/deselect/<slug>", methods=["POST"])
def deselect(slug):
    _update_state(slug, selected=False)
    _invalidate_shopping_list_cache()
    return jsonify({"success": True, "selected": False})

@app.route("/markdown/shopping_list")
def update_shopping_list_html():
    show_sources = request.args.get("show_sources", "false").lower() == "true"
    return jsonify({"html": get_shopping_list_html(show_sources=show_sources)})

@app.route("/send_list", methods=["POST"])
def send_list():
    """Send shopping list PDF via email"""
    data = request.get_json()
    email_input = data.get("email", "").strip()

    if not email_input:
        return jsonify({"success": False, "error": "No email addresses provided"}), 400

    # Parse email addresses (split by semicolon or comma)
    recipients = [e.strip() for e in email_input.replace(";", ",").split(",") if e.strip()]

    if not recipients:
        return jsonify({"success": False, "error": "No valid email addresses"}), 400

    # Get sender email and password from environment
    sender = os.environ.get("GMAIL_SENDER")
    password = os.environ.get("GMAIL_APP_PASSWORD")

    if not sender:
        return jsonify({"success": False, "error": "GMAIL_SENDER environment variable not set"}), 500

    if not password:
        return jsonify({"success": False, "error": "GMAIL_APP_PASSWORD environment variable not set"}), 500

    # Generate PDF
    selected_slugs = [r.slug for r in get_all_recipes() if r.selected]

    if not selected_slugs:
        return jsonify({"success": False, "error": "No recipes selected"}), 400

    try:
        lists, metas = _get_shopping_list_data()
        main, secondary = get_merged_shopping_list(selected_slugs, lists)
        names = [metas[slug].name for slug in selected_slugs]
        md = generate_shopping_list_md(names, selected_slugs, main, secondary, show_sources=False)

        # Convert markdown to HTML
        html_content = markdown.markdown(md, extensions=[
            "tables",
            "fenced_code",
            "nl2br",
            "sane_lists"
        ])

        # Wrap in proper HTML document with styling
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: letter;
                    margin: 0.75in;
                }}
                body {{
                    font-family: Arial, sans-serif;
                    font-size: 11pt;
                    line-height: 1.5;
                    color: #000;
                }}
                h1 {{
                    font-size: 20pt;
                    font-weight: bold;
                    color: #000;
                    margin-top: 0;
                    margin-bottom: 0.5em;
                    padding-bottom: 0.3em;
                    border-bottom: 2px solid #333;
                }}
                h2 {{
                    font-size: 16pt;
                    font-weight: bold;
                    color: #000;
                    margin-top: 1em;
                    margin-bottom: 0.4em;
                    padding-bottom: 0.2em;
                    border-bottom: 1px solid #666;
                    page-break-after: avoid;
                }}
                h3 {{
                    font-size: 13pt;
                    font-weight: bold;
                    color: #000;
                    margin-top: 0.8em;
                    margin-bottom: 0.3em;
                    padding-left: 0.3em;
                    border-left: 3px solid #333;
                    page-break-after: avoid;
                }}
                ul, ol {{
                    margin-bottom: 0.5em;
                    padding-left: 1.5em;
                }}
                li {{
                    margin-bottom: 0.2em;
                    page-break-inside: avoid;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 1em;
                    page-break-inside: avoid;
                }}
                th, td {{
                    padding: 6px 10px;
                    border: 1px solid #999;
                    text-align: left;
                }}
                th {{
                    background-color: #f0f0f0;
                    font-weight: bold;
                }}
                tr {{
                    page-break-inside: avoid;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # Generate PDF in memory
        pdf_bytes = HTML(string=full_html).write_pdf()

        # Save PDF temporarily
        today = date.today().isoformat()
        filename = f"shopping-list-{today}.pdf"
        temp_pdf_path = osp.join(OUTPUT_DIR, filename)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_bytes)

        # Build and send email
        subject = f"Shopping List - {today}"
        body = f"Please find attached your shopping list for {len(selected_slugs)} selected recipes."

        message = build_message(
            sender=sender,
            recipients=recipients,
            subject=subject,
            body=body,
            attachments=[temp_pdf_path]
        )

        send_email(
            sender=sender,
            password=password,
            recipients=recipients,
            message=message,
            server=SMTP_SERVER,
            port=SMTP_PORT
        )

        # Clean up temp file
        if osp.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

        logger.info("Shopping list sent to: %s", ", ".join(recipients))
        return jsonify({"success": True, "message": f"Email sent to {len(recipients)} recipient(s)"})

    except Exception as e:
        logger.error("Failed to send email: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/download_shopping_list_pdf")
def download_shopping_list_pdf():
    """Generate and download shopping list as PDF"""
    selected_slugs = [r.slug for r in get_all_recipes() if r.selected]

    if not selected_slugs:
        return "No recipes selected", 400

    lists, metas = _get_shopping_list_data()
    main, secondary = get_merged_shopping_list(selected_slugs, lists)
    names = [metas[slug].name for slug in selected_slugs]
    md = generate_shopping_list_md(names, selected_slugs, main, secondary, show_sources=False)

    # Convert markdown to HTML
    html_content = markdown.markdown(md, extensions=[
        "tables",
        "fenced_code",
        "nl2br",
        "sane_lists"
    ])

    # Wrap in proper HTML document with styling
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: letter;
                margin: 0.75in;
            }}
            body {{
                font-family: Arial, sans-serif;
                font-size: 11pt;
                line-height: 1.5;
                color: #000;
            }}
            h1 {{
                font-size: 20pt;
                font-weight: bold;
                color: #000;
                margin-top: 0;
                margin-bottom: 0.5em;
                padding-bottom: 0.3em;
                border-bottom: 2px solid #333;
            }}
            h2 {{
                font-size: 16pt;
                font-weight: bold;
                color: #000;
                margin-top: 1em;
                margin-bottom: 0.4em;
                padding-bottom: 0.2em;
                border-bottom: 1px solid #666;
                page-break-after: avoid;
            }}
            h3 {{
                font-size: 13pt;
                font-weight: bold;
                color: #000;
                margin-top: 0.8em;
                margin-bottom: 0.3em;
                padding-left: 0.3em;
                border-left: 3px solid #333;
                page-break-after: avoid;
            }}
            p {{
                margin-bottom: 0.5em;
            }}
            ul, ol {{
                margin-bottom: 0.5em;
                padding-left: 1.5em;
            }}
            li {{
                margin-bottom: 0.2em;
                page-break-inside: avoid;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 1em;
                page-break-inside: avoid;
            }}
            th, td {{
                padding: 6px 10px;
                border: 1px solid #999;
                text-align: left;
            }}
            th {{
                background-color: #f0f0f0;
                font-weight: bold;
            }}
            tr {{
                page-break-inside: avoid;
            }}
            strong {{
                font-weight: bold;
            }}
            em {{
                font-style: italic;
            }}
            code {{
                background-color: #f0f0f0;
                padding: 2px 4px;
                border-radius: 2px;
                font-family: monospace;
                font-size: 0.9em;
            }}
            pre {{
                background-color: #f0f0f0;
                padding: 0.5em;
                border-radius: 3px;
                margin-bottom: 0.5em;
                overflow-x: auto;
            }}
            pre code {{
                background-color: transparent;
                padding: 0;
            }}
            blockquote {{
                border-left: 3px solid #999;
                padding-left: 0.75em;
                margin: 0.5em 0;
                color: #333;
                font-style: italic;
            }}
            hr {{
                border: none;
                border-top: 1px solid #999;
                margin: 1em 0;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    # Generate PDF
    pdf_io = BytesIO()
    HTML(string=full_html).write_pdf(pdf_io)
    pdf_io.seek(0)

    # Generate filename with today's date
    today = date.today().isoformat()
    filename = f"shopping-list-{today}.pdf"

    return send_file(
        pdf_io,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

# ---------------------------------------------------------------------------
# Routes — recipe list
# ---------------------------------------------------------------------------

@app.route("/recipes_list")
def recipes_list():
    recipes = sorted(get_all_recipes(), key=lambda r: r.name)
    return render_template("recipes_list.html", recipes=recipes, active_page="recipes_list")

@app.route("/recipes_list/toggle/<slug>", methods=["POST"])
def toggle(slug):
    recipes = get_all_recipes()
    recipe = next((r for r in recipes if r.slug == slug), None)
    if recipe is None:
        abort(404)
    new_selected = not recipe.selected
    _update_state(slug, selected=new_selected)
    _invalidate_shopping_list_cache()
    return jsonify({"success": True, "selected": new_selected})

@app.route("/recipes/<path:file>")
def serve_recipe_file(file):
    recipes = get_all_recipes()
    slug, file = file.split("/", 1)
    recipe = next((r for r in recipes if r.slug == slug), None)
    if recipe is None:
        abort(404)
    return send_from_directory(osp.join(RECIPES_DIR, recipe.path), file)

@app.route("/pending/<slug>/<path:file>")
def serve_pending_file(slug, file):
    """Serve files from pending recipe directory."""
    pending_recipe_dir = osp.join(PENDING_DIR, slug)
    if not osp.exists(pending_recipe_dir):
        abort(404)
    return send_from_directory(pending_recipe_dir, file)

@app.route("/markdown/recipe/<recipe_name>")
def get_markdown_recipe(recipe_name):
    recipes = get_all_recipes()
    recipe = next((r for r in recipes if r.name == recipe_name), None)
    if recipe is None:
        abort(404)

    md_file = osp.join(RECIPES_DIR, recipe.path, recipe.md_filename)
    if not md_file.endswith(".md") or not osp.exists(md_file):
        abort(404)

    with open(md_file, "r", encoding="utf-8") as f:
        md_content = f.read()

    html_content = markdown.markdown(md_content, extensions=[
        "tables",
        "fenced_code",
        "nl2br",
        "sane_lists"
    ])
    html_content = re.sub(
        r'src="([^":]+)"',
        lambda m: f'src="recipes/{recipe.slug}/{m.group(1)}"',
        html_content,
    )
    return jsonify({"filename": md_file, "content": html_content})

# ---------------------------------------------------------------------------
# Recipe management helpers
# ---------------------------------------------------------------------------

def save_pending(result: ImportResult, pending_dir: str = PENDING_DIR):
    """Save an extracted recipe to the pending directory."""
    recipe_dir = osp.join(pending_dir, result.slug)
    os.makedirs(recipe_dir, exist_ok=True)

    # Save YAML
    yaml_path = osp.join(recipe_dir, "recipe.yaml")
    with open(yaml_path, "w") as f:
        yaml.dump(result.recipe_data.model_dump(mode="python", exclude_none=True), f, default_flow_style=False)

    # Save Markdown
    md_path = osp.join(recipe_dir, "recipe.md")
    with open(md_path, "w") as f:
        f.write(result.markdown)

    # Save source info
    info_path = osp.join(recipe_dir, "source.txt")
    with open(info_path, "w") as f:
        f.write(result.source)

def promote_recipe(slug: str, pending_dir: str = PENDING_DIR, recipes_dir: str = RECIPES_DIR):
    """Move a recipe from pending to saved/dinner directory."""
    src = osp.join(pending_dir, slug)
    dst = osp.join(recipes_dir, "saved", "dinner", slug)

    if not osp.exists(src):
        raise FileNotFoundError(f"Pending recipe not found: {slug}")

    if osp.exists(dst):
        raise FileExistsError(f"Recipe already exists: {slug}")

    os.makedirs(osp.dirname(dst), exist_ok=True)

    # Move the directory
    shutil.move(src, dst)

def discard_pending(slug: str, pending_dir: str = PENDING_DIR):
    """Delete a pending recipe."""
    recipe_dir = osp.join(pending_dir, slug)
    if not osp.exists(recipe_dir):
        raise FileNotFoundError(f"Pending recipe not found: {slug}")

    shutil.rmtree(recipe_dir)

def demote_recipe(slug: str, recipes_dir: str = RECIPES_DIR, pending_dir: str = PENDING_DIR):
    """Move a recipe from saved to pending."""
    # Find the recipe in saved directories
    src = None
    for recipe in get_all_recipes():
        if recipe.slug == slug:
            src = osp.join(recipes_dir, recipe.path)
            break

    if not src or not osp.exists(src):
        raise FileNotFoundError(f"Saved recipe not found: {slug}")

    dst = osp.join(pending_dir, slug)

    if osp.exists(dst):
        raise FileExistsError(f"Recipe already exists in pending: {slug}")

    os.makedirs(osp.dirname(dst), exist_ok=True)

    # Move the directory
    shutil.move(src, dst)

def delete_saved_recipe(slug: str, recipes_dir: str = RECIPES_DIR):
    """Delete a saved recipe."""
    # Find the recipe in saved directories
    recipe_dir = None
    for recipe in get_all_recipes():
        if recipe.slug == slug:
            recipe_dir = osp.join(recipes_dir, recipe.path)
            break

    if not recipe_dir or not osp.exists(recipe_dir):
        raise FileNotFoundError(f"Saved recipe not found: {slug}")

    shutil.rmtree(recipe_dir)

# ---------------------------------------------------------------------------
# Routes — Recipe Editor
# ---------------------------------------------------------------------------

@app.route("/editor", methods=["GET"])
def editor_page():
    """Render the recipe editor page with tabs for editing and importing."""
    return render_template("editor.html", active_page="editor")

@app.route("/editor/recipes", methods=["GET"])
def list_all_recipes():
    """List all recipes (saved and pending) for the editor."""
    saved_recipes = []
    pending_recipes = []

    # Get saved recipes
    for recipe in get_all_recipes():
        saved_recipes.append({
            "slug": recipe.slug,
            "name": recipe.name,
            "path": recipe.path,
            "status": "saved"
        })

    # Get pending recipes
    if osp.exists(PENDING_DIR):
        for slug in os.listdir(PENDING_DIR):
            recipe_dir = osp.join(PENDING_DIR, slug)
            if osp.isdir(recipe_dir):
                pending_recipes.append({
                    "slug": slug,
                    "name": slug.replace("_", " ").title(),
                    "status": "pending"
                })

    return jsonify({
        "success": True,
        "saved": saved_recipes,
        "pending": pending_recipes
    })

@app.route("/editor/recipe/<status>/<slug>", methods=["GET"])
def load_recipe(status, slug):
    """Load a recipe's YAML and markdown for editing."""
    if status == "saved":
        recipes = get_all_recipes()
        recipe = next((r for r in recipes if r.slug == slug), None)
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404

        recipe_dir = osp.join(RECIPES_DIR, recipe.path)
    elif status == "pending":
        recipe_dir = osp.join(PENDING_DIR, slug)
        if not osp.exists(recipe_dir):
            return jsonify({"error": "Recipe not found"}), 404
    else:
        return jsonify({"error": "Invalid status"}), 400

    # Load YAML
    yaml_path = osp.join(recipe_dir, "recipe.yaml")
    yaml_content = ""
    if osp.exists(yaml_path):
        with open(yaml_path, "r") as f:
            yaml_content = f.read()

    # Load Markdown (try recipe.md first, then any .md file)
    md_content = ""
    md_filename = "recipe.md"
    md_path = osp.join(recipe_dir, md_filename)

    if not osp.exists(md_path):
        # Find any markdown file
        for f in os.listdir(recipe_dir):
            if f.endswith(".md"):
                md_filename = f
                md_path = osp.join(recipe_dir, f)
                break

    if osp.exists(md_path):
        with open(md_path, "r") as f:
            md_content = f.read()

    return jsonify({
        "success": True,
        "yaml": yaml_content,
        "markdown": md_content,
        "md_filename": md_filename
    })

@app.route("/editor/recipe/<status>/<slug>", methods=["POST"])
def save_recipe(status, slug):
    """Save edited recipe YAML and markdown."""
    data = request.get_json()
    yaml_content = data.get("yaml", "")
    markdown_content = data.get("markdown", "")

    if status == "saved":
        recipes = get_all_recipes()
        recipe = next((r for r in recipes if r.slug == slug), None)
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404

        recipe_dir = osp.join(RECIPES_DIR, recipe.path)
    elif status == "pending":
        recipe_dir = osp.join(PENDING_DIR, slug)
        if not osp.exists(recipe_dir):
            return jsonify({"error": "Recipe not found"}), 404
    else:
        return jsonify({"error": "Invalid status"}), 400

    try:
        # Validate YAML
        yaml.safe_load(yaml_content)

        # Save YAML
        yaml_path = osp.join(recipe_dir, "recipe.yaml")
        with open(yaml_path, "w") as f:
            f.write(yaml_content)

        # Save Markdown
        md_path = osp.join(recipe_dir, "recipe.md")
        with open(md_path, "w") as f:
            f.write(markdown_content)

        # Invalidate cache if saved recipe
        if status == "saved":
            _invalidate_shopping_list_cache()

        return jsonify({"success": True, "message": "Recipe saved successfully"})

    except yaml.YAMLError as e:
        return jsonify({"error": f"Invalid YAML: {str(e)}"}), 400
    except Exception as e:
        logger.error("Failed to save recipe: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/editor/preview", methods=["POST"])
def preview_markdown():
    """Render markdown to HTML for preview."""
    data = request.get_json()
    markdown_content = data.get("markdown", "")
    recipe_slug = data.get("slug", "")

    html_content = markdown.markdown(markdown_content, extensions=[
        "tables",
        "fenced_code",
        "nl2br",
        "sane_lists"
    ])

    # Fix image paths if recipe slug is provided
    if recipe_slug:
        # Find the recipe to get its path
        recipes = get_all_recipes()
        recipe = next((r for r in recipes if r.slug == recipe_slug), None)

        if recipe:
            # Fix relative image paths
            html_content = re.sub(
                r'src="([^":]+)"',
                lambda m: f'src="/recipes/{recipe.slug}/{m.group(1)}"',
                html_content,
            )
        else:
            # Check if it's a pending recipe
            pending_dir = osp.join(PENDING_DIR, recipe_slug)
            if osp.exists(pending_dir):
                html_content = re.sub(
                    r'src="([^":]+)"',
                    lambda m: f'src="/pending/{recipe_slug}/{m.group(1)}"',
                    html_content,
                )

    return jsonify({
        "success": True,
        "html": html_content
    })

# ---------------------------------------------------------------------------
# Routes — Recipe Import (Gemini)
# ---------------------------------------------------------------------------

@app.route("/import/extract", methods=["POST"])
def import_extract():
    """Extract recipe using Gemini API and return preview."""
    data = request.get_json()
    url = (data.get("url") or "").strip() or None
    text = (data.get("text") or "").strip() or None

    if not url and not text:
        return jsonify({"error": "Provide a URL or pasted text."}), 400

    try:
        result = extract_recipe(url=url, text=text)
    except Exception as e:
        logger.error("Extraction failed: %s", e)
        return jsonify({"error": str(e)}), 500

    session["pending_import"] = {
        "recipe_data": result.recipe_data.model_dump(mode="json"),
        "markdown": result.markdown,
        "slug": result.slug,
        "source": result.source,
    }

    return jsonify({
        "success": True,
        "recipe": result.recipe_data.model_dump(mode="json"),
        "markdown_preview": result.markdown,
        "slug": result.slug,
        "source": result.source,
    })

@app.route("/import/confirm", methods=["POST"])
def import_confirm():
    """Save the previewed recipe to pending/."""
    pending = session.get("pending_import")
    if not pending:
        return jsonify({"error": "No pending import found. Please extract first."}), 400

    result = ImportResult(
        recipe_data=RecipeData(**pending["recipe_data"]),
        markdown=pending["markdown"],
        slug=pending["slug"],
        source=pending["source"],
    )

    try:
        save_pending(result, pending_dir=PENDING_DIR)
    except Exception as e:
        logger.error("Failed to save pending recipe: %s", e)
        return jsonify({"error": str(e)}), 500

    session.pop("pending_import", None)
    return jsonify({"success": True, "slug": result.slug})

# @app.route("/import/extract", methods=["POST"])
# def import_extract():
#     """Step 1: extract recipe via Claude and return a preview."""
#     data = request.get_json()
#     url  = (data.get("url")  or "").strip() or None
#     text = (data.get("text") or "").strip() or None

#     if not url and not text:
#         return jsonify({"error": "Provide a URL or pasted text."}), 400

#     try:
#         result = extract_recipe(url=url, text=text)
#     except Exception as e:
#         logger.error("Extraction failed: %s", e)
#         return jsonify({"error": str(e)}), 500

#     session["pending_import"] = {
#         "recipe_data": result.recipe_data.model_dump(mode="json"),
#         "markdown":    result.markdown,
#         "slug":        result.slug,
#         "source":      result.source,
#     }

#     return jsonify({
#         "recipe":           result.recipe_data.model_dump(mode="json"),
#         "markdown_preview": result.markdown,
#         "slug":             result.slug,
#         "source":           result.source,
#     })

# @app.route("/import/confirm", methods=["POST"])
# def import_confirm():
#     """Step 2: save the previewed recipe to pending/."""
#     pending = session.get("pending_import")
#     if not pending:
#         return jsonify({"error": "No pending import found. Please extract first."}), 400

#     result = ImportResult(
#         recipe_data=RecipeData(**pending["recipe_data"]),
#         markdown=pending["markdown"],
#         slug=pending["slug"],
#         source=pending["source"],
#     )

#     try:
#         save_pending(result, pending_dir=PENDING_DIR)
#     except Exception as e:
#         logger.error("Failed to save pending recipe: %s", e)
#         return jsonify({"error": str(e)}), 500

#     session.pop("pending_import", None)
#     return jsonify({"success": True, "slug": result.slug})

# ---------------------------------------------------------------------------
# Routes — pending recipes
# ---------------------------------------------------------------------------

@app.route("/pending")
def pending_list():
    """Redirect to editor page."""
    return redirect("/editor")

@app.route("/pending/promote/<slug>", methods=["POST"])
def promote(slug):
    try:
        promote_recipe(slug, pending_dir=PENDING_DIR, recipes_dir=RECIPES_DIR)
        _invalidate_shopping_list_cache()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})

@app.route("/pending/discard/<slug>", methods=["POST"])
def discard(slug):
    try:
        discard_pending(slug, pending_dir=PENDING_DIR)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})

@app.route("/editor/demote/<slug>", methods=["POST"])
def demote(slug):
    """Move a recipe from saved to pending."""
    try:
        demote_recipe(slug, recipes_dir=RECIPES_DIR, pending_dir=PENDING_DIR)
        _invalidate_shopping_list_cache()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})

@app.route("/editor/delete/<slug>", methods=["POST"])
def delete_saved(slug):
    """Delete a saved recipe."""
    try:
        delete_saved_recipe(slug, recipes_dir=RECIPES_DIR)
        _invalidate_shopping_list_cache()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})

# ---------------------------------------------------------------------------
# Routes — schedule management
# ---------------------------------------------------------------------------

@app.route("/schedule/config", methods=["GET"])
def get_schedule():
    """Get current schedule configuration."""
    config = _get_schedule_config()

    # Calculate next send date/time if enabled
    next_send = None
    if config.get("enabled"):
        day_of_week = config.get("day_of_week", 0)
        send_time = config.get("send_time", "09:00")

        today = date.today()
        days_until = (day_of_week - today.weekday()) % 7
        if days_until == 0:
            # Check if time has passed today
            hour, minute = map(int, send_time.split(":"))
            now = datetime.now()
            send_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now >= send_datetime:
                days_until = 7

        next_date = today + timedelta(days=days_until if days_until > 0 else 7)
        next_send = f"{next_date.isoformat()} {send_time}"

    return jsonify({
        "success": True,
        "config": config,
        "next_send": next_send
    })

@app.route("/schedule/config", methods=["POST"])
def save_schedule():
    """Save schedule configuration."""
    try:
        data = request.get_json()
        config = {
            "enabled": data.get("enabled", False),
            "num_recipes": int(data.get("num_recipes", 3)),
            "day_of_week": int(data.get("day_of_week", 0)),
            "send_time": data.get("send_time", "09:00"),
            "recipients": data.get("recipients", "")
        }

        _save_schedule_config(config)

        # Reschedule the job
        _reschedule_email_job()

        return jsonify({"success": True, "message": "Schedule saved"})
    except Exception as e:
        logger.error("Failed to save schedule: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/schedule/send_now", methods=["POST"])
def send_now():
    """Manually trigger scheduled email."""
    try:
        send_scheduled_shopping_list()
        return jsonify({"success": True, "message": "Email sent successfully"})
    except Exception as e:
        logger.error("Failed to send email: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------

scheduler = BackgroundScheduler()
scheduler.start()

def _reschedule_email_job():
    """Remove existing job and reschedule based on current config."""
    # Remove existing job if it exists
    if scheduler.get_job("weekly_shopping_list"):
        scheduler.remove_job("weekly_shopping_list")

    config = _get_schedule_config()
    if not config.get("enabled"):
        logger.info("Scheduled emails disabled")
        return

    day_of_week = config.get("day_of_week", 0)
    send_time = config.get("send_time", "09:00")
    hour, minute = map(int, send_time.split(":"))

    # Schedule job using cron trigger
    trigger = CronTrigger(
        day_of_week=day_of_week,
        hour=hour,
        minute=minute
    )

    scheduler.add_job(
        func=send_scheduled_shopping_list,
        trigger=trigger,
        id="weekly_shopping_list",
        name="Weekly Shopping List Email",
        replace_existing=True
    )

    logger.info("Scheduled weekly email for day=%d at %s", day_of_week, send_time)

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    os.makedirs(PENDING_DIR, exist_ok=True)

    # Initialize scheduler with current config
    _reschedule_email_job()

    try:
        app.run(host="0.0.0.0", port=5000, debug=True)
    finally:
        scheduler.shutdown()
