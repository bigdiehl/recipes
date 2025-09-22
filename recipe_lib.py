"""DESCRIPTION: Contains various supported classes/enums"""


from dataclasses import dataclass
from enum import Enum, auto
import yaml
from typing import Optional, List, Union
from pint import Unit, UnitRegistry
from pint.facets.plain import PlainQuantity as Quantity

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
    
@dataclass
class Food:
    """
    Elements:
        - names: all names that the food may be referred to as. First will be used in shopping list. 
        - unit: Preferred unit for shopping lists
        - min_amount: Minimal amount that should trigger inclusion in a shopping list. Measured in 'unit' units. E.g. 1 tsp flour is not enough to trigger
    """
    names: Union[str, List[str]]
    category: FoodType
    unit: Optional[str] = None
    min_amount: Optional[float] = None 
    likely_to_have: bool = False
    
    def __post_init__(self):
        if isinstance(self.names, str):
            self.names = [self.names]
        elif not isinstance(self.names, list):
            raise ValueError("names must be str or List[str]")
    
    def has_name(self, name: str) -> bool:
        """Returns true if the name matches one of the food names"""
        name = name.lower()
        if name in self.names:
            return True
        return False
    
    def get_name(self) -> str:
        """Return the primary name for the food"""
        return self.names[0]

@dataclass
class Ingredient:
    food: Food
    quantity: Union[float, Quantity]
    has_units: bool = False
    
    def __post_init__(self):
        if isinstance(self.quantity, Quantity):
            self.has_units = True
        elif not isinstance(self.quantity, (int, float)):
            raise ValueError(f"invalid type for quantity: {type(self.quantity)}")
        
    def __add__(self, other: 'Ingredient'):
        if self.food != other.food:
            raise ValueError("Cannot merge ingredients with different foods.")
        
        if self.has_units != other.has_units:
            raise ValueError("Mismatch in has_units when merging ingredients")
        
        return Ingredient(
            food=self.food,
            quantity=(self.quantity + other.quantity),
            has_units=self.has_units
        )
        
    def __repr__(self):
        return f"Ingredient(food={self.food.get_name()}, quantity={str(self.quantity)})"
        
    def to_preferred_unit(self):
        if self.food.unit is not None and self.has_units:
            self.quantity = self.quantity.to(self.food.unit)
            

@dataclass
class RecipeMetaData:
    servings: int
    category: CategoryType
    meal: MealType
    # Affinity? Min period?
    
    def __post_init__(self):
        """To support init via a dictionary from YAML file"""
        if isinstance(self.category, str):
            self.category = CategoryType(self.category.upper())
        if isinstance(self.meal, str):
            self.meal = MealType(self.meal.upper())
            
    
@dataclass
class Recipe:
    ingredients : List[Ingredient]
    instructions : str
    metadata: dict

class RecipeParser:
    def __init__(self, recipe_path : str):
        
        with open(recipe_path) as f:
            recipe = yaml.safe_load(f)

        name = recipe['name']
        ingredients = recipe['ingredients']
        steps = recipe['instructions']
        servings = recipe['servings']

        # parse ingredients
