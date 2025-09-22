
import numpy as np
from app import app, db, Recipe


"""
Improvements: 
1. Select based on the dish type (e.g. randomly select entrees. random select salad. random select
   side that complements entree)
2. Have some way to increase/decrease the probability of a specific dish. E.g. a score of how much
   we like a dish that will directly affect how likely it is to be chosen
    - Could just be a number that scales weeks_since_last

"""

# TODO - for some reason this script was not working when in the repo root dir. The db was not
# able to be queried. Should figure that out.

def select_n_recipes(n=3):
    """Randomly select the specified number of recipes. Update the weeks_since_last field after
    selection."""
    recipes = Recipe.query.all()
    selected = [get_random_recipe() for i in range(n)]
    selected_ids = [s.id for s in selected]

    # Update weeks_since_last field
    for recipe in recipes:
        if recipe.id in selected_ids:
            recipe.weeks_since_last = 0
        else:
            recipe.weeks_since_last += 1

    return selected

def get_random_recipe():
    """Select random recipe. Weighted by weeks_since_last field. I.e. recipe will have higher
    likelihood of being chosen if it hasn't been chosen for longer. Will not be chosen if
    weeks_since_last is set to 0."""

    recipes = Recipe.query.all()

    probs = np.array([r.weeks_since_last for r in recipes], dtype=np.float64)
    probs /= np.sum(probs) # Normalize so that sum(probs) == 1

    idx = np.random.choice(len(recipes) , p=probs)
    return recipes[idx]

if __name__ == '__main__':

    with app.app_context():
        db.create_all()
        recipe = get_random_recipe()
        print(recipe)

        

