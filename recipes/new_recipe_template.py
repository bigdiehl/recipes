#!/usr/bin/python3

# Used to create a new directory and starter files for a new recipe
# Usage: python3 new_recipe_template.py <recipe_name>

import os
import sys

recipe_name = sys.argv[1]

if not os.path.exists(recipe_name):
    os.mkdir(recipe_name)

with open(os.path.join(recipe_name, "shopping_list.csv"), "w") as f:
    f.write("quantity, food\n")

with open(os.path.join(recipe_name, "metadata.yaml"), "w") as f:
    f.write("servings: \n")
    f.write("category: \n")
    f.write("meal: \n")
    f.write("enabled: True\n")
    f.write("min_period_weeks: 4\n")
    
with open(os.path.join(recipe_name, "recipe.md"), "w") as f:
    f.write("# Title\n\n")
    f.write("Servings:\n\n")
    f.write(r'<img style="float: right;" src="image.png" width=400>')
    f.write("\n\n## Ingredients")
    f.write("\n\n## Directions\n")