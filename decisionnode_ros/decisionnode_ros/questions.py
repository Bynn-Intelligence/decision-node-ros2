"""The questions the node asks, read from its parameters.

Each question lives under ``questions.<id>`` in the node's parameters, and
``questions.ids`` gives their order::

    questions:
      ids: [person, hazard]
      person:
        type: truth
        instructions: Is there a person in the frame?
      hazard:
        type: choice
        instructions: What hazard is in view, if any?
        options: [none, fire, smoke, water]
"""

import json
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import decisionnode as dn

TYPES = ("truth", "choice", "score", "number", "point", "box")


class QuestionError(ValueError):
    """A question the parameters describe that cannot be asked."""


class BoosterError(ValueError):
    """A booster the parameters describe that cannot be sent."""


def parse_boosters(entries: Sequence[str]) -> List[Any]:
    """Return the boosters to send, in order, from the ``boosters`` parameter.

    Each entry is a booster's name (``bynn_depth``), or a JSON object in the API's form
    for a booster with settings (``{"name": "bynn_segment", "options": {"prompt":
    ["purple gate"]}}``). Empty entries are left out. Which boosters exist and what their
    settings may be is the API's to judge.
    """
    boosters: List[Any] = []
    for entry in entries:
        text = entry.strip()
        if not text:
            continue
        if not text.startswith("{"):
            boosters.append(text)
            continue
        try:
            booster = json.loads(text)
        except ValueError as exc:
            raise BoosterError("boosters: %s is not a JSON object: %s" % (text, exc)) from None
        if not isinstance(booster, dict) or not isinstance(booster.get("name"), str) or not booster["name"]:
            raise BoosterError('boosters: %s needs a "name"' % text)
        boosters.append(booster)
    return boosters


def parse_questions(params: Mapping[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """Return the question ids in order and the questions built with the SDK.

    ``params`` maps a parameter's name below ``questions.`` (``person.type``) to its value.
    """
    ids = list(params.get("ids") or [])
    if not ids:
        raise QuestionError("questions.ids names no question")
    if len(set(ids)) != len(ids):
        raise QuestionError("questions.ids names a question twice")
    questions: Dict[str, Any] = {}
    for qid in ids:
        fields = {k[len(qid) + 1:]: v for k, v in params.items() if k.startswith(qid + ".")}
        questions[qid] = build_question(qid, fields)
    return ids, questions


def build_question(qid: str, fields: Mapping[str, Any]) -> Any:
    kind = fields.get("type")
    if kind not in TYPES:
        raise QuestionError("questions.%s.type must be one of %s, got %r" % (qid, ", ".join(TYPES), kind))
    instructions = fields.get("instructions")
    if not isinstance(instructions, str) or not instructions.strip():
        raise QuestionError("questions.%s.instructions must be a non-empty string" % qid)
    if kind == "truth":
        return dn.truth(instructions)
    if kind == "choice":
        options = list(fields.get("options") or [])
        if not options:
            raise QuestionError("questions.%s.options must list at least one option" % qid)
        return dn.choice(instructions, options)
    if kind == "score":
        levels = list(fields.get("levels") or [])
        if not levels:
            raise QuestionError("questions.%s.levels must list at least one level, lowest first" % qid)
        return dn.score(instructions, levels)
    if kind == "number":
        return dn.number(instructions, **_given(fields, ("min", "max", "step")))
    builder = dn.point if kind == "point" else dn.box
    extra = _given(fields, ("units", "max"))
    if "max" in extra:
        extra["max"] = int(extra["max"])
    return builder(instructions, **extra)


def _given(fields: Mapping[str, Any], names: Tuple[str, ...]) -> Dict[str, Any]:
    return {n: fields[n] for n in names if fields.get(n) not in (None, "")}
