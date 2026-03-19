"""
IOlabs AI SDR Platform — Config Loader Tests (Step 2)

Tests:
  - Load configs/client_example.json successfully
  - All required fields present and correctly typed
  - Missing required field raises ConfigValidationError with descriptive message
  - Invalid field type raises ConfigValidationError
  - SMTP password references env var pattern (not plain text)
  - Classification rules validate correctly (all signal types)
  - Personas validate all 6 types present
  - Classification tiers: A/B/C present with numeric thresholds
"""

import pytest

# TODO: Step 2 — implement tests once core/config_loader.py is built


@pytest.mark.skip(reason="Implemented in Step 2")
def test_load_client_example_config():
    """config/client_example.json loads without errors."""
    pass


@pytest.mark.skip(reason="Implemented in Step 2")
def test_missing_required_field_raises_descriptive_error():
    """Missing client_id raises ConfigValidationError with field name in message."""
    pass


@pytest.mark.skip(reason="Implemented in Step 2")
def test_invalid_emails_per_day_type_raises_error():
    """emails_per_day must be integer, not string."""
    pass


@pytest.mark.skip(reason="Implemented in Step 2")
def test_all_six_personas_required():
    """Config must include all 6 persona keys."""
    pass


@pytest.mark.skip(reason="Implemented in Step 2")
def test_classification_tiers_abc_required():
    """A, B, C tiers must all be present with valid min_score values."""
    pass


@pytest.mark.skip(reason="Implemented in Step 2")
def test_smtp_password_must_be_env_reference():
    """SMTP password field must use ${ENV_VAR} pattern, not plain text."""
    pass
