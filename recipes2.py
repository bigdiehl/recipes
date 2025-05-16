
from dataclasses import dataclass
from enum import Enum, auto
import yaml
from typing import Optional

from recipe_lib import Recipe, Food, Ingredient, foods


ingredients = [
    Ingredient(quantity=2, food="chicken breast"),
    Ingredient(quantity=2, unit="tsp", food="cajun_seasoning"),
    Ingredient(quantity=2, food="chicken breast"),
    Ingredient(quantity=2, food="chicken breast"),
    Ingredient(quantity=2, food="chicken breast"),
]

recipe = Recipe(
    ingredients=ingredients, 
    servings=4,
    instructions= ""
)

