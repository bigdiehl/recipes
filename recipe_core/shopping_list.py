#!/usr/bin/env python3

"""
DESCRIPTION: Parses recipe data from the filesystem, merges ingredients across
recipes, and generates a shopping list in Markdown.
"""

from __future__ import annotations

import os
import pandas as pd
import yaml
import logging

from pprint import pprint
from typing import  List, Dict, Tuple
from termcolor import colored
import numpy as np

from recipe_core.foods import get_food
from recipe_core.recipe_lib import Ingredient, RecipeData, MergedIngredient, parse_quantity
from recipe_core import units

logger = logging.getLogger(__name__)

RECIPES_DIR = os.path.join(os.path.dirname(__file__), '../data/recipes')


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

def find_recipe_dirs(target_dir: str = RECIPES_DIR) -> List[str]:
    """Return subdirectories of target_dir that contain a recipe.yaml file."""
    dirs = []
    for root, _, files in os.walk(target_dir):
        if "recipe.yaml" in files:
            dirs.append(root)
    return dirs


def get_recipe_slug(recipe_dir: str) -> str:
    """Return the folder name (slug) for a recipe directory."""
    return os.path.basename(recipe_dir)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _recipe_data_to_ingredients(recipe_data: RecipeData, slug: str) -> List[Ingredient]:
    """Convert a RecipeData's ingredient list into Ingredient objects."""
    ingredients = []
    for item in recipe_data.ingredients:
        food = get_food(item.food)
        quantity = parse_quantity(item.quantity)
        ingredients.append(Ingredient(food=food, quantity=quantity, source=slug))
    return ingredients

def get_shopping_list_data(
    target_dir: str = RECIPES_DIR,
) -> Tuple[Dict[str, List[Ingredient]], Dict[str, RecipeData]]:
    """
    Walk target_dir and load all recipes that have a recipe.yaml file.

    Returns:
        ingredients_by_recipe:  slug → list of Ingredient
        metadata_by_recipe:     slug → RecipeData
    """
    ingredients_by_recipe: Dict[str, List[Ingredient]] = {}
    metadata_by_recipe: Dict[str, RecipeData] = {}

    for recipe_dir in find_recipe_dirs(target_dir):
        slug = get_recipe_slug(recipe_dir)
        yaml_path = os.path.join(recipe_dir, "recipe.yaml")

        try:
            recipe_data = RecipeData.from_yaml(yaml_path)
        except Exception as e:
            logger.error("Failed to load recipe '%s': %s", slug, e)
            continue

        metadata_by_recipe[slug] = recipe_data
        ingredients_by_recipe[slug] = _recipe_data_to_ingredients(recipe_data, slug)

    return ingredients_by_recipe, metadata_by_recipe

# ---------------------------------------------------------------------------
# Merging and sorting
# ---------------------------------------------------------------------------

def get_merged_shopping_list(
    recipes: List[str],
    ingredients_by_recipe: Dict[str, List[Ingredient]],
) -> Tuple[Dict[str, List[MergedIngredient]], Dict[str, List[MergedIngredient]]]:
    """
    Merge ingredients across the requested recipes and sort into two buckets:
      - main:      things you likely need to buy
      - secondary: things you probably already have (likely_to_have=True)

    Both dicts are keyed by FoodType category name, values sorted alphabetically.
    Incompatible units are kept as separate quantity groups within a MergedIngredient.
    Ingredients listed without a quantity are tracked separately as 'unspecified'.
    """
    # Collect all ingredients for the selected recipes
    all_ingredients: List[Ingredient] = []
    for recipe in recipes:
        if recipe not in ingredients_by_recipe:
            logger.warning("Recipe '%s' not found in loaded data — skipping.", recipe)
            continue
        all_ingredients.extend(ingredients_by_recipe[recipe])

    # Merge by food identity using MergedIngredient
    merged: Dict[int, MergedIngredient] = {}
    for ingredient in all_ingredients:
        key = id(ingredient.food)
        if key not in merged:
            merged[key] = MergedIngredient(food=ingredient.food)
        merged[key].add(ingredient)

    merged_list = list(merged.values())

    # Convert to preferred units where possible
    for mi in merged_list:
        mi.to_preferred_unit()

    # Filter out ingredients below min_amount
    merged_list = [mi for mi in merged_list if mi.is_above_min()]

    # Partition into main / secondary and sort alphabetically
    main: Dict[str, List[MergedIngredient]] = {}
    secondary: Dict[str, List[MergedIngredient]] = {}

    for mi in merged_list:
        category = mi.food.category.name
        target = secondary if mi.food.likely_to_have else main
        target.setdefault(category, []).append(mi)

    sort_key = lambda mi: mi.food.get_name()
    main = {k: sorted(v, key=sort_key) for k, v in sorted(main.items())}
    secondary = {k: sorted(v, key=sort_key) for k, v in sorted(secondary.items())}

    return main, secondary


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

if 0:
    def generate_shopping_list_md(
        names: List[str],
        main: Dict[str, List[MergedIngredient]],
        secondary: Dict[str, List[MergedIngredient]],
        show_sources: bool = False,
    ) -> str:
        """
        Render the shopping list as a Markdown string.

        Args:
            names:        The human-friendly names of the selected recipes (for the header).
            recipes:      Slugs of the selected recipes (for the header).
            main:         Primary shopping list grouped by category.
            secondary:    'Likely to already have' list grouped by category.
            show_sources: If True, annotate each quantity with which recipe it came from.
        """

        def _format_line(mi: MergedIngredient) -> str:
            qty_str = mi.format_quantity()
            if qty_str:
                return f"- {mi.food.get_name()} ({qty_str})\n"
            return f"- {mi.food.get_name()}\n"

        def _section(heading: str, data: Dict[str, List[MergedIngredient]]) -> str:
            out = f"## {heading}\n\n"
            for category, ingredients in data.items():
                out += f"#### {category}\n"
                for mi in ingredients:
                    out += _format_line(mi)
                out += "\n"
            return out

        md = "# Shopping List\n\n"
        md += "For:\n\n"
        
        for i, name in enumerate(names):
            md += f"[{i+1}] {name}\n"
        md += "\n"
        md += _section("Main List", main)
        md += _section("Likely to Already Have", secondary)

        return md

else:
    def generate_shopping_list_md(
        names: List[str],
        slugs: List[str],
        main: Dict[str, List[MergedIngredient]],
        secondary: Dict[str, List[MergedIngredient]],
        show_sources: bool = False,
    ) -> str:
        """
        Render the shopping list as a Markdown string.

        Args:
            names:          Human readable names of recipes
            recipes:        Slugs of the selected recipes.
            main:           Primary shopping list grouped by category.
            secondary:      'Likely to already have' list grouped by category.
            show_sources:   If True, add an additional column to the table showing which recipe(s) 
                            each ingredient came from.
        """

        def _section(heading: str, data: Dict[str, List[MergedIngredient]]) -> str:
            # Flatten all categories into a single list of (category, name, qty) rows
            rows = []
            for category, ingredients in data.items():
                for mi in ingredients:
                    new_rows = [
                        category,
                        mi.food.get_name(),
                        mi.format_quantity(slugs),
                    ]
                    if show_sources:
                        new_rows.append(mi.format_sources(slugs))
                    rows.append(new_rows)

            if not rows:
                return ""

            w_cat  = max(max(len(r[0]) for r in rows), len("Category"))
            w_name = max(max(len(r[1]) for r in rows), len("Ingredient"))
            w_qty  = max(max(len(r[2]) for r in rows), len("Quantity"))
            
            if show_sources:
                w_src  = max(max(len(r[3]) for r in rows), len("Sources"))
                
                header    = f"| {'Category':<{w_cat}} | {'Ingredient':<{w_name}} | {'Quantity':<{w_qty}} | {'Sources':<{w_src}} |"
                separator = f"| {'-' * w_cat} | {'-' * w_name} | {'-' * w_qty} | {'-' * w_src} |"
                
                lines = [header, separator]
                last_cat = None
                for cat, name, qty, src in rows:
                    display_cat = cat if cat != last_cat else ""
                    last_cat = cat
                    lines.append(f"| {display_cat:<{w_cat}} | {name:<{w_name}} | {qty:<{w_qty}} | {src:<{w_src}} |")
                
            else:
                header    = f"| {'Category':<{w_cat}} | {'Ingredient':<{w_name}} | {'Quantity':<{w_qty}} |"
                separator = f"| {'-' * w_cat} | {'-' * w_name} | {'-' * w_qty} |"
                
                lines = [header, separator]
                last_cat = None
                for cat, name, qty in rows:
                    display_cat = cat if cat != last_cat else ""
                    last_cat = cat
                    lines.append(f"| {display_cat:<{w_cat}} | {name:<{w_name}} | {qty:<{w_qty}} |")

            return f"## {heading}\n\n" + "\n".join(lines) + "\n\n"

        md = "# Shopping List\n\n"
        md += "Recipes:\n\n"
        for i, name in enumerate(names):
            md += f"[{i+1}] {name}<br>\n"
        md += "\n"
        md += _section("Main List", main)
        md += "<br>\n"
        md += _section("Likely to Already Have", secondary)

        return md



# ---------------------------------------------------------------------------
# CLI entry point for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    recipes = [
        "black_bean_and_pepper_jack_tostadas",
        "butternut_squash_soup",
        "test_recipe"
    ]

    target_dir = os.path.join(os.path.dirname(__file__), 'test')
    ingredients_by_recipe, metadata_by_recipe = get_shopping_list_data(target_dir=target_dir)
    main, secondary = get_merged_shopping_list(recipes, ingredients_by_recipe)
    
    names = [metadata_by_recipe[slug].name for slug in recipes]
    md = generate_shopping_list_md(
        names, 
        recipes,
        main, 
        secondary, 
        show_sources=True
    )

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "shopping_list.md"), "w") as f:
        f.write(md)

    print(md)
