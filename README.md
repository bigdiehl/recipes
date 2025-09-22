
## Description

This repo:
- stores recipe data in the 'recipes' directory 
- contains functionality for generating a shopping list from that recipe data.
- contains tools for sending out the list in an email report

## Setup



## Recipes

All recipes are stored in the `recipes` directory. Each recipe is composed of 3 files:
1. `shopping_list.csv` - The name and quantity of ingredients to get.
    - The ingredient names must match a name in `foods.py`. 
    - The `quantity` field can either be a number, a number and a unit, or `-` for unspecified. 
    - If specifying a quantity doesn't make sense, just put `-` in that field. (e.g. a recipe needs x amount of sour cream, but sour cream is bought by the tub. Putting `-` will effectively result in the shopping list just saying "sour cream")
2. `metadata.yaml` - High level attributes for the recipe. 
    - servings: int. 
    - category: [entree, salad, dessert side]
    - meal: [breakfast, lunch, dinner]
    - enabled [true, false]
    - min_period_weeks: int. Minimum number of weeks to wait before putting this recipe back into the pool of selection candidates.
3. `recipe.md` - The human-readable recipe. Not used in generating shopping list.


### Adding a New Recipe

1. cd into the `recipes` directory
2. Run `./new_recipe_template.py <recipe_name>`. This will generate a directory with the given `<recipe_name>` and copy over the starter files in `recipe_starter_files`



## TODO
Handle foods
    - Without any quantity at all (tortillas)
        - What if multiple recipes call for this? Make sure you get enough for both. 
    - With custom quantities (1 tub yougurt, 1 bunch cilantro)
    - Mix and match between these
        - What if list A calls for '1 bunch cilantro` and list B just calls for 'cilantro' (because it just needs a bit). How to summarize this on the shopping list?

Sometimes it just doesn't make sense to put exact quantities in the shopping list. It makes more sense to put in the term that applies to what you would get off the shelf

Metadata
- 'meal' can include multiple meals

Recipes
- gnocchi_bake needs revision. Doesn't have any quantity info on half the ingredients. Disabled for now. 
- Same for firehous_mac_n_cheese


#### Next Steps

1. Input more recipes
2. Add ability in web interface to view combined shopping list
    - Will need to load in recipe data in app.py at startup
    - Add button to email out shopping list
    - Add info display showing when the next shopping list will be sent out. (should detect cron job and when it will run)
3. Need to figure out cron job for automatically sending out recipe list
    - When run, it will take selection (making one if needed), generate shopping list, and email it out.
    - It will randomly select for next week. Update the "selected" field of the db
    - It will update the db field saying when the recipe was last chosen. 
        - Need to figure out what units that will be in. 