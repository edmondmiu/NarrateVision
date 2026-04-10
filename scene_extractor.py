"""
Scene extractor: turns transcript text into image generation prompts.

V1 uses keyword extraction (no LLM needed, instant).
Future: LM Studio API for richer scene descriptions.
"""

import re

# Visual keywords that signal a scene worth illustrating
SCENE_TRIGGERS = {
    "settings": [
        "forest", "castle", "mountain", "ocean", "sea", "river", "lake",
        "village", "city", "cave", "desert", "garden", "house", "room",
        "sky", "field", "road", "bridge", "tower", "palace", "church",
        "school", "market", "beach", "island", "valley", "hill", "cliff",
        "dungeon", "temple", "library", "kitchen", "bedroom", "street",
    ],
    "characters": [
        "king", "queen", "prince", "princess", "knight", "dragon",
        "witch", "wizard", "fairy", "giant", "monster", "wolf", "bear",
        "fox", "rabbit", "cat", "dog", "bird", "horse", "lion", "tiger",
        "child", "boy", "girl", "man", "woman", "old man", "old woman",
        "soldier", "pirate", "thief", "angel", "demon", "ghost",
    ],
    "actions": [
        "running", "flying", "swimming", "fighting", "sleeping",
        "walking", "dancing", "singing", "crying", "laughing",
        "riding", "climbing", "falling", "hiding", "searching",
        "eating", "drinking", "reading", "writing", "building",
    ],
    "atmosphere": [
        "dark", "bright", "stormy", "sunny", "rainy", "snowy",
        "foggy", "moonlit", "starry", "golden", "shadowy", "misty",
        "cold", "warm", "magical", "mysterious", "peaceful", "scary",
    ],
}

# Flatten for quick lookup
ALL_KEYWORDS = set()
for category in SCENE_TRIGGERS.values():
    ALL_KEYWORDS.update(category)

STYLE_PREFIX = "storybook illustration, watercolor style, detailed, warm lighting"


def extract_scene(transcript_chunk: str) -> str | None:
    """
    Extract a scene description from a transcript chunk.
    Returns an image prompt string, or None if the chunk has no visual content.
    """
    text = transcript_chunk.lower().strip()
    if not text:
        return None

    found = {
        "settings": [],
        "characters": [],
        "actions": [],
        "atmosphere": [],
    }

    for category, keywords in SCENE_TRIGGERS.items():
        for kw in keywords:
            if kw in text:
                found[category].append(kw)

    # Need at least one setting or character to make a scene
    if not found["settings"] and not found["characters"]:
        return None

    # Build prompt from extracted elements
    parts = []

    if found["atmosphere"]:
        parts.append(", ".join(found["atmosphere"]))

    if found["settings"]:
        parts.append(", ".join(found["settings"]))

    if found["characters"]:
        chars = ", ".join(found["characters"])
        if found["actions"]:
            actions = ", ".join(found["actions"])
            parts.append(f"{chars} {actions}")
        else:
            parts.append(chars)

    scene_desc = ", ".join(parts)
    prompt = f"{STYLE_PREFIX}, {scene_desc}"

    return prompt


def extract_scene_from_accumulator(sentences: list[str], last_prompt: str | None = None) -> str | None:
    """
    Given a list of recent sentences, extract the best scene.
    Avoids returning the same prompt twice in a row.
    """
    # Combine recent sentences for context
    combined = " ".join(sentences[-3:])  # last 3 sentences
    prompt = extract_scene(combined)

    if prompt and prompt != last_prompt:
        return prompt

    return None
