
"""DESCRIPTION: Adds the recipe names and paths to the web app database. Makes any path updates
needed, and removes any recipes that are no longer found in the filesystem"""

import os
from app import app, db, Recipe
import re

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

if __name__ == '__main__':

    with app.app_context():
        # Make sure tables exist
        db.create_all()
        import_recipes()

        # To view database contents from CLI, use sqlite3 and the command 'SELECT * FROM recipe;'
        # sqlite3 instance/app.db 'SELECT * FROM recipe;'