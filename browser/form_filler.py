"""Fill a job application form from the ElevateU ATS profile.

Only confident label matches are filled; everything else is reported back so
the Brain can ask the user. Password fields are never touched, and nothing
here submits the form (submission goes through the confirmation gate).
"""

from __future__ import annotations

import os
from typing import Any

from rapidfuzz import fuzz, process
from rapidfuzz.utils import default_process

# ATS profile key -> labels that mean it. "_full_name" is composed from first + last.
ALIASES: dict[str, tuple[str, ...]] = {
    "_full_name": ("full name", "name", "your name", "legal name"),
    "legal_first_name": ("first name", "given name", "legal first name"),
    "legal_last_name": ("last name", "family name", "surname", "legal last name"),
    "preferred_name": ("preferred name", "preferred first name", "nickname"),
    "email": ("email", "email address", "e-mail"),
    "phone": ("phone", "phone number", "mobile", "mobile phone", "telephone", "cell phone"),
    "address_line1": ("address", "street address", "address line 1"),
    "address_line2": ("address line 2", "apartment", "suite"),
    "city": ("city",),
    "state": ("state", "province", "state/province"),
    "postal_code": ("zip", "zip code", "postal code", "postcode"),
    "country": ("country",),
    "linkedin_url": ("linkedin", "linkedin profile", "linkedin url"),
    "github_url": ("github", "github url", "github profile"),
    "portfolio_url": ("portfolio", "website", "personal website", "portfolio url"),
    "school_name": ("school", "university", "college", "school name"),
    "degree_type": ("degree", "degree type"),
    "field_of_study": ("major", "field of study", "discipline"),
    "gpa": ("gpa",),
    "authorized_to_work_us": ("authorized to work", "legally authorized to work in the united states", "work authorization"),
    "requires_sponsorship_now": ("require sponsorship", "visa sponsorship", "require visa sponsorship now"),
    "requires_sponsorship_future": ("require sponsorship in the future", "future sponsorship"),
    "visa_status": ("visa status", "current visa"),
    "salary_expectation": ("salary expectation", "desired salary", "expected salary", "compensation expectations"),
    "notice_period": ("notice period", "earliest start date", "start date"),
    "how_did_you_hear": ("how did you hear about us", "how did you hear", "referral source"),
    "willing_to_relocate": ("willing to relocate", "open to relocation"),
}
_PHRASES = [(key, alias) for key, aliases in ALIASES.items() for alias in aliases]
MIN_SCORE = 88

# Tags every fillable visible field with data-holodesk-field and returns its label.
_SCAN_JS = r"""
() => {
  const out = [];
  let i = 0;
  for (const el of document.querySelectorAll('input, textarea, select')) {
    const type = (el.getAttribute('type') || el.tagName).toLowerCase();
    if (['hidden', 'password', 'submit', 'button', 'image', 'reset', 'checkbox', 'radio'].includes(type)) continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const label = (el.labels && el.labels[0] && el.labels[0].innerText) || el.getAttribute('aria-label') ||
      el.getAttribute('placeholder') || el.getAttribute('name') || el.id || '';
    el.setAttribute('data-holodesk-field', String(i));
    const options = el.tagName === 'SELECT' ? Array.from(el.options).map(o => o.text.trim()).filter(Boolean) : [];
    out.push({i, type, label: label.replace(/\*/g, '').replace(/\s+/g, ' ').trim().slice(0, 120), options, empty: !el.value});
    i++;
  }
  return out;
}
"""


def match_key(label: str) -> tuple[str | None, int]:
    """Best ATS profile key for a form label, or None below MIN_SCORE.

    Whole-label similarity, not substring: "Company name" must not match "name".
    """
    if not label.strip():
        return None, 0
    best = process.extractOne(label, [p[1] for p in _PHRASES], scorer=fuzz.ratio, processor=default_process)
    if not best or best[1] < MIN_SCORE:
        return None, int(best[1]) if best else 0
    return _PHRASES[best[2]][0], int(best[1])


def _value_for(key: str, profile: dict) -> str | None:
    if key == "_full_name":
        parts = [profile.get("legal_first_name"), profile.get("legal_last_name")]
        return " ".join(p for p in parts if p) or None
    value = profile.get(key)
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def fill_application(page, profile: dict) -> dict[str, Any]:
    try:
        fields = page.evaluate(_SCAN_JS)
    except Exception as exc:
        return {"success": False, "response": f"Couldn't read the form: {exc}"}

    filled, unfilled = [], []
    resume = os.getenv("HOLODESK_RESUME_PATH", "").strip()
    for field in fields:
        label = field["label"]
        loc = page.locator(f'[data-holodesk-field="{field["i"]}"]')
        try:
            if field["type"] == "file":
                if resume and os.path.isfile(resume) and any(w in label.lower() for w in ("resume", "cv")):
                    loc.set_input_files(resume)
                    filled.append({"label": label, "value": os.path.basename(resume)})
                else:
                    unfilled.append(label or "file upload")
                continue
            if not field["empty"]:
                continue  # never overwrite what the page or the user already entered
            key, _ = match_key(label)
            value = _value_for(key, profile) if key else None
            if value is None:
                unfilled.append(label or f"unlabeled {field['type']}")
                continue
            if field["options"]:
                choice = process.extractOne(value, field["options"], scorer=fuzz.WRatio, processor=default_process)
                if not choice or choice[1] < 80:
                    unfilled.append(label)
                    continue
                loc.select_option(label=choice[0])
                value = choice[0]
            else:
                loc.fill(value)
            filled.append({"label": label, "value": value})
        except Exception:
            unfilled.append(label or field["type"])

    spoken = "; ".join(f"{f['label']}: {f['value']}" for f in filled) or "nothing"
    missing = ", ".join(unfilled) or "none"
    return {
        "success": True,
        "response": f"Filled {len(filled)} fields ({spoken}). Still empty: {missing}.",
        "filled": filled,
        "unfilled": unfilled,
    }
