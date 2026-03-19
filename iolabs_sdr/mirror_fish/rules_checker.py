"""
IOlabs AI SDR Platform — Mirror Fish: IOlabs Methodology Rules Checker (Section 14)

Deterministic check of email copy against IOlabs methodology rules.

Confirmed rules:
  Rule 1: No calendar link in Email 1 — blog post CTA only
  Rule 2: Peer framing — "when speaking with [persona]..." present
  Rule 3: Company name in sentence 2–3, never sentence 1
  Rule 4: Opening paragraph 40–60 words, no questions
  Rule 5: No greeting line

TODO: OPEN ITEM 1 — Rules 6–10 must be provided by IOlabs operator before
  Mirror Fish can be fully calibrated. Flag violations for these as PENDING.
  Rule 6: [PENDING — IOlabs to provide]
  Rule 7: [PENDING — IOlabs to provide]
  Rule 8: [PENDING — words/phrases that are never used]
  Rule 9: [PENDING — CTA rules for Email 2 and Email 3]
  Rule 10: [PENDING — formatting rules: bullets, bold, full email body length]
"""

# TODO: Mirror Fish Phase — implement RulesChecker.check(copy_set) → List[RuleViolation]
raise NotImplementedError("mirror_fish/rules_checker.py: implemented after Open Item 1 resolved")
