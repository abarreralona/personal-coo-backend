"""
IOlabs AI SDR Platform — Config Loader Tests (Step 2)

Acceptance criterion (Section 12):
    "Loads and validates client JSON. Raises descriptive error on any missing required field."

All tests in this file must pass before proceeding to Step 3.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from core.config_loader import (
    REQUIRED_PERSONAS,
    ClientConfig,
    ClassificationTiers,
    PersonaConfig,
    SMTPConfig,
    load_client_config,
)
from core.exceptions import ConfigNotFoundError, ConfigValidationError

# ── Paths ─────────────────────────────────────────────────────────────────────

CONFIGS_DIR = Path(__file__).parent.parent / "configs"
CLIENT_EXAMPLE_PATH = CONFIGS_DIR / "client_example.json"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def smtp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the SMTP password env var required by client_example.json."""
    monkeypatch.setenv("SMTP_PASSWORD_CLIENT_EXAMPLE", "test_smtp_password_123")


@pytest.fixture()
def raw_example_config() -> dict:
    """Return the raw parsed dict from client_example.json (no env resolution)."""
    return json.loads(CLIENT_EXAMPLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def valid_config_path(
    tmp_path: Path,
    raw_example_config: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, dict]:
    """
    Write a clean copy of client_example config to tmp_path,
    set the required env var, and return (configs_dir, raw_dict).
    """
    monkeypatch.setenv("SMTP_PASSWORD_CLIENT_EXAMPLE", "test_smtp_pass")
    cfg = deepcopy(raw_example_config)
    (tmp_path / "client_example.json").write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path, cfg


# ── Happy-path tests ──────────────────────────────────────────────────────────


def test_load_client_example_returns_client_config(smtp_env: None) -> None:
    """client_example.json loads and returns a ClientConfig instance."""
    config = load_client_config("client_example")
    assert isinstance(config, ClientConfig)


def test_client_id_matches_filename(smtp_env: None) -> None:
    config = load_client_config("client_example")
    assert config.client_id == "client_example"


def test_core_fields_correct(smtp_env: None) -> None:
    config = load_client_config("client_example")
    assert config.sender_name == "Jordan Rivera"
    assert config.sender_email == "jordan@example-client.com"
    assert config.emails_per_day == 20
    assert config.target_timezone == "America/Chicago"


def test_smtp_password_resolved_from_env(smtp_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """SMTP password is resolved from env var, not stored as raw ${...} ref."""
    monkeypatch.setenv("SMTP_PASSWORD_CLIENT_EXAMPLE", "my_secret_password")
    config = load_client_config("client_example")
    assert config.sender_smtp.password == "my_secret_password"
    # Must not contain the raw env ref string
    assert "${" not in config.sender_smtp.password


def test_all_six_personas_present(smtp_env: None) -> None:
    """All 6 required persona types must be in the config."""
    config = load_client_config("client_example")
    assert set(config.personas.keys()) == REQUIRED_PERSONAS


def test_personas_are_persona_config_instances(smtp_env: None) -> None:
    config = load_client_config("client_example")
    for key, persona in config.personas.items():
        assert isinstance(persona, PersonaConfig), f"Persona '{key}' is not a PersonaConfig"


def test_classification_tiers_abc_all_present(smtp_env: None) -> None:
    config = load_client_config("client_example")
    tiers = config.classification_tiers
    assert isinstance(tiers, ClassificationTiers)
    assert tiers.A.min_score == 70
    assert tiers.B.min_score == 40
    assert tiers.C.min_score == 0


def test_classification_tiers_labels_correct(smtp_env: None) -> None:
    config = load_client_config("client_example")
    assert config.classification_tiers.A.label == "Hot"
    assert config.classification_tiers.B.label == "Warm"
    assert config.classification_tiers.C.label == "Discard"


def test_classification_rules_list_non_empty(smtp_env: None) -> None:
    config = load_client_config("client_example")
    assert len(config.classification_rules) > 0


def test_disqualifying_rule_parses(smtp_env: None) -> None:
    config = load_client_config("client_example")
    disqualifying = [r for r in config.classification_rules if r.disqualifying]
    assert len(disqualifying) >= 1, "Expected at least one disqualifying rule in client_example config"


def test_reply_handlers_all_present(smtp_env: None) -> None:
    config = load_client_config("client_example")
    rh = config.reply_handlers
    assert rh.ooo.action == "reschedule"
    assert rh.not_interested.action == "flag_pause"
    assert rh.unsubscribe.action == "dnc"
    assert rh.wrong_email.action == "flag_invalid"
    assert rh.interested.enabled is True
    assert rh.asking_for_info.enabled is True
    assert rh.complex_question.enabled is True


def test_handoff_trigger_includes_interested(smtp_env: None) -> None:
    config = load_client_config("client_example")
    assert "interested" in config.handoff_trigger


def test_linkedin_invite_limit_positive(smtp_env: None) -> None:
    config = load_client_config("client_example")
    assert config.linkedin_config.daily_invite_limit > 0


def test_executive_persona_has_real_system_prompt(smtp_env: None) -> None:
    """Executive persona must have a real prompt, not a TODO stub."""
    config = load_client_config("client_example")
    prompt = config.personas["executive"].system_prompt
    assert "TODO" not in prompt
    assert len(prompt) > 50


def test_executive_sequence_timing_positive(smtp_env: None) -> None:
    config = load_client_config("client_example")
    timing = config.personas["executive"].sequence_timing
    assert timing.email_1_to_2 > 0
    assert timing.email_2_to_3 > 0
    assert timing.email_3_to_final > 0


# ── SMTP env var failure ───────────────────────────────────────────────────────


def test_smtp_password_env_var_missing_raises_config_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing SMTP env var raises ConfigValidationError with the var name in the message."""
    monkeypatch.delenv("SMTP_PASSWORD_CLIENT_EXAMPLE", raising=False)
    with pytest.raises(ConfigValidationError) as exc_info:
        load_client_config("client_example")
    assert "SMTP_PASSWORD_CLIENT_EXAMPLE" in str(exc_info.value)


def test_smtp_password_env_var_missing_error_mentions_dotenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Error message guides user to the .env file."""
    monkeypatch.delenv("SMTP_PASSWORD_CLIENT_EXAMPLE", raising=False)
    with pytest.raises(ConfigValidationError) as exc_info:
        load_client_config("client_example")
    # Should tell user to add it to .env
    assert ".env" in str(exc_info.value)


# ── Config not found ──────────────────────────────────────────────────────────


def test_config_not_found_raises_config_not_found_error() -> None:
    with pytest.raises(ConfigNotFoundError):
        load_client_config("nonexistent_client_xyz")


def test_config_not_found_error_mentions_client_id() -> None:
    with pytest.raises(ConfigNotFoundError) as exc_info:
        load_client_config("ghost_client")
    assert "ghost_client" in str(exc_info.value)


def test_config_not_found_error_mentions_template() -> None:
    """Error message must guide user to create config from the example template."""
    with pytest.raises(ConfigNotFoundError) as exc_info:
        load_client_config("ghost_client")
    msg = str(exc_info.value)
    assert "client_example.json" in msg or "template" in msg


# ── Missing required fields ───────────────────────────────────────────────────


def test_missing_client_id_raises_config_validation_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    configs_dir, cfg = valid_config_path
    del cfg["client_id"]
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError) as exc_info:
        load_client_config("client_example", configs_dir=configs_dir)
    assert "client_example" in str(exc_info.value)


def test_missing_sender_name_raises_config_validation_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    configs_dir, cfg = valid_config_path
    del cfg["sender_name"]
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError):
        load_client_config("client_example", configs_dir=configs_dir)


def test_missing_discovery_raises_config_validation_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    configs_dir, cfg = valid_config_path
    del cfg["discovery"]
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError):
        load_client_config("client_example", configs_dir=configs_dir)


def test_missing_classification_tiers_raises_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    configs_dir, cfg = valid_config_path
    del cfg["classification_tiers"]
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError):
        load_client_config("client_example", configs_dir=configs_dir)


def test_missing_personas_section_raises_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    configs_dir, cfg = valid_config_path
    del cfg["personas"]
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError):
        load_client_config("client_example", configs_dir=configs_dir)


# ── Field validation ──────────────────────────────────────────────────────────


def test_invalid_emails_per_day_zero_raises_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    configs_dir, cfg = valid_config_path
    cfg["emails_per_day"] = 0
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError):
        load_client_config("client_example", configs_dir=configs_dir)


def test_invalid_emails_per_day_negative_raises_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    configs_dir, cfg = valid_config_path
    cfg["emails_per_day"] = -5
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError):
        load_client_config("client_example", configs_dir=configs_dir)


def test_invalid_timezone_raises_descriptive_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    configs_dir, cfg = valid_config_path
    cfg["target_timezone"] = "Not/A/Timezone"
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError) as exc_info:
        load_client_config("client_example", configs_dir=configs_dir)
    assert "timezone" in str(exc_info.value).lower()


def test_invalid_client_id_with_uppercase_raises_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    """client_id must be lowercase — PostgreSQL schema names are case-sensitive."""
    configs_dir, cfg = valid_config_path
    cfg["client_id"] = "ClientExample"  # uppercase not allowed
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError) as exc_info:
        load_client_config("client_example", configs_dir=configs_dir)
    assert "client_id" in str(exc_info.value)


def test_client_id_mismatch_raises_descriptive_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    """client_id in JSON must match the filename."""
    configs_dir, cfg = valid_config_path
    cfg["client_id"] = "different_client"
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError) as exc_info:
        load_client_config("client_example", configs_dir=configs_dir)
    msg = str(exc_info.value)
    assert "different_client" in msg or "mismatch" in msg


def test_missing_persona_key_raises_descriptive_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    """Error must name which persona type is missing."""
    configs_dir, cfg = valid_config_path
    del cfg["personas"]["ops"]
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError) as exc_info:
        load_client_config("client_example", configs_dir=configs_dir)
    assert "ops" in str(exc_info.value)


def test_classification_tier_ordering_violation_raises_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    """A.min_score must be strictly greater than B.min_score."""
    configs_dir, cfg = valid_config_path
    cfg["classification_tiers"]["A"]["min_score"] = 30
    cfg["classification_tiers"]["B"]["min_score"] = 50  # B > A — invalid
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError):
        load_client_config("client_example", configs_dir=configs_dir)


def test_visual_ai_rule_without_prompt_raises_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    """visual_ai signal type requires a non-empty prompt."""
    configs_dir, cfg = valid_config_path
    cfg["classification_rules"].append(
        {
            "name": "bad_visual_rule",
            "type": "visual_ai",
            "source": "homepage_screenshot",
            "prompt": "",  # invalid — must be non-empty for visual_ai
            "keywords": [],
            "weight": 10,
            "disqualifying": False,
        }
    )
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError) as exc_info:
        load_client_config("client_example", configs_dir=configs_dir)
    assert "prompt" in str(exc_info.value)


def test_keyword_rule_without_keywords_raises_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    """keyword signal type requires at least one keyword."""
    configs_dir, cfg = valid_config_path
    cfg["classification_rules"].append(
        {
            "name": "bad_keyword_rule",
            "type": "keyword",
            "source": "page_text",
            "prompt": "",
            "keywords": [],  # invalid — must be non-empty for keyword type
            "weight": 10,
            "disqualifying": False,
        }
    )
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError) as exc_info:
        load_client_config("client_example", configs_dir=configs_dir)
    assert "keyword" in str(exc_info.value).lower()


def test_invalid_json_raises_config_validation_error(tmp_path: Path) -> None:
    """Malformed JSON raises ConfigValidationError with line info."""
    bad_json = tmp_path / "broken.json"
    bad_json.write_text("{ invalid json !!!", encoding="utf-8")
    with pytest.raises(ConfigValidationError) as exc_info:
        load_client_config("broken", configs_dir=tmp_path)
    assert "JSON" in str(exc_info.value) or "json" in str(exc_info.value).lower()


def test_linkedin_connection_message_too_long_raises_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    """LinkedIn connection message must be ≤ 300 characters."""
    configs_dir, cfg = valid_config_path
    cfg["linkedin_config"]["connection_message_template"] = "x" * 301
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError):
        load_client_config("client_example", configs_dir=configs_dir)


def test_smtp_port_out_of_range_raises_error(
    valid_config_path: tuple[Path, dict],
) -> None:
    configs_dir, cfg = valid_config_path
    cfg["sender_smtp"]["port"] = 99999
    (configs_dir / "client_example.json").write_text(json.dumps(cfg))
    with pytest.raises(ConfigValidationError):
        load_client_config("client_example", configs_dir=configs_dir)


def test_extra_unknown_fields_are_ignored(smtp_env: None) -> None:
    """
    Top-level _comment and _open_items fields in the JSON (used as in-file docs)
    must be silently ignored — not cause validation errors.
    """
    config = load_client_config("client_example")
    # If we got here, extra fields were ignored
    assert config.client_id == "client_example"
