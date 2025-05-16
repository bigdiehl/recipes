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