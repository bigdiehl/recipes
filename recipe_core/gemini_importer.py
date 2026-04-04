#!/usr/bin/env python3
"""
DESCRIPTION: Extract recipe data from URLs or text using Google Gemini API.
"""

import logging
import os
import re
import requests
from dataclasses import dataclass
from typing import Optional

from google import genai
from google.genai import types
import yaml

from recipe_core.recipe_lib import RecipeData

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"

@dataclass
class ImportResult:
    """Result of recipe extraction."""
    recipe_data: RecipeData
    markdown: str
    slug: str
    source: str

def _fetch_url(url: str) -> str:
    """Fetch content from a URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error("Failed to fetch URL %s: %s", url, e)
        raise ValueError(f"Failed to fetch URL: {e}")

def _generate_slug(name: str) -> str:
    """Generate a slug from a recipe name."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    slug = slug.strip('_')
    return slug

def extract_recipe(url: Optional[str] = None, text: Optional[str] = None, api_key: Optional[str] = None) -> ImportResult:
    """
    Extract recipe data from a URL or text using Gemini API.

    Args:
        url: URL to extract recipe from (optional)
        text: Text containing recipe (optional)
        api_key: Gemini API key (defaults to GEMINI_API_KEY env var)

    Returns:
        ImportResult with recipe data, markdown, slug, and source
    """
    if not url and not text:
        raise ValueError("Must provide either url or text")

    # Get API key
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    # Create Gemini client
    client = genai.Client(api_key=api_key)

    # Get recipe content
    if url:
        source = url
        content = _fetch_url(url)
    else:
        source = "pasted text"
        content = text

    # Create extraction prompt
    prompt = f"""Extract recipe information from the following content and return ONLY valid YAML and Markdown.

Your response must be in this EXACT format with no other text:

---YAML---
name: Recipe Name
servings: 4
meal: DINNER
category: ENTREE
min_period_weeks: 4
enabled: true
ingredients:
  - food: ingredient 1
    quantity: 1 cup
  - food: ingredient 2
    quantity: 2 tbsp
---MARKDOWN---
# Recipe Name

## Ingredients
- 1 cup ingredient 1
- 2 tbsp ingredient 2

## Instructions
1. Step 1
2. Step 2

## Notes
Optional notes here

IMPORTANT RULES:
- meal must be one of: BREAKFAST, LUNCH, DINNER
- category must be one of: ENTREE, SALAD, DESSERT, SIDE
- ingredients must use simple food names (e.g., "chicken breast", "onion", "olive oil")
- quantities should use standard units (cup, tbsp, tsp, oz, lb, gram, etc.)
- If no quantity is specified, omit the quantity field for that ingredient
- Return ONLY the YAML and Markdown sections, nothing else

Content to extract:

{content[:10000]}"""

    # Call Gemini
    try:
        # Try the simpler API call format
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        # Extract text from response
        if hasattr(response, 'text'):
            result = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            result = response.candidates[0].content.parts[0].text
        else:
            raise ValueError("Unable to extract text from response")

    except Exception as e:
        logger.error("Gemini API call failed: %s", e)
        # Try to list available models for debugging
        try:
            logger.info("Attempting to list available models...")
            for model in client.models.list():
                logger.info("Available model: %s", model.name)
        except Exception as list_error:
            logger.error("Could not list models: %s", list_error)
        raise ValueError(f"Failed to extract recipe: {e}")

    # Parse response
    try:
        yaml_match = re.search(r'---YAML---(.*?)---MARKDOWN---', result, re.DOTALL)
        markdown_match = re.search(r'---MARKDOWN---(.*)', result, re.DOTALL)

        if not yaml_match or not markdown_match:
            raise ValueError("Response format invalid - missing YAML or MARKDOWN sections")

        yaml_text = yaml_match.group(1).strip()
        markdown_text = markdown_match.group(1).strip()

        # Parse YAML
        recipe_dict = yaml.safe_load(yaml_text)
        recipe_data = RecipeData(**recipe_dict)

        # Generate slug
        slug = _generate_slug(recipe_data.name)

        return ImportResult(
            recipe_data=recipe_data,
            markdown=markdown_text,
            slug=slug,
            source=source
        )

    except Exception as e:
        logger.error("Failed to parse Gemini response: %s", e)
        logger.debug("Response was: %s", result)
        raise ValueError(f"Failed to parse recipe data: {e}")
