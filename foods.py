"""DESCRIPTION: Contains the list of all supported foods, and their definitions."""

from recipe_lib import Food, FoodType
from pprint import pprint
from typing import Union

# List of recognized foods
foods = [
    # Meat
    Food("chicken breast", FoodType.Meat),
    Food("pork sausage", FoodType.Meat),
    Food("minced clams", FoodType.Meat),
    Food(["salmon fillet", "salmon"], FoodType.Meat),
    
    # Dairy
    Food("sour cream", FoodType.Dairy),
    Food("butter", FoodType.Dairy),
    Food("milk", FoodType.Dairy),
    Food(["cream", "heavy cream"], FoodType.Dairy),
    Food("half and half", FoodType.Dairy), # TODO difference between cream? light cream?
    Food("greek yogurt", FoodType.Dairy),
    Food("cream cheese", FoodType.Dairy),
    Food("shredded mozzarella", FoodType.Dairy),
    Food("shredded cheese", FoodType.Dairy),
    Food("pepper jack cheese", FoodType.Dairy),
    
    # Vegetables
    Food("red pepper", FoodType.Vegetable),
    Food("green pepper", FoodType.Vegetable),
    Food("green onion", FoodType.Vegetable),
    Food("poblano pepper", FoodType.Vegetable),
    Food(["roma tomato", "roma tomatoes"], FoodType.Vegetable),
    Food(["white onion", "onion"], FoodType.Vegetable),
    Food("yellow onion", FoodType.Vegetable),
    Food(["red onion", "red onions"], FoodType.Vegetable),
    Food("cilantro", FoodType.Vegetable),
    Food("cucumber", FoodType.Vegetable),
    Food("yellow potatoes", FoodType.Vegetable),
    Food("jalepeno", FoodType.Vegetable),
    
    # Fruits
    Food(["lime", "limes"], FoodType.Fruit),
    Food(["lemon", "lemons"], FoodType.Fruit),
    
    # Spices
    Food("cajun seasoning", FoodType.Spice, likely_to_have=True),
    Food("chili powder", FoodType.Spice, likely_to_have=True),
    Food("garlic powder", FoodType.Spice, likely_to_have=True),
    Food("salt", FoodType.Spice, likely_to_have=True),
    Food("thyme", FoodType.Spice, likely_to_have=True),
    Food("pepper", FoodType.Spice, likely_to_have=True),
    Food("italian seasoning", FoodType.Spice, likely_to_have=True),
    Food("rosemary", FoodType.Spice, likely_to_have=True),

    # Other
    Food("honey", FoodType.Other, likely_to_have=True),
    Food(["egg", "eggs"], FoodType.Other),
    Food("veggie stock concentrate", FoodType.Other),
    Food("black beans", FoodType.Other),
    Food("tortillas", FoodType.Other),
    Food("minced garlic", FoodType.Other, likely_to_have=True),
    Food("bread crumbs", FoodType.Other),
    Food("yeast", FoodType.Other),
    Food("flour", FoodType.Other, unit='cup', min_amount=2), # TODO - baking
    Food("baking powder", FoodType.Other), # TODO - baking
    Food("tomato paste", FoodType.Other),
    Food("gnocchi", FoodType.Other),
    Food("chicken bouillon", FoodType.Other, likely_to_have=True),
    Food(["linguine pasta", "flat pasta"], FoodType.Other),
    Food(["corkscrew pasta", "cavatappi pasta"], FoodType.Other),
    Food(["cornstarch"], FoodType.Other, likely_to_have=True)
]

def get_food(name: str) -> Union[Food, None]:
    """Return the Food object if the provided name matches one of it's names."""
    for food in foods:
        if food.has_name(name):
            return food
    return None