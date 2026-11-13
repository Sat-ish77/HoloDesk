from agents.production_control import ProductionControlAgent


def test_romanized_nepali_open_facebook_routes_to_open_web():
    route = ProductionControlAgent().route("facebook khola")
    assert route.canonical.language == "ne"
    assert route.normalized_text == "open facebook"
    assert route.intents[0][0:2] == ("task_agent", "open_web")
    assert route.intents[0][2]["target"] == "facebook"


def test_nepali_gmail_draft_becomes_grounded_workflow():
    route = ProductionControlAgent().route(
        "gmail ma Satish Wagle bhanne manxe khoja ta teslai malai aauna dhilo hunxa bhanera mail draft gara ta"
    )
    assert route.canonical.intent == "draft_email"
    assert route.canonical.recipient_name == "Satish Wagle"
    assert route.canonical.message_body == "I will be late"
    assert route.intents[0][0:2] == ("task_agent", "grounded_desktop")
    assert "Satish Wagle" in route.normalized_text
    assert "I will be late" in route.normalized_text
    assert route.workflow[-1].action == "ask_confirmation"


def test_nepali_tictactoe_spatial_cell_routes_to_overlay_move():
    route = ProductionControlAgent().route("first row ko second box ma lagau")
    assert route.canonical.intent == "game_move"
    assert route.canonical.target == "top center"
    assert route.intents[0][0:2] == ("overlay_agent", "place_tictactoe")
    assert route.intents[0][2]["cell"] == "top center"


def test_first_profile_routes_to_grounded_click():
    route = ProductionControlAgent().route("click the first profile")
    assert route.canonical.intent == "click_ui"
    assert route.intents[0][0:2] == ("task_agent", "grounded_desktop")
    assert route.canonical.spatial_reference == "first"
