"""
Page map: what is on screen in the current tab, as elements the model can act on.

A script walks the DOM (open shadow roots included), keeps the interactive
elements that are visible in the viewport, and tags each with data-holo-ref.
Acting by ref is then a plain locator, and a navigation wipes the tags, so a
stale ref fails instead of clicking something else.

Elements are grouped by dialog, post (article) or landmark. The post nearest
the centre of the viewport is marked on screen: that is "this post".

No site-specific selectors live here. Password values are never read.
"""

from __future__ import annotations

# Shared helpers, prepended to both scripts below.
_HELPERS = r"""
const clean = s => (s || '').replace(/\s+/g, ' ').trim();
const up = n => n.parentElement || (n.getRootNode && n.getRootNode().host) || null;
const closestDeep = (el, sel) => { for (let n = el; n; n = up(n)) if (n.matches && n.matches(sel)) return n; return null; };
const roleOf = el => {
  const r = el.getAttribute('role'); if (r) return r;
  const t = el.tagName;
  if (t === 'A') return 'link';
  if (t === 'BUTTON' || t === 'SUMMARY') return 'button';
  if (t === 'SELECT') return 'combobox';
  if (t === 'TEXTAREA') return 'textbox';
  if (t === 'INPUT') {
    const ty = (el.type || 'text').toLowerCase();
    if (ty === 'password') return 'password';
    if (ty === 'checkbox' || ty === 'radio') return ty;
    if (ty === 'submit' || ty === 'button' || ty === 'reset' || ty === 'image') return 'button';
    if (ty === 'search') return 'searchbox';
    return 'textbox';
  }
  if (el.isContentEditable) return 'textbox';
  return 'clickable';
};
const isField = el => ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.isContentEditable;
const nameOf = el => {
  let n = el.getAttribute('aria-label');
  if (!n) { const ids = el.getAttribute('aria-labelledby');
    if (ids) n = ids.split(/\s+/).map(i => { const t = document.getElementById(i); return t ? t.innerText : ''; }).join(' '); }
  if (!n && el.labels && el.labels.length) {     // a wrapping <label> also holds the control's own text
    const c = el.labels[0].cloneNode(true); c.querySelectorAll('input,select,textarea,button').forEach(x => x.remove()); n = c.textContent; }
  if (!n && el.tagName === 'INPUT' && ['submit', 'button', 'reset'].includes(el.type)) n = el.value;
  if (!n && !isField(el)) n = el.innerText;
  if (!n) n = el.getAttribute('placeholder') || el.getAttribute('aria-placeholder') || el.getAttribute('data-placeholder') || el.getAttribute('title') || el.getAttribute('alt');
  if (!n && !isField(el)) { const c = el.querySelector('[aria-label],img[alt],[title]');
    if (c) n = c.getAttribute('aria-label') || c.getAttribute('alt') || c.getAttribute('title'); }
  if (!n && el.tagName === 'INPUT') n = el.getAttribute('name');
  return clean(n).slice(0, 80);
};
const valueOf = el => {
  if (el.tagName === 'INPUT') { const ty = (el.type || '').toLowerCase();
    return ['password', 'checkbox', 'radio', 'submit', 'button', 'file'].includes(ty) ? null : clean(el.value).slice(0, 200); }
  if (el.tagName === 'TEXTAREA') return clean(el.value).slice(0, 200);
  if (el.tagName === 'SELECT') return clean((el.selectedOptions[0] || {}).text).slice(0, 80);
  if (el.isContentEditable) return clean(el.innerText).slice(0, 200);
  return null;
};
const stateOf = el => {
  const s = [];
  if (el.getAttribute('aria-pressed') === 'true') s.push('pressed');
  if (el.checked === true || el.getAttribute('aria-checked') === 'true') s.push('checked');
  if (el.getAttribute('aria-expanded') === 'true') s.push('expanded');
  if (el.getAttribute('aria-selected') === 'true') s.push('selected');
  if (el.disabled === true || el.getAttribute('aria-disabled') === 'true') s.push('disabled');
  if (document.activeElement === el) s.push('focused');
  return s;
};
const describe = el => ({ role: roleOf(el), name: nameOf(el), value: valueOf(el), state: stateOf(el) });
"""

SNAPSHOT_JS = "(opts) => {" + _HELPERS + r"""
  const vw = innerWidth, vh = innerHeight;
  const SEL = 'a[href],button,input:not([type=hidden]),textarea,select,summary,[role=button],[role=link],' +
    '[role=textbox],[role=searchbox],[role=combobox],[role=checkbox],[role=radio],[role=switch],[role=tab],' +
    '[role=menuitem],[role=option],[contenteditable=""],[contenteditable=true],[contenteditable=plaintext-only],[onclick]';
  const POST = 'article,[role=article]';
  const DIALOG = 'dialog[open],[role=dialog],[role=alertdialog]';
  const LANDMARK = 'nav,[role=navigation],header,[role=banner],main,[role=main],form,[role=search],aside,footer';

  const found = [], stale = [];
  const walk = root => root.querySelectorAll('*').forEach(el => {
    if (el.hasAttribute('data-holo-ref')) stale.push(el);
    if (el.matches(SEL)) found.push(el);
    if (el.shadowRoot) walk(el.shadowRoot);
  });
  walk(document);
  stale.forEach(el => el.removeAttribute('data-holo-ref'));

  const onScreen = el => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1 || r.bottom <= 0 || r.top >= vh || r.right <= 0 || r.left >= vw) return false;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') return false;
    // Skip what a modal or sticky bar covers: the user can't see or click it either.
    const x = Math.min(Math.max(r.left + r.width / 2, 1), vw - 1), y = Math.min(Math.max(r.top + r.height / 2, 1), vh - 1);
    let top = document.elementFromPoint(x, y);
    while (top && top.shadowRoot) { const inner = top.shadowRoot.elementFromPoint(x, y); if (!inner || inner === top) break; top = inner; }
    if (!top) return false;
    for (let n = top; n; n = up(n)) if (n === el) return true;
    for (let n = el; n; n = up(n)) if (n === top) return true;
    return false;
  };

  const outermost = (el, sel) => { let hit = null; for (let n = el; n; n = up(n)) if (n.matches && n.matches(sel)) hit = n; return hit; };
  const groups = [], groupIds = new Map();
  const groupOf = el => {
    let node = closestDeep(el, DIALOG), kind = 'dialog';
    if (!node) { node = outermost(el, POST); kind = 'post'; }
    if (!node) { node = closestDeep(el, LANDMARK); kind = node ? (node.getAttribute('role') || node.tagName.toLowerCase()) : 'page'; }
    if (!node) return 0;
    if (!groupIds.has(node)) {
      let label = node.getAttribute('aria-label');
      if (!label && kind === 'dialog') { const h = node.querySelector('h1,h2,h3,[role=heading]'); label = h ? h.innerText : ''; }
      if (!label && kind === 'post') label = node.innerText;
      const r = node.getBoundingClientRect();
      groups.push({ id: groups.length + 1, kind, label: clean(label).slice(0, 90),
                    dist: (r.top <= vh / 2 && r.bottom >= vh / 2) ? 0 : Math.min(Math.abs(r.top - vh / 2), Math.abs(r.bottom - vh / 2)) });
      groupIds.set(node, groups.length);
    }
    return groupIds.get(node);
  };

  const elements = [];
  let total = 0;
  for (const el of found) {
    if (!onScreen(el)) continue;
    const d = describe(el);
    if (!d.name && !isField(el)) continue;
    const parent = up(el), holder = parent ? closestDeep(parent, '[data-holo-ref]') : null;
    if (holder && nameOf(holder) === d.name) continue;       // a link wrapping its own button
    total += 1;
    if (elements.length >= opts.max) continue;
    const ref = 'e' + (elements.length + 1);
    el.setAttribute('data-holo-ref', ref);
    elements.push({ ref, group: groupOf(el), ...d });
  }
  // "This post" = the post that covers, or is nearest to, the middle of the screen.
  const posts = groups.filter(g => g.kind === 'post');
  if (posts.length) posts.reduce((a, b) => (b.dist < a.dist ? b : a)).on_screen = true;
  return { title: document.title, url: location.href, groups, elements, total };
}"""

DESCRIBE_JS = "(el) => {" + _HELPERS + " return describe(el); }"

# Text of the group an element belongs to, for checking that a comment landed.
GROUP_TEXT_JS = "(el) => {" + _HELPERS + r"""
  const g = closestDeep(el, 'dialog[open],[role=dialog],[role=alertdialog]') ||
            (() => { let hit = null; for (let n = el; n; n = up(n)) if (n.matches && n.matches('article,[role=article]')) hit = n; return hit; })();
  return clean((g || document.body).innerText);
}"""

EDITABLE_ROLES = {"textbox", "searchbox", "combobox"}


def selector(ref: str) -> str:
    return f'[data-holo-ref="{ref}"]'


def take(page, max_elements: int = 150) -> dict:
    return page.evaluate(SNAPSHOT_JS, {"max": max_elements})


def describe(page, ref: str) -> dict | None:
    """The element's state right now, or None when the ref no longer exists."""
    found = page.locator(selector(ref))
    if found.count() == 0:
        return None
    return found.first.evaluate(DESCRIBE_JS)


def label(el: dict) -> str:
    """One element as the model and the user read it: button "Like" [pressed]."""
    text = f'{el["role"]} "{el["name"]}"'
    if el.get("value") is not None:
        text += f' = "{el["value"]}"'
    if el.get("state"):
        text += " [" + ", ".join(el["state"]) + "]"
    return text


def target_group(snap: dict) -> dict | None:
    """Where "this" points: an open dialog first, else the post on screen."""
    used = {el["group"] for el in snap["elements"]}
    for kind_ok in (lambda g: g["kind"] == "dialog", lambda g: g.get("on_screen")):
        for group in snap["groups"]:
            if kind_ok(group) and group["id"] in used:
                return group
    return None


def render(snap: dict, max_chars: int = 4000) -> str:
    """Compact text map: groups as headers, one line per element."""
    groups = {g["id"]: g for g in snap["groups"]}
    order = sorted(groups.values(), key=lambda g: (g["kind"] != "dialog", not g.get("on_screen"), g["id"]))
    lines: list[str] = []
    for group in order + [None]:
        gid = group["id"] if group else 0
        members = [el for el in snap["elements"] if el["group"] == gid]
        if not members:
            continue
        if group is None:
            lines.append("[page]")
        else:
            mark = " · ON SCREEN" if group.get("on_screen") else ""
            lines.append(f'[{group["kind"]}{mark}] {group["label"]}'.rstrip())
        lines.extend(f'  {el["ref"]} {label(el)}' for el in members)
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars].rsplit("\n", 1)[0] + "\n… (map cut; scroll and snapshot again for the rest)"
    elif snap["total"] > len(snap["elements"]):
        text += f'\n… ({snap["total"] - len(snap["elements"])} more elements not listed)'
    return text
