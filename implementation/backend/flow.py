# Everything a person sees in the flow lives here, including the questions, the checkbox options, and the sliders.
# The sliders are only used by the terminal tool now; the web page just has the "tell us what to change" box.
# Change the wording or add an option in this file and the terminal tool and the API (GET /api/v1/flow) both follow.
# The wording comes from the Figma board.

AI_NOTICE = "This draft was written with AI, using your own words. You decide what gets posted."

DEFAULT_TITLE = "Today's Update"

# Meals and money (meal trains, gift cards, fundraising) are left out on purpose.
# CaringBridge has its own plans for how those will be offered.
HELP_OPTIONS = [
    {"id": "rides", "label": "Rides"},
    {"id": "prayers", "label": "Prayers"},
    {"id": "visits", "label": "Visits"},
    {"id": "home_help", "label": "Help at home"},
    {"id": "pet_care", "label": "Pet care"},
]

QUESTIONS = [
    {
        "id": "what_happened",
        "step_label": "What's happened so far",
        "type": "voice",
        "title": "What's happened so far?",
        "prompt": "Catch people up on how you got here, like a diagnosis, a hospital stay, or how the last few days have gone. Type or talk, and we'll help tidy it up.",
    },
    {
        "id": "what_next",
        "step_label": "What's coming up next",
        "type": "voice",
        "title": "What's coming up next?",
        "prompt": "Any upcoming treatments, appointments, or news you're waiting on. If you don't know yet, that's okay. You can skip this.",
    },
    {
        "id": "help",
        "step_label": "How others can help",
        "type": "checkboxes",
        "title": "How Can Others Help Right Now?",
        "prompt": "People want to help. Pick anything that would make this week a little easier. You can change it anytime.",
        "options": HELP_OPTIONS,
    },
]

# Each slider has five positions, and "labels" are the words shown for them.
SLIDERS = [
    {"id": "length", "title": "Length", "low": "Shorter", "high": "Longer",
     "labels": ["Much shorter", "A bit shorter", "As it is", "A bit longer", "Much longer"]},
    {"id": "tone", "title": "Tone", "low": "Just the facts", "high": "Warm",
     "labels": ["Just the facts", "A little plainer", "As it is", "A little warmer", "Warm"]},
    {"id": "wording", "title": "Wording", "low": "Polished", "high": "My own words",
     "labels": ["Polished", "A little more polished", "As it is", "Mostly mine", "My own words"]},
]

SLIDER_DEFAULT = 3  # the middle of 1 to 5 means "leave it as it is"
