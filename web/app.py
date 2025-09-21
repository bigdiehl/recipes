
import os
from flask import Flask, render_template, abort, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import markdown
import re

db = SQLAlchemy()

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False) # Human formatted name
    dir = db.Column(db.String(200), nullable=False) # relative to 'recipes' dir
    md_filename = db.Column(db.String(200), nullable=False) 
    selected = db.Column(db.Boolean, default=False)

# -----------------------------------------------------------------------

RECIPES_DIR = os.path.join(os.path.dirname(__file__), 'recipes')

def find_markdown_files(target_dir):
    md_files = []
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.endswith('.md'):
                md_files.append(os.path.join(root, file))
    return md_files

def get_recipe_names():
    """Converts recipe dir names to space-seperated and capitalized names. Assumes recipe dir
    name is underscore delimited."""
    md_files = find_markdown_files(RECIPES_DIR)
    names = []
    for name in md_files:
        name: str = os.path.basename(os.path.dirname(name)).lower()
        name = name.replace("_", " ")
        name = name.title()
        names.append(name)
    return names

def import_recipes():

    md_files = find_markdown_files(RECIPES_DIR)
    recipe_names = get_recipe_names()

    for idx in range(len(recipe_names)):

        name = recipe_names[idx]
        existing = Recipe.query.filter_by(name=name).first()

        # Get path relative to the 'recipes' dir
        recipe_dir_name = os.path.dirname(md_files[idx])
        recipe_dir_name = re.sub(RECIPES_DIR, "", recipe_dir_name)
        if recipe_dir_name[0] == "/":
            recipe_dir_name = recipe_dir_name[1:]

        if existing:
            print(f"'{name}' already in database.")
            if existing.dir != recipe_dir_name:
                existing.dir = recipe_dir_name
                print(f"Updating path to {recipe_dir_name}")
        else:

            recipe = Recipe(
                name=name,
                dir=recipe_dir_name,
                md_filename=os.path.basename(md_files[idx])
            )
            db.session.add(recipe)
            print(f"Added '{name}' to database")

        # TODO - remove database entries that are no longer present in filesystem.

    db.session.commit()
    print("Import complete.")

# -----------------------------------------------------------------------

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'  # SQLite file
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# -----------------------------------------------------------------------

@app.route('/')
def index():
    recipes = Recipe.query.all()
    selected_recipes = [recipe for recipe in recipes if recipe.selected]
    return render_template(
        'index.html', 
        active_page="home", 
        recipes=sorted(selected_recipes, key=lambda x: x.name)
    )


@app.route('/deselect/<int:recipe_id>', methods=['POST'])
def deslect(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    recipe.selected = False
    db.session.commit()
    return jsonify({'success': True, 'selected': recipe.selected})

# -----------------------------------------------------------------------

@app.route('/recipes_list')
def recipes_list():
    recipes = Recipe.query.all()

    return render_template(
        'recipes_list.html', 
        recipes=sorted(recipes, key=lambda x: x.name), 
        active_page="recipes_list", 
    )

@app.route('/recipes_list/toggle/<int:recipe_id>', methods=['POST'])
def toggle(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    recipe.selected = not recipe.selected
    db.session.commit()
    return jsonify({'success': True, 'selected': recipe.selected})

@app.route('/recipes/<path:file>')
def serve_markdown_file(file):
    return send_from_directory("recipes", file)

@app.route('/markdown/api/<recipe>')
def get_markdown_content(recipe):

    recipe = Recipe.query.filter_by(name=recipe).first()
    md_file = os.path.join("recipes", recipe.dir, recipe.md_filename)
    print(f"Serving md_file={md_file}")

    if not md_file.endswith('.md'):
        print(f"File must end with .md,  got {md_file}.")
        abort(404)

    if not os.path.exists(md_file):
        abort(404)

    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()

        html_content = markdown.markdown(md_content)

        # Replace relative image src paths to use the markdown file server route
        html_content = re.sub(
            r'src="([^":]+)"',  # match src="something" that is not a full URL
            lambda m: f'src="recipes/{recipe.dir}/{m.group(1)}"',
            html_content
        )
        # print(html_content)

    return jsonify({
        'filename': md_file,
        'content': html_content
    })

if __name__ == '__main__':
    # TODO - add recipe import. Just have it run here when we start the app.
    with app.app_context():
        db.create_all()
        import_recipes()
        # To view database contents from CLI, use sqlite3 and the command 'SELECT * FROM recipe;'
        # sqlite3 instance/app.db 'SELECT * FROM recipe;'
    app.run(host='0.0.0.0', port=5000, debug=True)