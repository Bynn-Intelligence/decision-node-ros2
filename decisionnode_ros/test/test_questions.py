import pytest

# The DecisionNode Python SDK is installed with pip, which rosdep does not do: where
# it is missing (as on a build from rosdep keys alone), these tests are skipped. Nothing
# here raises on import, since some test runners import every module to collect it.
try:
    from decisionnode_ros.questions import BoosterError, QuestionError, parse_boosters, parse_questions
except ImportError:
    HAVE_SDK = False
else:
    HAVE_SDK = True

pytestmark = pytest.mark.skipif(not HAVE_SDK, reason="the DecisionNode Python SDK is not installed")


def test_questions_in_order_and_built():
    ids, questions = parse_questions({
        "ids": ["hazard", "person", "crowd", "door"],
        "person.type": "truth", "person.instructions": "Is there a person?",
        "hazard.type": "choice", "hazard.instructions": "Which hazard?", "hazard.options": ["none", "fire"],
        "crowd.type": "number", "crowd.instructions": "How many people?", "crowd.min": 0, "crowd.max": 50,
        "door.type": "box", "door.instructions": "Every open door.", "door.max": 4,
    })
    assert ids == ["hazard", "person", "crowd", "door"]
    assert dict(questions["person"]) == {"type": "truth", "instructions": "Is there a person?"}
    assert dict(questions["hazard"])["criteria"] == {"none": None, "fire": None}
    assert dict(questions["crowd"])["min"] == 0 and dict(questions["crowd"])["max"] == 50
    assert dict(questions["door"])["max"] == 4


@pytest.mark.parametrize("params, words", [
    ({}, "names no question"),
    ({"ids": ["a", "a"]}, "twice"),
    ({"ids": ["a"], "a.type": "maybe", "a.instructions": "?"}, "must be one of"),
    ({"ids": ["a"], "a.type": "truth"}, "non-empty string"),
    ({"ids": ["a"], "a.type": "choice", "a.instructions": "?"}, "at least one option"),
    ({"ids": ["a"], "a.type": "score", "a.instructions": "?"}, "at least one level"),
])
def test_bad_questions_are_refused(params, words):
    with pytest.raises(QuestionError, match=words):
        parse_questions(params)


def test_boosters_by_name_and_with_settings():
    entries = ["", "bynn_depth", ' {"name": "bynn_segment", "options": {"prompt": ["purple gate", "landing pad"]}} ', "age"]
    assert parse_boosters(entries) == [
        "bynn_depth",
        {"name": "bynn_segment", "options": {"prompt": ["purple gate", "landing pad"]}},
        "age",
    ]
    assert parse_boosters([""]) == []


@pytest.mark.parametrize("entry, words", [
    ('{"name": "bynn_segment", ', "not a JSON object"),
    ('{"options": {"prompt": "gate"}}', 'needs a "name"'),
    ('{"name": ""}', 'needs a "name"'),
])
def test_bad_boosters_are_refused(entry, words):
    with pytest.raises(BoosterError, match=words):
        parse_boosters([entry])
