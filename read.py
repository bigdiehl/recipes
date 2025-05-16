import pandas as pd
import os
import yaml
from pint import UnitRegistry
from pprint import pprint
from foods import get_food
from typing import  List
from termcolor import colored
import numpy as np

unit = UnitRegistry()

target_dir = "."

lists = {}
metas = {}

from recipe_lib import Ingredient, RecipeMetaData

# Each recipe folder should have these two files
list_name = "shopping_list.csv"
metadata_name = "metadata.yaml"

# Read in all recipe data (shopping list, metadata)
# -----------------------------------------------------------------
for root, dirs, files in os.walk(target_dir):
    if list_name in files and metadata_name in files:
        recipe_name = os.path.basename(root)
        # lists[recipe_name] = os.path.join(root, list_name)
        # metas[recipe_name] = os.path.join(root, metadata_name)
        
        lists[recipe_name] = pd.read_csv(
            os.path.join(root, list_name),
            skipinitialspace=True
        )
        
        with open(os.path.join(root, metadata_name)) as f:
            metas[recipe_name] = yaml.safe_load(f)
            metas[recipe_name] = yaml.safe_load(f)
            

# Convert shopping list data (i.e. units, food) to Python types
# -----------------------------------------------------------------
for name, df in lists.items():
        
    def convert_to_food(name):
        food = get_food(name)
        if food is None:
            raise ValueError(f"{name} does not match any defined foods in foods.py")
        return food
    
    try:
        df['quantity'] = df['quantity'].apply(lambda x: unit(x))
        df['food'] = df['food'].apply(convert_to_food)
    except Exception as e:
        print(colored(f"Error encountered when parsing shopping list for {name}", "red"))
        raise e
    
# Combine metadata to dataframe
# -----------------------------------------------------------------
# Necessary?


# Select recipes
# -----------------------------------------------------------------

# TODO - Method for selecting recipes
this_week = [
    'honey_lime_enchiladas',
    'cajun_chicken_linguine',
    'honey_lime_enchiladas',
]
    
# Merge and sort
# -----------------------------------------------------------------
combined = [lists[key] for key in this_week]
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
        ingredients.append(Ingredient(**row.to_dict()))

    merged_ingredients.append(np.sum(ingredients))
    
    # Remove rows
    temp_df = temp_df[temp_df["food"] != target_food] 
    temp_df.reset_index(inplace=True, drop=True)


# Convert to preferred units
for ingredient in merged_ingredients:
    ingredient.to_preferred_unit()

# Sort into categories
main_sorted = {}
secondary_sorted = {}

for ingredient in merged_ingredients:
    
    category = ingredient.food.category
    
    # TODO - clean up. Add logic for food.min_amount
    
    if not ingredient.food.likely_to_have:
        if category not in main_sorted:
            main_sorted[category] = []
        main_sorted[category].append(ingredient)
    else:
        if category not in secondary_sorted:
            secondary_sorted[category] = []
        secondary_sorted[category].append(ingredient)
    
# print("Main")
# pprint(main_sorted)
# print("Likely to have")
# pprint(secondary_sorted)


# Generate shopping list document
# -----------------------------------------------------------------
with open("shopping_list.md", "w") as f:
    f.write("# Shopping List\n\n")
    f.write("For:\n")
    for recipe in this_week:
        f.write(f"- {recipe}\n")
    f.write("\n")
    f.write("## Main List\n\n")
    for category, ingredients in main_sorted.items():
        f.write(f"#### {category.value}\n")
        ingredients = sorted(ingredients, key=lambda x: x.food.get_name())
        for ingredient in ingredients:
            f.write(f"- {ingredient.food.get_name()} ({str(ingredient.quantity)})\n")
    
    f.write("----------\n\n")
    f.write("## Likely to Already Have\n\n")
    for category, ingredients in secondary_sorted.items():
        f.write(f"#### {category.value}\n")
        ingredients = sorted(ingredients, key=lambda x: x.food.get_name())
        for ingredient in ingredients:
            f.write(f"- {ingredient.food.get_name()} ({str(ingredient.quantity)})\n")


# pprint(merged_ingredients)

# TODO - support for no quantity (e.g. 'tortillas') Should be obvious with recipe given