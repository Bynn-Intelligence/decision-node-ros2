import base64
import json
import math

import pytest

# The DecisionNode Python SDK is installed with pip, which rosdep does not do: where
# it is missing (as on a build from rosdep keys alone), these tests are skipped. Nothing
# here raises on import, since some test runners import every module to collect it.
try:
    import decisionnode as dn

    from decisionnode_ros.engine import ApiKeyError, DecisionEngine, read_api_key
    from decisionnode_ros.images import raw_to_jpeg
    from decisionnode_ros.questions import parse_questions
except ImportError:
    HAVE_SDK = False
else:
    HAVE_SDK = True
    FRAME = raw_to_jpeg("rgb8", 8, 8, 24, b"\x80" * 192)

pytestmark = pytest.mark.skipif(not HAVE_SDK, reason="the DecisionNode Python SDK is not installed")

PARAMS = {
    "ids": ["person", "hazard", "crowd", "door"],
    "person.type": "truth", "person.instructions": "Is there a person in the frame?",
    "hazard.type": "choice", "hazard.instructions": "What hazard is in view?", "hazard.options": ["none", "smoke"],
    "crowd.type": "number", "crowd.instructions": "How many people?", "crowd.min": 0, "crowd.max": 50,
    "door.type": "box", "door.instructions": "The open door.",
}


def engine(api, **kw):
    ids, questions = parse_questions(PARAMS)
    client = dn.DecisionNode(api_key="dn_test_key", base_url=api.url, max_retries=0)
    return DecisionEngine(client, ids, questions, kw.get("model", "decisionnode-flash"), kw.get("boosters", ()), "camera")


def test_a_frame_is_sent_with_the_questions(api):
    outcome = engine(api, boosters=["age"]).decide(FRAME, {"mission": "inspection"})
    assert outcome.ok
    sent = api.requests[0]
    assert sent["path"] == "/v1/decide"
    assert sent["headers"]["Authorization"] == "Bearer dn_test_key"
    body = sent["body"]
    assert body["model"] == "decisionnode-flash"
    assert body["state"] == {"mission": "inspection"}
    assert list(body["questions"]) == ["person", "hazard", "crowd", "door"]
    assert body["boosters"] == ["age"]
    image = body["images"][0]
    assert image["id"] == "camera" and base64.b64decode(image["data"]) == FRAME


def test_the_answers_are_typed_in_order(api):
    outcome = engine(api).decide(FRAME)
    assert [a.id for a in outcome.answers] == ["person", "hazard", "crowd", "door"]
    person, hazard, crowd, door = outcome.answers
    assert person.type == "truth" and person.truth == 0.91 and math.isnan(person.confidence)
    assert hazard.choice == "smoke" and hazard.labels == ["none", "smoke"] and hazard.probabilities == [0.1, 0.9]
    assert crowd.number == 3 and crowd.expected == 3.2
    assert door.place == [10, 20, 110, 220] and door.present == 0.95 and (door.width, door.height) == (640, 480)
    assert outcome.request_id == "req_mock_0001" and outcome.latency_ms == 42
    assert outcome.model == "decisionnode-flash-0.9.0-rc1" and outcome.cost_usd == 0.00012


def test_several_places_are_flattened(api):
    api.body = {"model": "m", "answers": {"door": {"type": "box", "count": 2, "present": 0.9, "complete": 0.8,
        "boxes": [{"x1": 1, "y1": 2, "x2": 3, "y2": 4, "confidence": 0.7}, {"x1": 5, "y1": 6, "x2": 7, "y2": 8, "confidence": 0.6}],
        "image": "camera", "width": 640, "height": 480}}}
    outcome = engine(api).decide(FRAME)
    door = outcome.answers[3]
    assert door.count == 2 and door.place == [1, 2, 3, 4, 5, 6, 7, 8] and door.place_confidence == [0.7, 0.6]
    assert outcome.answers[0].type == "unknown"  # an answer the API did not send


DEPTH = {"image": "camera", "ahead": 3.21, "directions": [5.12, 4.03, None, 2.81, 6.02, 7.15, 9.33], "ground": True,
         "grid_rows": 2, "grid_cols": 2, "grid": [[9.1, 8.7], [3.4, 2.9]], "depth_min": 1.01, "depth_max": 14.98,
         "depth_median": 4.37, "width": 8, "height": 8}
SEGMENT = {"image": "camera", "width": 8, "height": 8, "prompts": ["purple gate"], "instances": [],
           "depth_source": "bynn_depth", "assumed_hfov_deg": 65}


def test_booster_settings_are_sent_and_their_readings_come_back(api):
    evidence = {
        "bynn_depth": {"version": "bynn_depth-v1", "status": "ok", "latency_ms": 41, "billed_calls": 1, "results": [DEPTH]},
        "bynn_segment": {"version": "bynn_segment-v1", "status": "ok", "latency_ms": 88, "billed_calls": 1, "results": [SEGMENT]},
    }
    api.body = dict(api.body, evidence=evidence)
    boosters = ["bynn_depth", {"name": "bynn_segment", "options": {"prompt": ["purple gate"], "max_instances": 2}}]
    outcome = engine(api, boosters=boosters).decide(FRAME)
    assert api.requests[0]["body"]["boosters"] == boosters
    assert outcome.ok and json.loads(outcome.evidence_json) == evidence
    assert list(json.loads(outcome.evidence_json)) == ["bynn_depth", "bynn_segment"]  # the request's order


KNOWLEDGE = {
    "collection": "col_manuals", "collection_name": "Operating manuals", "corpus": {"version": 12},
    "query": {"source": "auto", "tokens": 9}, "budget": {"mode": "auto", "tokens": 800, "entry": "short", "cause": None},
    "scope": {"key": "model", "value": "ur10e"}, "warnings": [],
    "passages": [
        {"n": 1, "pinned": True, "item": "itm_estop", "chunk": 0, "byte_start": 0, "byte_end": 212,
         "reference": "safety-1", "title": "Emergency stop", "heading": "Before any motion", "tokens": 48,
         "score": None, "lexical": False, "rendered": True},
        {"n": 2, "pinned": False, "item": "itm_gripper", "chunk": 3, "byte_start": 1840, "byte_end": 2311,
         "reference": None, "title": "UR10e gripper", "heading": "Payload limits", "tokens": 97,
         "score": 0.8123, "lexical": False, "rendered": True},
    ],
    "omitted": {"below_min_score": 2}, "pending_items": 0, "search": {"plan": "hybrid", "candidates": 24, "fallback": False},
    "truncated": False,
}


def test_the_knowledge_booster_is_sent_and_its_passages_come_back(api):
    evidence = {"knowledge": {"version": "knowledge-v1", "status": "ok", "latency_ms": 31, "billed_calls": 1,
                              "results": [KNOWLEDGE]}}
    api.body = dict(api.body, evidence=evidence)
    knowledge = {"name": "knowledge", "require": True, "options": {"collection": "col_manuals", "scope": "ur10e", "top_k": 4}}
    outcome = engine(api, boosters=["bynn_depth", knowledge]).decide(FRAME)
    assert api.requests[0]["body"]["boosters"] == ["bynn_depth", knowledge]
    assert outcome.ok and json.loads(outcome.evidence_json) == evidence  # as received, nothing dropped
    passages = json.loads(outcome.evidence_json)["knowledge"]["results"][0]["passages"]
    assert [(p["n"], p["title"], p["heading"]) for p in passages] == [
        (1, "Emergency stop", "Before any motion"), (2, "UR10e gripper", "Payload limits")]


def test_the_boosters_can_change_between_requests(api):
    e = engine(api, boosters=[{"name": "knowledge", "options": {"collection": "col_manuals", "scope": "ur10e"}}])
    e.decide(FRAME)
    e.set_boosters([{"name": "knowledge", "options": {"collection": "col_manuals", "scope": "ur5e"}}])
    e.decide(FRAME)
    e.set_boosters([])
    e.decide(FRAME)
    sent = [r["body"].get("boosters") for r in api.requests]
    assert sent[0][0]["options"]["scope"] == "ur10e" and sent[1][0]["options"]["scope"] == "ur5e" and sent[2] is None


def test_a_required_knowledge_base_with_nothing_ready_is_an_outcome(api):
    api.status = 409
    api.body = {"detail": {"error_type": "knowledge_collection_empty", "message": "The knowledge base has no ready document.",
                           "details": {"items": 0, "failed": 0}}}
    outcome = engine(api, boosters=[{"name": "knowledge", "require": True, "options": {"collection": "col_manuals"}}]).decide(FRAME)
    assert not outcome.ok and outcome.error_type == "knowledge_collection_empty"


def test_without_boosters_there_is_no_evidence(api):
    outcome = engine(api).decide(FRAME)
    assert "boosters" not in api.requests[0]["body"]
    assert outcome.evidence_json == ""


def test_an_api_error_is_an_outcome_not_an_exception(api):
    api.status = 402
    api.body = {"detail": {"error_type": "insufficient_credit", "message": "The workspace has no credit left."}}
    outcome = engine(api).decide(FRAME)
    assert not outcome.ok and outcome.answers == []
    assert outcome.error_type == "insufficient_credit" and "no credit" in outcome.error_message


def test_the_api_key_comes_from_a_file_or_the_environment(tmp_path):
    key_file = tmp_path / "key"
    key_file.write_text("dn_live_from_file\n")
    assert read_api_key(str(key_file), {}) == "dn_live_from_file"
    assert read_api_key("", {"DECISIONNODE_API_KEY": "dn_live_from_env"}) == "dn_live_from_env"
    with pytest.raises(ApiKeyError, match="no API key"):
        read_api_key("", {})
    with pytest.raises(ApiKeyError, match="cannot be read"):
        read_api_key(str(tmp_path / "missing"), {})
