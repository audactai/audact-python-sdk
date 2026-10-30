"""prompt_confidentiality_config and new CheckResult fields."""

from __future__ import annotations

from uuid import uuid4

import pytest

from audact.models import (
    CheckResult,
    Configuration,
    CreateConfigurationRequest,
    PlatformConfigurationSpec,
    PromptConfidentialityConfig,
    UpdateConfigurationRequest,
)

PCC = {
    "hardening": True,
    "canary": True,
    "ngram": False,
    "ngram_size": 6,
    "ngram_min_matches": 3,
    "allowlist_phrases": ["hello there"],
}


def test_prompt_confidentiality_config_all_optional() -> None:
    cfg = PromptConfidentialityConfig()
    assert cfg.model_dump(exclude_none=True) == {}
    assert PromptConfidentialityConfig.model_validate(PCC).model_dump() == PCC


def test_check_result_new_fields_roundtrip() -> None:
    raw = {
        "check_id": "prompt_confidentiality",
        "verdict": "block",
        "prompt_fingerprint": "0123456789abcdef",
        "layers": ["canary", "ngram"],
        "prompt_scope": "shared_union",
    }
    cr = CheckResult.model_validate(raw)
    assert cr.prompt_fingerprint == "0123456789abcdef"
    assert cr.layers == ["canary", "ngram"]
    assert cr.prompt_scope == "shared_union"
    dumped = cr.model_dump()
    for k in ("prompt_fingerprint", "layers", "prompt_scope"):
        assert dumped[k] == raw[k]
    # Control: absent in older responses -> None.
    old = CheckResult.model_validate({"check_id": "x", "verdict": "allow"})
    assert old.prompt_fingerprint is None and old.layers is None and old.prompt_scope is None


def test_configuration_models_roundtrip() -> None:
    create = CreateConfigurationRequest.model_validate(
        {"name": "n", "countries": ["US"], "prompt_confidentiality_config": PCC}
    )
    assert isinstance(create.prompt_confidentiality_config, PromptConfidentialityConfig)
    assert create.model_dump()["prompt_confidentiality_config"] == PCC

    upd = UpdateConfigurationRequest.model_validate({"prompt_confidentiality_config": PCC})
    assert upd.model_dump(exclude_none=True) == {"prompt_confidentiality_config": PCC}
    assert UpdateConfigurationRequest().prompt_confidentiality_config is None

    conf = Configuration.model_validate(
        {
            "config_id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "name": "n",
            "version": 1,
            "countries": ["US"],
            "prompt_confidentiality_config": PCC,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )
    assert conf.prompt_confidentiality_config is not None
    assert conf.prompt_confidentiality_config.ngram_size == 6
    assert conf.model_dump(mode="json")["prompt_confidentiality_config"] == PCC


@pytest.mark.parametrize("with_field", [True, False])
def test_platform_spec_alias(with_field: bool) -> None:
    raw: dict = {"ref": "c1", "name": "n"}
    if with_field:
        raw["promptConfidentialityConfig"] = PCC
    spec = PlatformConfigurationSpec.model_validate(raw)
    if with_field:
        assert spec.prompt_confidentiality_config is not None
        assert spec.prompt_confidentiality_config.allowlist_phrases == ["hello there"]
        assert spec.model_dump(by_alias=True)["promptConfidentialityConfig"] == PCC
    else:
        assert spec.prompt_confidentiality_config is None
