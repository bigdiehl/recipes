
## Description

This repo (a) recipe data in the 'recipes' directory and (b) contains functionality for generating a shopping list from that recipe data.


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
