import os
import os.path as osp
import pandas as pd
import yaml
from pint import UnitRegistry
from pprint import pprint
from foods import get_food
from typing import  List, Dict
from termcolor import colored
import numpy as np
from recipe_lib import Ingredient, RecipeMetaData

RECIPES_DIR = os.path.join(os.path.dirname(__file__), 'recipes')

def find_markdown_files(target_dir):
    """Walk the target directory and return a list of markdown files found (full path)"""
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


def get_shopping_list_data(target_dir="./recipes"):
    """Traverses target_dir and looks for shopping list and metadata docs. Parses files and converts
    data to python types.  Returns: 
    - lists: dict[str,Dataframe]
    - metas: dict[str,dict]
    """

    unit = UnitRegistry()

    def add_dimensionless_unit(name):
        unit.define(f"{name} = 1 * dimensionless")

    add_dimensionless_unit("bundle")
    add_dimensionless_unit("cans")
    add_dimensionless_unit("tub")

    lists = {}
    metas = {}

    # Each recipe folder should have these two files
    LIST_NAME = "shopping_list.csv"
    METADATA_NAME = "metadata.yaml"

    # Read in all recipe data (shopping list, metadata)
    # -----------------------------------------------------------------
    for root, dirs, files in os.walk(target_dir):
        if LIST_NAME in files and METADATA_NAME in files:
            recipe_name = os.path.basename(root)
            try:
                lists[recipe_name] = pd.read_csv(
                    os.path.join(root, LIST_NAME),
                    skipinitialspace=True
                )
            except pd.errors.ParserError as e:
                print(f"Error parsing {os.path.join(root, LIST_NAME)}")
                raise e
            
            with open(os.path.join(root, METADATA_NAME)) as f:
                metas[recipe_name] = yaml.safe_load(f)
                

    # Convert shopping list data (i.e. units, food) to Python types
    # -----------------------------------------------------------------
    for name, df in lists.items():
            
        def convert_to_food(name):
            food = get_food(name)
            if food is None:
                raise ValueError(f"{name} does not match any defined foods in foods.py")
            return food
        
        def convert_quantity(name):
            try:
                u = unit(name)
                return u
            except:
                if name == "-":
                    return unit("") # Dimensionless
                else:
                    raise ValueError(f"Undefined unit: {name}")
        
        try:
            df['quantity'] = df['quantity'].apply(convert_quantity)
            df['food'] = df['food'].apply(convert_to_food)
        except Exception as e:
            print(colored(f"Error encountered when parsing shopping list for {name}", "red"))
            raise e
        
    # Combine metadata to dataframe
    # -----------------------------------------------------------------
    # Necessary?
    # metas_df = pd.DataFrame(metas)
    # This creates df where rowsfd are meta variables and columns are recipes

    return lists, metas


def get_merged_shopping_list(recipes: List[str], lists: Dict[str, pd.DataFrame]):

    # Merge and sort
    # -----------------------------------------------------------------
    
    # Get combined shopping list for the requested recipes
    combined = [lists[recipe] for recipe in recipes]
    combined_df = pd.concat(combined).reset_index(drop=True)

    # Merge duplicate foods
    merged_ingredients : List[Ingredient] = []
    temp_df = combined_df.copy()
    while len(temp_df) > 0:

        # Get all foods of the same type
        target_food = temp_df["food"][0]
        same_foods = temp_df[temp_df["food"] == target_food]

        # Combine into single ingredient
        ingredients: List[Ingredient] = []
        for index, row in same_foods.iterrows():
            try:
                ingredients.append(Ingredient(**row.to_dict()))
            except:
                breakpoint()
                # Figure out why we are here

        # 'add' ingredients of same food type together to get the total quantity
        merged_ingredients.append(np.sum(ingredients))
        
        # Remove rows
        temp_df = temp_df[temp_df["food"] != target_food] 
        temp_df.reset_index(inplace=True, drop=True)

    # Convert to preferred units
    for ingredient in merged_ingredients:
        ingredient.to_preferred_unit()

    # Sort into categories
    main_sorted: dict[str, List[Ingredient]] = {} # main shopping list
    secondary_sorted: dict[str, List[Ingredient]] = {} # list of likely to have

    for ingredient in merged_ingredients:
        
        category = ingredient.food.category.name
        
        # TODO - clean up. Add logic for food.min_amount
        
        if not ingredient.food.likely_to_have:
            if category not in main_sorted:
                main_sorted[category] = []
            main_sorted[category].append(ingredient)
        else:
            if category not in secondary_sorted:
                secondary_sorted[category] = []
            secondary_sorted[category].append(ingredient)

    # Sort categories and ingredients alphabetically
    f1 = lambda x: x.food.get_name() # for sorting ingredients
    f2 = lambda x: x[0] # for sorting categories

    main_sorted = {k:sorted(v, key=f1) for k, v in sorted(main_sorted.items(), key=f2)}
    secondary_sorted = {k:sorted(v, key=f1) for k, v in sorted(secondary_sorted.items(), key=f2)}

    return main_sorted, secondary_sorted


def generate_shopping_list_md(recipes, main_sorted, secondary_sorted, output_dir="output"):
    """Generate markdown for the provided shopping list"""

    print(f"generate_shopping_list_md: {recipes}")
    # TODO - convert decimal to fractions (e.g. 0.5 to 1/2, but with compact 1/2)
    md = ""
    md += "# Shopping List\n\n"
    md += "For:\n\n"
    for recipe in recipes:
        md += f"- {recipe}\n"
    md += "\n"
    md += "## Main List\n\n"
    for category, ingredients in main_sorted.items():
        md += f"#### {category}\n"
        ingredients = sorted(ingredients, key=lambda x: x.food.get_name())
        for ingredient in ingredients:
            md += f"- {ingredient.food.get_name()} ({str(ingredient.quantity)})\n"
    
    md += "----------\n\n"
    md += "## Likely to Already Have\n\n"
    for category, ingredients in secondary_sorted.items():
        md += f"#### {category}\n"
        ingredients = sorted(ingredients, key=lambda x: x.food.get_name())
        for ingredient in ingredients:
            md += f"- {ingredient.food.get_name()} ({str(ingredient.quantity)})\n"
        
    return md


if __name__ == "__main__":

    from pprint import pprint

    md_files = find_markdown_files(RECIPES_DIR)
    names = []
    for name in md_files:
        name: str = os.path.basename(os.path.dirname(name)).lower()

    recipes = [
        'honey_lime_enchiladas',
        'cajun_chicken_linguine',
        'clam_chowder',
    ]

    lists, metas = get_shopping_list_data()
    main, secondary = get_merged_shopping_list(recipes, lists)
    md = generate_shopping_list_md(recipes, main, secondary)

    output_dir="output"
    with open(osp.join(output_dir, "shopping_list.md"), "w") as f:
        f.write(md)