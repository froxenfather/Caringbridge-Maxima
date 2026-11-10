# Everything a person sees in the flow lives here, including the questions, the checkbox and button options, and the sliders.
# Change the wording or add an option in this file and the terminal tool and the API (GET /api/v1/flow) both follow.
# The wording comes from the Figma board.

AI_NOTICE = "This draft was written with AI, using your own words. You decide what gets posted."

HELP_OPTIONS = [
    {"id": "meals", "label": "Meals"},
    {"id": "rides", "label": "Rides"},
    {"id": "gift_cards", "label": "Gift cards"},
    {"id": "prayers", "label": "Prayers"},
    {"id": "visits", "label": "Visits"},
    {"id": "home_help", "label": "Help at home"},
    {"id": "pet_care", "label": "Pet care"},
    {"id": "fundraising", "label": "Fundraising"},
]

UPDATE_OPTIONS = [
    {"id": "every_few_days", "label": "Every few days"},
    {"id": "weekly", "label": "About once a week"},
    {"id": "when_news", "label": "When there's news"},
]

REACH_OPTIONS = [
    {"id": "comments", "label": "Comments and Reactions on the page"},
    {"id": "candle", "label": "Light a candle on the page"},
    {"id": "text", "label": "Text me"},
    {"id": "hold_off", "label": "Please hold off"},
]

QUESTIONS = [
    {
        "id": "what_happened",
        "type": "voice",
        "title": "What would you like friends and family to know?",
        "prompt": "Type or talk whatever comes to mind. We'll help you find the words and tidy it up.",
    },
    {
        "id": "what_next",
        "type": "voice",
        "title": "Help others understand what's next?",
        "prompt": "Any treatments, appointments, or news you're waiting on. If you don't know yet, that's okay. You can skip this.",
    },
    {
        "id": "help",
        "type": "checkboxes",
        "title": "How Can Others Help Right Now?",
        "prompt": "People want to help. Pick anything that would make this week a little easier. We'll add it to Ways to Help, and you can change it anytime.",
        "options": HELP_OPTIONS,
        "other_id": "help_other",
        "other_prompt": "Anything else you'd like people to know? (Optional)",
    },
    {
        "id": "staying_in_touch",
        "type": "buttons",
        "title": "Staying in Touch",
        "fields": [
            {"id": "update_frequency", "prompt": "How often do you think you'll share updates?", "options": UPDATE_OPTIONS, "multiple": False},
            {"id": "reach_out", "prompt": "How would you like people to reach out?", "options": REACH_OPTIONS, "multiple": True},
        ],
        "note": "You'll choose who can see your page in Step 4.",
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
