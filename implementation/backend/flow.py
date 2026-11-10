# Everything a person sees in the flow lives here, including the questions, the checkbox and button options, and the sliders.
# Change the wording or add an option in this file and the terminal tool and the API (GET /api/v1/flow) both follow.
# The question text and the Q4 options are placeholders until we have the final copy from Figma.

AI_NOTICE = "This draft was written with AI, using your own words. You decide what gets posted."

HELP_OPTIONS = [
    {"id": "meals", "label": "Meals"},
    {"id": "rides", "label": "Rides"},
    {"id": "gift_cards", "label": "Gift cards"},
    {"id": "prayers", "label": "Prayers"},
    {"id": "visits", "label": "Visits"},
    {"id": "home_help", "label": "Help at home"},
]

UPDATE_OPTIONS = [
    {"id": "daily", "label": "Daily"},
    {"id": "few_times_week", "label": "A few times a week"},
    {"id": "weekly", "label": "Weekly"},
    {"id": "when_news", "label": "When there's news"},
]

REACH_OPTIONS = [
    {"id": "text", "label": "Text me"},
    {"id": "call", "label": "Call me"},
    {"id": "check_page", "label": "Check this page for updates"},
    {"id": "comment", "label": "Leave a comment on the page"},
    {"id": "not_now", "label": "Please don't reach out right now"},
]

QUESTIONS = [
    {
        "id": "what_happened",
        "type": "voice",
        "title": "What happened?",
        "prompt": "Tell your friends and family what's going on, in your own words.",
    },
    {
        "id": "what_next",
        "type": "voice",
        "title": "What happens next?",
        "prompt": "What's coming up, or what are you waiting to find out?",
    },
    {
        "id": "help",
        "type": "checkboxes",
        "title": "How can others help right now?",
        "options": HELP_OPTIONS,
        "other_id": "help_other",
        "other_prompt": "Anything else you'd like people to know? (optional)",
    },
    {
        "id": "staying_in_touch",
        "type": "buttons",
        "title": "Staying in touch",
        "fields": [
            {"id": "update_frequency", "prompt": "How often do you think you'll share updates?", "options": UPDATE_OPTIONS},
            {"id": "reach_out", "prompt": "How would you like people to reach out?", "options": REACH_OPTIONS},
        ],
    },
]

SLIDERS = [
    {"id": "length", "title": "Length", "low": "Shorter", "high": "Longer"},
    {"id": "tone", "title": "Tone", "low": "Just the facts", "high": "Warm"},
    {"id": "wording", "title": "Wording", "low": "Polished", "high": "My own words"},
]

SLIDER_DEFAULT = 3  # the middle of 1 to 5 means "leave it as it is"
