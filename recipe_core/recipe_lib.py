"""DESCRIPTION: Contains various supported classes/enums"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional, List, Union

from dataclasses import dataclass, field
import yaml
from pint import UnitRegistry, errors as pint_errors
from pint.facets.plain import PlainQuantity as Quantity
from pydantic import BaseModel, field_validator, ConfigDict
from fractions import Fraction

from recipe_core import units

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Units
# ---------------------------------------------------------------------------

ureg = UnitRegistry()

# These are custom base units. Meaning that they don't relate to anything else.
_CUSTOM_UNITS = [
    ["bundle"],
    ["cans", "can"], 
    ["tub", "tubs"], 
    ["bunch"], 
    ["clove", "cloves"], 
    ["slice", "slices"],
     # "not applicable" (na) — use for ingredients where specifying a unit doesn't make sense.
    ['na', 'n/a']
]

for _unit_names in _CUSTOM_UNITS:
    aliases = " = ".join(_unit_names)
    ureg.define(f"{_unit_names[0]} = [] = {aliases}")
    logger.debug("Registered new unit: '%s'", _unit_names[0])
    
def _register_unit(name: Union[str, List[str]]):
    """Register a unit as a base type if not already known."""
    try:
        ureg.parse_units(name)
    except pint_errors.UndefinedUnitError:
        ureg.define(f"{name} = [] = {name}")
        logger.debug("Registered new unit: '%s'", name)
        
        
def parse_quantity(raw: str):
    """
    Parse a quantity string into a Pint Quantity, or return None if unspecified.

    Examples:
        "1.5 cups"  → Quantity(1.5, 'cup')
        "2 cans"    → Quantity(2, 'cans')                (custom base unit)
        "3"         → Quantity(3, 'dimensionless')       (dimensionless)
        ""          → None                               (unspecified)
    """
    raw = raw.strip()
    if not raw:
        return None

    # Try Pint first
    try:
        return ureg(raw)
    except pint_errors.UndefinedUnitError as e:
        
        words = raw.split(" ")
        # Handle cases where we have a unit by no number. If 'raw' is just a number, it should have
        # already been caught by 'ureg(raw)'.
        if len(words) == 1 or len(words) > 2:
            raise ValueError(f"Unable to parse quantity: '{raw}'." \
                "A quantity should be a number optionally followed by a unit.")
            
        # Unknown unit — register it as a base type and retry
        unit_name = words[1]
        _register_unit(unit_name)
        return ureg(raw)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FoodType(Enum):
    Baking = "BAKING"
    Dairy = "DAIRY"
    Fruit = "FRUIT"
    Meat = "MEAT"
    Other = "OTHER"
    Spice = "SPICE"
    Vegetable = "VEGETABLE"

class CategoryType(Enum):
    Entree = "ENTREE"
    Salad = "SALAD"
    Dessert = "DESSERT"
    Side = "SIDE"

class MealType(Enum):
    Breakfast = "BREAKFAST"
    Lunch = "LUNCH"
    Dinner = "DINNER"
    
# ---------------------------------------------------------------------------
# Food registry model
# ---------------------------------------------------------------------------

class Food(BaseModel):
    """
    Represents a known food in the registry.

    Attributes:
        names:          All names/aliases for this food. The first is used as the
                        display name on shopping lists.
        category:       Food type used for grouping on the shopping list.
        preferred_unit: Unit to convert to when generating a shopping list (e.g. 'cup').
        min_amount:     Minimum quantity (in preferred_unit) that is worth listing.
                        E.g. 1 tsp of flour is probably not worth adding to the list.
        likely_to_have: If True, the food is sorted into the secondary 'probably have
                        this already' section of the shopping list.
    """

    names: List[str]
    category: FoodType
    preferred_unit: Optional[str] = None
    min_amount: Optional[float] = None
    likely_to_have: bool = False

    @field_validator("names", mode="before")
    @classmethod
    def coerce_names_to_list(cls, v):
        if isinstance(v, str):
            return [v.lower().strip()]
        return [n.lower().strip() for n in v]

    def has_name(self, name: str) -> bool:
        """Returns true if the name matches one of the food names"""
        return name.lower().strip() in self.names

    def get_name(self) -> str:
        """Return the primary name for the food"""
        return self.names[0]

    @classmethod
    def default(cls, name: str) -> "Food":
        """Return a minimal Food for ingredients not found in the registry."""
        logger.warning("Unregistered food: '%s' — using default (FoodType.Other)", name)
        return cls(names=[name], category=FoodType.Other)
    
# ---------------------------------------------------------------------------
# Ingredient - holds a live Pint Quantity
# ---------------------------------------------------------------------------
            
@dataclass
class Ingredient:
    """
    Pairs a Food with a quantity.  Quantity may be a plain float (dimensionless)
    or a pint Quantity (has units).
    """
    food: Food
    quantity: Optional[Union[float, Quantity]] = None
    source: str = ""
        
    def __repr__(self):
        return f"Ingredient(food={self.food.get_name()}, quantity={self.quantity}, source={self.source!r})"

# ---------------------------------------------------------------------------
# MergedIngredient — result of combining one food across multiple recipes
# ---------------------------------------------------------------------------

def _units_are_compatible(a, b) -> bool:
    """Return True if two Pint Quantities can be added together."""
    try:
        _ = a + b
        return True
    except Exception:
        return False

def _float_to_frac(value: float, max_denominator: int = 8) -> str:
    """Convert a float to a compact fraction string"""
    
    frac = Fraction(value).limit_denominator(max_denominator)
    whole = int(frac)
    remainder = frac - whole
    
    # Create string representation
    if remainder == 0:
        return str(whole)
    elif whole == 0:
        return f"{remainder.numerator}/{remainder.denominator}"
    else:
        return f"{whole} {remainder.numerator}/{remainder.denominator}"
    
@dataclass
class QuantityGroup:
    """
    One group of compatible quantities for a food, plus which recipes
    contributed to this group.
    """
    quantity: object          # summed Pint Quantity
    sources: List[str] = field(default_factory=list)
    

    def format(self) -> str:
        """Return a human-readable string for this quantity, suppressing
        dimensionless unit labels."""
        q = self.quantity
        unit_str = format(q.units)
        mag = _float_to_frac(float(q.magnitude))
        
        if unit_str in ("", "dimensionless"):
            return mag
        return f"{mag} {unit_str}"


@dataclass
class MergedIngredient:
    """
    The result of merging one food across all selected recipes.

    quantities:     holds one QuantityGroup per incompatible unit type.
    unspecified:    holds the slugs of recipes that listed this food without a quantity.
    """
    food: "Food"
    quantities: List[QuantityGroup] = field(default_factory=list)
    unspecified: List[str] = field(default_factory=list)   # recipe slugs

    def add(self, ingredient: Ingredient):
        """Incorporate one Ingredient into this MergedIngredient."""
        if ingredient.quantity is None:
            self.unspecified.append(ingredient.source)
            return

        # Try to merge into an existing compatible group
        for group in self.quantities:
            if _units_are_compatible(group.quantity, ingredient.quantity):
                group.quantity = group.quantity + ingredient.quantity
                group.sources.append(ingredient.source)
                return

        # No compatible group found — start a new one
        self.quantities.append(
            QuantityGroup(quantity=ingredient.quantity, sources=[ingredient.source])
        )

    def to_preferred_unit(self):
        """Convert each quantity group to the food's preferred unit where possible."""
        preferred = self.food.preferred_unit
        if not preferred:
            return
        for group in self.quantities:
            try:
                group.quantity = group.quantity.to(preferred)
            except Exception:
                pass  # incompatible unit — leave as-is

    def format_quantity(self, recipe_slugs: List[str]) -> str:
        """
        Render the full quantity string for the shopping list. 'recipe_slugs' is the slugs for the
        selected recipes. Used to number the sources.

        Example: "2 cans + 1 cup + unspecified from [1]"
        """
        parts = []

        for group in self.quantities:
            s = group.format()
            parts.append(s)

        if self.unspecified:
            if len(parts) > 0:
                sources = {slug: i for i, slug in enumerate(recipe_slugs)}
                unspecified_sources = [f"[{sources[slug]+1}]" for slug in self.unspecified]
                unspecified_sources = ", ".join(unspecified_sources)
                parts.append(f"unspecified from {unspecified_sources}")
            else:
                parts.append("")

        return " + ".join(parts) if parts else ""
    
    def format_sources(self, recipe_slugs: List[str]):
        """Returns a formatted list of sources. 'recipe_slugs' is the slugs for the selected
        recipes. Used to number the sources."""
        all_sources = {slug: i for i, slug in enumerate(recipe_slugs)}
        sources = set()

        for q in self.quantities:
            for s in q.sources:
                sources.add(all_sources[s])
        
        for s in self.unspecified:
            sources.add(all_sources[s])
                
        sources = sorted(sources)
        return ", ".join(f"[{s+1}]" for s in sources)

    def is_above_min(self) -> bool:
        """
        Return False only when every quantity group is below min_amount.
        If there are multiple groups or unspecified entries, always include.
        """
        min_amt = self.food.min_amount
        if min_amt is None:
            return True
        if self.unspecified or len(self.quantities) > 1:
            return True
        if not self.quantities:
            return False
        q = self.quantities[0].quantity
        try:
            return q.magnitude >= min_amt
        except Exception:
            return True


# ---------------------------------------------------------------------------
# Recipe data schema  (lives in recipe.yaml)
# ---------------------------------------------------------------------------

class RecipeIngredient(BaseModel):
    """A single ingredient line as it appears in a recipe.yaml file."""
    model_config = ConfigDict(coerce_numbers_to_str=True)
    
    food: str           # raw name — matched against registry at shopping-list time
    quantity: str = ""  # e.g. "1.5 cups", "3", "0.5 lb"
    
class RecipeData(BaseModel):
    """
    Schema for the recipe.yaml file that lives alongside each recipe's markdown file. This data
    is used in shopping list generation, and in rendering a recipe if recipe.md is not present. 

    Attributes:
        name:               Human-readable name of the recipe
        servings:           Number of servings the recipe makes. 
        meal:               Which meal this recipe is primarily intended for.
        category:           ENTREE, SALAD, DESSERT, SIDE
        ingredients:        A list of the ingredients for the recipe. These should be  more tailored 
                            for the shopping list since this is the data that the list will be 
                            generated from. 
        min_period_weeks:   Minimum period in weeks to wait before having this recipe again. 
        enabled:            Whether this recipe should be included in the shopping list generation. # TODO - should probably have this in web UI. User can enable/disable recipe. And also set the min period. 
        instructions:       Optional list of instructions for the recipe. If recipe.md is not 
                            present, these instructions will be used when rendering the recipe.
    """

    name: str
    servings: int
    meal: MealType
    category: CategoryType
    ingredients: List[RecipeIngredient]
    min_period_weeks: int = 4 
    enabled: bool = True
    instructions: Optional[List[str]] = None

    @field_validator("meal", mode="before")
    @classmethod
    def normalise_meal(cls, v):
        return v.upper() if isinstance(v, str) else v

    @field_validator("category", mode="before")
    @classmethod
    def normalise_category(cls, v):
        return v.upper() if isinstance(v, str) else v

    @classmethod
    def from_yaml(cls, path: str) -> "RecipeData":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)