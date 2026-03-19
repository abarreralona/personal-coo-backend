"""
IOlabs AI SDR Platform — Email Composer (Step 12)

Generates the opening paragraph via Claude API and injects it into the
HTML template for the contact's persona.

Opening paragraph rules (from Section 10 + Open Item 1 confirmed rules):
  Rule 1: No calendar link in Email 1 — blog post CTA only
  Rule 2: Peer framing — "when speaking with [persona] at [industry]..."
  Rule 3: Company name in sentence 2–3, never sentence 1
  Rule 4: Opening paragraph 40–60 words, no questions
  Rule 5: No greeting line — dive straight into the paragraph
  Rule 6: TODO: OPEN ITEM 1 — IOlabs to provide
  Rule 7: TODO: OPEN ITEM 1 — IOlabs to provide
  Rule 8: TODO: OPEN ITEM 1 — words/phrases that are never used
  Rule 9: TODO: OPEN ITEM 1 — CTA rules for Email 2 and Email 3
  Rule 10: TODO: OPEN ITEM 1 — formatting rules

Word count validation:
  Target: 40–70 words (spec says 40–60 in rules, 40–70 in Stage 4 logic — using 70 as retry threshold)
  If response > 70 words → retry ONCE with stricter instruction
  If retry still > 70 words OR API failure → use persona_config.fallback_opening

Template placeholders (all required):
  {opening_paragraph}
  {company_name}
  {tracked_blog_url}
  {pixel_url}
  {sender_name}

Business Rule 7:
  LLM unavailable → use fallback_opening, log degraded_mode=true
"""

# TODO: Step 12 — implement Composer.compose(contact, lead, client_config) → EmailPayload
raise NotImplementedError("email/composer.py: implemented in Step 12")
