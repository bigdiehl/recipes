import json
import logging
import os
import os.path as osp
from pathlib import Path
import re
from dataclasses import dataclass

import markdown
import yaml
from flask import Flask, abort, jsonify, render_template, request, send_from_directory, session

from recipe_core.recipe_lib import RecipeData
from recipe_core.shopping_list import (
    find_recipe_dirs,
    generate_shopping_list_md,
    get_merged_shopping_list,
    get_shopping_list_data
)
# from recipe_importer import ImportResult, discard_pending, extract_recipe, promote_recipe, save_pending

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

    return markdown.markdown(md, extensions=["tables"])

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
    data = request.get_json()
    email = data.get("email")
    # TODO: wire up email sending (Flask-Mail / SendGrid / smtplib)
    logger.info("Sending shopping list to %s", email)
    return jsonify({"success": True})

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

    html_content = markdown.markdown(md_content)
    html_content = re.sub(
        r'src="([^":]+)"',
        lambda m: f'src="recipes/{recipe.slug}/{m.group(1)}"',
        html_content,
    )
    return jsonify({"filename": md_file, "content": html_content})

# ---------------------------------------------------------------------------
# Routes — AI recipe import
# ---------------------------------------------------------------------------

@app.route("/import", methods=["GET"])
def import_page():
    return render_template("import.html", active_page="import")

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
    slugs = []
    if osp.exists(PENDING_DIR):
        slugs = sorted(
            d for d in os.listdir(PENDING_DIR)
            if osp.isdir(osp.join(PENDING_DIR, d))
        )
    return render_template("pending.html", slugs=slugs, active_page="import")

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

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    os.makedirs(PENDING_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
