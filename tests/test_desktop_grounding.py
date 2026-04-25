from agents.desktop_grounding_agent import (
    DesktopActionExecutor,
    DesktopActionPlanner,
    GroundingSafetyPolicy,
)


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


def test_executor_dry_run_noop_is_safe_stop(tmp_path):
    planner = DesktopActionPlanner()
    plan = planner.build_plan("do something unsupported")
    executor = DesktopActionExecutor(parser=DummyParser())
    result = executor.execute_plan(plan, dry_run=True, screenshot_dir=str(tmp_path))
    assert result["success"] is False
    assert "No supported grounded action" in (result["stopped_reason"] or "")
