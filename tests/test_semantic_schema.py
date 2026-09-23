"""
Unit tests for SERA Semantic Contract, Validator, and Evaluator.
"""

import pytest
from app.core.semantic.schema import (
    ActionFamily,
    CanonicalIntent,
    CompactSemanticContext,
    SemanticModifiers,
    SemanticReference,
    SemanticTarget,
)
from app.core.semantic.validator import SemanticValidator
from tests.semantic_interpreter.evaluator import SemanticEvaluator


def test_canonical_intent_serialization():
    intent = CanonicalIntent(
        intent="open_application",
        action_family=ActionFamily.APPLICATION.value,
        target=SemanticTarget(type="application", value="chrome"),
        modifiers=SemanticModifiers(repeat=True),
        confidence=0.98
    )
    d = intent.to_dict()
    assert d["intent"] == "open_application"
    assert d["action_family"] == "APPLICATION"
    assert d["target"]["value"] == "chrome"
    assert d["modifiers"]["repeat"] is True
    assert d["confidence"] == 0.98
    assert d["needs_clarification"] is False


def test_compact_semantic_context():
    ctx = CompactSemanticContext(
        utterance="Open the second one.",
        active_browser="chrome",
        last_verified_action="web_search",
        relevant_entities=[{"type": "search_result", "ordinal": 2}]
    )
    d = ctx.to_dict()
    assert d["utterance"] == "Open the second one."
    assert d["active_browser"] == "chrome"
    assert len(d["relevant_entities"]) == 1


def test_validator_with_clean_json():
    raw_json = '''{
        "intent": "open_application",
        "action_family": "APPLICATION",
        "target": {"type": "application", "value": "chrome"},
        "reference": null,
        "modifiers": {"repeat": false, "relative": false, "direction": null, "temporal": null, "qualifiers": {}},
        "parameters": {},
        "context_resolution": {"resolved": false, "context_entity_id": null, "context_source": null},
        "confidence": 0.95,
        "needs_clarification": false,
        "ambiguity_reason": null
    }'''
    intent_obj, is_valid, err = SemanticValidator.validate(raw_json)
    assert is_valid is True
    assert err is None
    assert intent_obj.intent == "open_application"
    assert intent_obj.target.value == "chrome"


def test_validator_strips_markdown_fences():
    raw_fenced = '''```json
    {
        "intent": "set_brightness",
        "action_family": "SYSTEM",
        "target": {"type": "setting", "value": "brightness"},
        "modifiers": {"repeat": false, "relative": false, "direction": null, "temporal": null, "qualifiers": {}},
        "parameters": {"value": 80},
        "confidence": 0.99,
        "needs_clarification": false
    }
    ```'''
    intent_obj, is_valid, err = SemanticValidator.validate(raw_fenced)
    assert is_valid is True
    assert intent_obj.intent == "set_brightness"
    assert intent_obj.parameters["value"] == 80


def test_validator_handles_malformed_json():
    malformed = '{"intent": "open_application", "target": {'
    intent_obj, is_valid, err = SemanticValidator.validate(malformed)
    assert is_valid is False
    assert "Malformed JSON" in err
    assert intent_obj.needs_clarification is True
    assert intent_obj.intent == "unknown"


def test_evaluator_exact_match():
    pred = CanonicalIntent(
        intent="open_application",
        action_family="APPLICATION",
        target=SemanticTarget(type="application", value="chrome")
    )
    expected = {
        "intent": "open_application",
        "action_family": "APPLICATION",
        "target": {"type": "application", "value": "chrome"},
        "needs_clarification": False
    }
    is_match, comp_matches, reason = SemanticEvaluator.evaluate_case(pred, expected)
    assert is_match is True
    assert all(comp_matches.values())
    assert reason == ""


def test_evaluator_paraphrase_equivalence():
    pred = CanonicalIntent(
        intent="open_application",
        action_family="APPLICATION",
        target=SemanticTarget(type="application", value="google chrome")
    )
    expected = {
        "intent": "open_application",
        "action_family": "APPLICATION",
        "target": {"type": "application", "value": "chrome"},
        "needs_clarification": False
    }
    is_match, comp_matches, reason = SemanticEvaluator.evaluate_case(pred, expected)
    assert is_match is True


def test_evaluator_reference_ordinal_match():
    pred = CanonicalIntent(
        intent="open_reference",
        action_family="BROWSER",
        reference=SemanticReference(type="search_result", scope="previous_search_results", ordinal=1)
    )
    expected = {
        "intent": "open_reference",
        "action_family": "BROWSER",
        "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
        "needs_clarification": False
    }
    is_match, comp_matches, reason = SemanticEvaluator.evaluate_case(pred, expected)
    assert is_match is True


def test_evaluator_ambiguity_negative_match():
    pred = CanonicalIntent(
        intent="unknown",
        action_family="UNKNOWN",
        confidence=0.2,
        needs_clarification=True,
        ambiguity_reason="Underspecified request without active window"
    )
    expected = {
        "needs_clarification": True,
        "confidence": 0.3
    }
    is_match, comp_matches, reason = SemanticEvaluator.evaluate_case(pred, expected)
    assert is_match is True
