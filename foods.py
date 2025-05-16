from recipe_lib import Food, FoodType
from pprint import pprint

# List of recognized foods
foods = [
    # Meat
    Food("chicken breast", FoodType.Meat),
    
    # Dairy
    Food("butter", FoodType.Dairy),
    Food(["cream", "heavy cream"], FoodType.Dairy),
    
    # Vegetables
    Food("red pepper", FoodType.Vegetable),
    Food("green pepper", FoodType.Vegetable),
    
    # Fruits
    Food(["lime", "limes"], FoodType.Fruit),
    
    # Spices
    Food("cajun seasoning", FoodType.Spice, likely_to_have=True),
    Food("chili powder", FoodType.Spice, likely_to_have=True),
    Food("garlic powder", FoodType.Spice, likely_to_have=True),
    
    # Other
    Food("honey", FoodType.Other, likely_to_have=True),
    Food(["egg", "eggs"], FoodType.Other),
]

def get_food(name):
    for food in foods:
        if food.has_name(name):
            return food
    return None