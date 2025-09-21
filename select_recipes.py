
import numpy as np

"""


GOAL: Randomly select some recipes for the week. 
- We could just manually put together a list that we step through and repeat. 
But that's kind of boring
- Idea 1: Generate list of recipes. Randomly mix the list. 
    - Has the benefit that we don't do things the same order always
    - Could add reciple multiple times to list, but then it might be scheduled 
      close to each other. Also things could be close when list is repeating
- Better idea would be to determine the desired spacing of a dish, and that 
  influences the probability of it being chosen during a week. 


- Hard constraint - dish cannot be chosen 2 weeks in a row. 
- I suppose the number of dishes is going to make a difference here. Assumes we
  have enough dishes to populate our desired frequencies. But if we have too
  many dishes, then dishes will NOT be served at their desired frequency. There
  will be a backup. Backup just gets bigger forever? Or some sort of equilibrium 
  is found
  
  
- Maybe the attribute to have is "min time between dish". I.e how l



"""