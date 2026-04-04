## TODO 

- Only load recipe if recipe.yaml and recipe.md are present
    - Maybe we can generate something rudimentary from the recipe.yaml?

- Do we plan on doing anything with meal, category?
    - Should we be able to specify multiple meals? I.e. this dish is good for lunch of dinner?

- Should we keep info like 'enabled' or 'min_period_weeks' in recipe.yaml? 

- I would like to rename 'recipe list' to 'saved recipes'
- Add new 'candidate recipes' page. (Or just combine with 'recipes' page?)
- Group recipes. 

- Add input to specify how many people you are shopping for. Scale recipe amounts accordingly
- Add enable/disable and adjustment to min_period_weeks in web UI. Move these quantities to the UI json db.

- Maybe define some custom unit rules for specific foods (e.g. x tbs == 1 stick for butter)

- Would like to format markdown a bit. E.g. make headings more visually distinct.

- Better error handling and logging of those errors
    - E.g. if there is an error loading a recipe, keep going, don't include recipe in UI, and log the error. 
    - I can come and check the error, or go to a custom route. Figure it out from there. 
    ==moraccan_chickpea_and_apricot_tagine== is currently not working. Can test on this. 

Eventually I think I want to have the app running on Frank or similar, and then have the recipes in a shared drive that I can edit from any computer.

- Lookup spice blend and list out the spices needed in shopping list.
- Maybe I should make a whole new section named "Spices" since they are pretty much all "likely to have".

## Description

This repo:
- stores recipe data in the 'recipes' directory 
- contains functionality for generating a shopping list from that recipe data.
- contains tools for sending out the list in an email report
- contains a web interface

## Setup

After cloning the repo, use the `uv sync` to add the necessary python dependencies 

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


TODO
- Still need photo for butternut squash soup



# -----------------------------------------------

TODO
- Log with foods we don't recognize. Need some feedback that we should add a food to foods.yaml
- Testing - testing generating a shopping list from each recipe. 
- Better README
- Workflow for importing recipes
- Config for personal data (app password, default emails to send to, email to send from, etc)
- Starter files for setting up as a service

- Look into hosting this on web so we can access anywhere. 
- Better output of PDFs. should match what we see on the webpage. 
    - Look into using Playwright / Puppeteer

- Method for printing recipes
- Think about mirroring web with physical recipe book. 
    - Maybe we should get rid of meal/category. And just have something like "section". Update
    to match the section we use in our physical recipe book. Can be arbitrary - dinner, dessert, side

At some point, we should refine how we randomly select. I mainly want to get 2-3 entrees for the week, and maybe 2 sides. Should be able to specify how many of each category. Or just keep it random?

- Make weekly email schedule font more similar to the rest on mobile
- Make next schedule sent date use month and day of week names
- send now (test) should work even if no schedule is saved. 
- on recipes page, first selected recipe should automatically be selected for display. Otherwise just the first one in list. Or should remember the last one that was selected (in a cookie?)

## Running

export GMAIL_APP_PASSWORD="<app_pasword>"
export GMAIL_SENDER="<your_email>"
uv run web/app.py