import pytest

from decisionnode_ros.questions import QuestionError, parse_questions


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
