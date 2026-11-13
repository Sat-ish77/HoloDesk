from agents.desktop_grounding_agent import (
    DesktopGroundingAgent,
    DesktopActionExecutor,
    DesktopActionPlanner,
    GroundingSafetyPolicy,
)
from agents.orchestrator import OrchestratorAgent
from agents.task_agent import TaskAgent
from agents.wake_word_agent import WakeWordConfig
from vision.ui_parser import OmniParserServerAdapter, OpenAIVisionUIParser
from vision.ui_parser import UIElement


class DummyParser:
    parser_name = "dummy"

    def parse(self, screenshot_path):
        class _Result:
            def __init__(self):
                self.success = True
                self.blockers = []
                self.elements = []

            def to_dict(self):
                return {
                    "success": self.success,
                    "parser_name": "dummy",
                    "elements": [],
                    "blockers": [],
                }

        return _Result()


def test_policy_blocks_banking_login():
    policy = GroundingSafetyPolicy()
    safe, reason, needs_confirm = policy.classify("login to my bank and transfer money")
    assert safe is False
    assert "Blocked by safety policy" in reason
    assert needs_confirm is False


def test_planner_open_site_in_browser():
    planner = DesktopActionPlanner()
    plan = planner.build_plan("open github in chrome")
    assert plan.safe is True
    assert len(plan.steps) == 2
    assert plan.steps[0].action == "open_application"
    assert plan.steps[1].action == "open_website"


def test_planner_send_email_requires_confirmation():
    planner = DesktopActionPlanner()
    plan = planner.build_plan("send email to Alice about project update")
    assert plan.steps
    assert all(step.requires_confirmation for step in plan.steps)


def test_planner_outlook_search_cleans_query():
    planner = DesktopActionPlanner()
    plan = planner.build_plan("search Alice in Outlook")
    assert [step.action for step in plan.steps] == [
        "open_application",
        "click_element_by_label",
        "type_text",
    ]
    assert plan.steps[-1].args["text"] == "Alice"


def test_planner_social_message_drafts_without_send():
    planner = DesktopActionPlanner()
    plan = planner.build_plan(
        "inside facebook search for srijana wagle and tell her that I will call you tomorrow I am busy right now"
    )
    actions = [step.action for step in plan.steps]
    assert actions[:4] == ["open_website", "wait", "click_element_by_label", "type_text"]
    assert "verify_draft" in actions
    assert all(step.action != "press_key" or step.args["key"] == "enter" for step in plan.steps)
    assert not any(step.requires_confirmation for step in plan.steps)


def test_planner_gmail_search_and_draft_workflow():
    planner = DesktopActionPlanner()
    plan = planner.build_plan("open gmail and search for Satish Wagle and draft an email saying I will be late")
    actions = [step.action for step in plan.steps]
    assert actions[0] == "open_website"
    assert "click_element_by_label" in actions
    assert "verify_draft" in actions
    assert any(step.args.get("text") == "Satish Wagle" for step in plan.steps)
    assert any(step.args.get("text") == "I will be late" for step in plan.steps)


def test_grounding_agent_plan_flags_confirmation():
    agent = DesktopGroundingAgent()
    plan = agent.plan("send email to Alice")
    assert plan["requires_confirmation"] is True


def test_orchestrator_routes_click_to_grounding():
    orchestrator = OrchestratorAgent(agents={})
    intents = orchestrator._detect_intents("click Compose")
    assert intents[0][0] == "task_agent"
    assert intents[0][1] == "grounded_desktop"


def test_orchestrator_routes_inside_browser_phrase():
    orchestrator = OrchestratorAgent(agents={})
    intents = orchestrator._detect_intents("open facebook inside chrome")
    assert intents[0] == (
        "task_agent",
        "open_web_in_browser",
        {"target": "facebook", "browser": "chrome", "raw": "open facebook inside chrome"},
    )


def test_orchestrator_routes_shutdown_even_with_polite_exit_words():
    orchestrator = OrchestratorAgent(agents={})
    intents = orchestrator._detect_intents("thanks, okay shut down my laptop")
    assert ("task_agent", "shutdown", {"raw": "thanks, okay shut down my laptop"}) in intents


def test_orchestrator_routes_reminders():
    orchestrator = OrchestratorAgent(agents={})
    intents = orchestrator._detect_intents("remind me to submit the project tomorrow at 9 AM")
    assert intents[0][0] == "reminder_agent"
    assert intents[0][1] == "set_reminder"


def test_orchestrator_routes_message_draft_not_raw_typing():
    orchestrator = OrchestratorAgent(agents={})
    intents = orchestrator._detect_intents("draft a message on messenger saying I will be late")
    assert ("task_agent", "draft_message", {"raw": "draft a message on messenger saying I will be late"}) in intents
    assert all(intent[1] != "type_text" for intent in intents)


def test_orchestrator_routes_social_control_to_grounding():
    orchestrator = OrchestratorAgent(agents={})
    intents = orchestrator._detect_intents("inside facebook search for srijana wagle and tell her hello")
    assert intents[0][0] == "task_agent"
    assert intents[0][1] == "grounded_desktop"


def test_omniparser_server_response_normalization():
    payload = {
        "parsed_content_list": [
            {"text": "Messages", "box": [10, 20, 110, 60], "score": 0.9, "class": "button"}
        ]
    }
    elements = OmniParserServerAdapter._elements_from_response(payload)
    assert elements[0].label == "Messages"
    assert elements[0].bbox == {"x": 10, "y": 20, "width": 100, "height": 40}


def test_openai_vision_parser_json_normalization():
    elements = OpenAIVisionUIParser._elements_from_json(
        {"elements": [{"label": "Sign in", "bbox": {"x": 5, "y": 6, "width": 70, "height": 20}}]},
        1280,
        720,
    )
    assert elements[0].label == "Sign in"
    assert elements[0].bbox["width"] == 70


def test_orchestrator_routes_overlay_close_before_app_close():
    orchestrator = OrchestratorAgent(agents={})
    intents = orchestrator._detect_intents("close the star panel please")
    assert intents[0][0] == "overlay_agent"
    assert intents[0][1] == "close_overlay"
    assert all(intent[1] != "close_app" for intent in intents)


def test_orchestrator_routes_verify_screen_to_grounding():
    orchestrator = OrchestratorAgent(agents={})
    intents = orchestrator._detect_intents("verify current screen")
    assert intents[0][0] == "desktop_grounding_agent"
    assert intents[0][1] == "verify_screen"


def test_orchestrator_routes_parser_test():
    orchestrator = OrchestratorAgent(agents={})
    intents = orchestrator._detect_intents("test UI parser")
    assert intents[0][0] == "desktop_grounding_agent"
    assert intents[0][1] == "test_parser"


def test_orchestrator_routes_close_site_in_browser_to_tab_close():
    orchestrator = OrchestratorAgent(agents={})
    intents = orchestrator._detect_intents("close facebook in chrome")
    assert intents[0] == (
        "task_agent",
        "close_browser_tab",
        {"target": "facebook", "browser": "chrome", "raw": "close facebook in chrome"},
    )


def test_task_close_app_requires_confirmation():
    agent = TaskAgent()
    result = agent.execute("close_app", {"app_name": "chrome", "raw": "close chrome"})
    assert result["success"] is True
    assert "Say yes" in result["response"]
    assert agent._pending_confirm is not None


def test_task_misheard_facebooking_clarifies_instead_of_closing_chrome():
    agent = TaskAgent()
    result = agent.execute("close_app", {"app_name": "facebooking in chrome", "raw": "close facebooking in chrome"})
    assert result["success"] is True
    assert "Did you mean close the current Facebook tab" in result["response"]
    assert agent._pending_confirm is not None


def test_nepali_romanized_command_normalizes_to_existing_intent():
    orchestrator = OrchestratorAgent(agents={})
    normalized = orchestrator.normalizer.normalize("facebook khola")
    assert normalized.text == "open facebook"
    intents = orchestrator._detect_intents(normalized.text)
    assert ("task_agent", "open_web", {"target": "facebook", "raw": "open facebook"}) in intents


def test_wake_word_default_phrase_is_hey_holo(monkeypatch):
    monkeypatch.delenv("HOLODESK_WAKE_WORD_PHRASE", raising=False)
    cfg = WakeWordConfig.from_env()
    assert cfg.phrase == "hey holo"


def test_executor_dry_run_noop_is_safe_stop(tmp_path):
    planner = DesktopActionPlanner()
    plan = planner.build_plan("do something unsupported")
    executor = DesktopActionExecutor(parser=DummyParser())
    result = executor.execute_plan(plan, dry_run=True, screenshot_dir=str(tmp_path))
    assert result["success"] is False
    assert "No supported grounded action" in (result["stopped_reason"] or "")


def test_executor_spatial_targeting_first_second_profile():
    elements = [
        UIElement("Dipendra profile", "button", {"x": 10, "y": 10, "width": 100, "height": 40}, 0.7),
        UIElement("Satish profile", "button", {"x": 10, "y": 80, "width": 100, "height": 40}, 0.9),
    ]
    assert DesktopActionExecutor._choose_element(elements, "first profile").label == "Dipendra profile"
    assert DesktopActionExecutor._choose_element(elements, "second profile").label == "Satish profile"


def test_executor_spatial_targeting_top_right():
    elements = [
        UIElement("Bottom Left", "button", {"x": 10, "y": 400, "width": 100, "height": 40}, 0.9),
        UIElement("Top Right", "button", {"x": 700, "y": 20, "width": 100, "height": 40}, 0.6),
        UIElement("Top Left", "button", {"x": 10, "y": 20, "width": 100, "height": 40}, 0.8),
    ]
    assert DesktopActionExecutor._choose_element(elements, "top right").label == "Top Right"
