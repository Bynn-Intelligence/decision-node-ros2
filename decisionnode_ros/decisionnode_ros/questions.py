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

from typing import Any, Dict, List, Mapping, Tuple

import decisionnode as dn

TYPES = ("truth", "choice", "score", "number", "point", "box")


class QuestionError(ValueError):
    """A question the parameters describe that cannot be asked."""


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
