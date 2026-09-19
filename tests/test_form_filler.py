import pytest

from browser.form_filler import _value_for, match_key


@pytest.mark.parametrize("label,key", [
    ("First Name", "legal_first_name"),
    ("Last name", "legal_last_name"),
    ("Email Address", "email"),
    ("Phone Number", "phone"),
    ("LinkedIn Profile", "linkedin_url"),
    ("Zip Code", "postal_code"),
    ("Full Name", "_full_name"),
])
def test_common_labels_match(label, key):
    assert match_key(label)[0] == key


@pytest.mark.parametrize("label", ["Company name", "Referrer's name", "Why do you want to work here?", "Hiring manager email", ""])
def test_lookalike_labels_are_left_for_the_user(label):
    assert match_key(label)[0] is None


def test_values_compose_and_booleans_become_yes_no():
    profile = {"legal_first_name": "Test", "legal_last_name": "User", "authorized_to_work_us": False, "gpa": ""}
    assert _value_for("_full_name", profile) == "Test User"
    assert _value_for("authorized_to_work_us", profile) == "No"
    assert _value_for("gpa", profile) is None
