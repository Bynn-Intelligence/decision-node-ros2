"""One decision about one frame, through the DecisionNode Python SDK.

Nothing here imports ROS, so it can be tested on its own. The result is a plain
:class:`Outcome`; the node turns it into a ``decisionnode_msgs/Decision``.
"""

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

import decisionnode as dn

NAN = float("nan")


class ApiKeyError(ValueError):
    """No API key could be found."""


def read_api_key(key_file: str = "", environ: Mapping[str, str] = os.environ) -> str:
    """The API key from ``key_file`` when it is given, else ``DECISIONNODE_API_KEY``.

    The key is never a ROS parameter's value: parameters are readable by anything on the
    ROS graph. The key is never logged.
    """
    if key_file:
        try:
            with open(os.path.expanduser(key_file), "r", encoding="utf-8") as fh:
                key = fh.read().strip()
        except OSError as exc:
            raise ApiKeyError("the API key file %s cannot be read: %s" % (key_file, exc.strerror)) from None
        if not key:
            raise ApiKeyError("the API key file %s is empty" % key_file)
        return key
    key = (environ.get("DECISIONNODE_API_KEY") or "").strip()
    if not key:
        raise ApiKeyError("no API key: set DECISIONNODE_API_KEY, or the parameter api_key_file to a file holding it")
    return key


@dataclass
class AnswerOut:
    id: str
    type: str
    truth: float = NAN
    choice: str = ""
    score: float = NAN
    number: float = NAN
    expected: float = NAN
    confidence: float = NAN
    present: float = NAN
    place: List[float] = field(default_factory=list)
    place_confidence: List[float] = field(default_factory=list)
    count: int = 0
    complete: float = NAN
    image: str = ""
    width: int = 0
    height: int = 0
    labels: List[str] = field(default_factory=list)
    probabilities: List[float] = field(default_factory=list)
    raw_json: str = ""


@dataclass
class Outcome:
    ok: bool
    answers: List[AnswerOut] = field(default_factory=list)
    request_id: str = ""
    model: str = ""
    latency_ms: float = NAN
    cost_usd: float = NAN
    evidence_json: str = ""
    error_type: str = ""
    error_message: str = ""


def _num(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return NAN
    return float(value)


def answer_out(qid: str, raw: Any) -> AnswerOut:
    """One answer, read field by field from the answer as the API sent it."""
    if not isinstance(raw, Mapping):
        return AnswerOut(id=qid, type="unknown", raw_json=json.dumps(raw))
    kind = raw.get("type") if isinstance(raw.get("type"), str) else "unknown"
    if kind == "noul":
        kind, raw = "truth", dict(raw, truth=raw.get("noul"))
    out = AnswerOut(id=qid, type=kind, raw_json=json.dumps(raw, ensure_ascii=False, sort_keys=True))
    out.truth = _num(raw.get("truth"))
    out.choice = raw.get("choice") if isinstance(raw.get("choice"), str) else ""
    out.score = _num(raw.get("score"))
    out.number = _num(raw.get("number"))
    out.expected = _num(raw.get("expected"))
    out.confidence = _num(raw.get("confidence"))
    out.present = _num(raw.get("present"))
    out.complete = _num(raw.get("complete"))
    out.image = raw.get("image") if isinstance(raw.get("image"), str) else ""
    for name in ("width", "height", "count"):
        value = raw.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            setattr(out, name, value)
    places = raw.get("points") if isinstance(raw.get("points"), list) else raw.get("boxes")
    corners = ("x", "y") if kind == "point" else ("x1", "y1", "x2", "y2")
    if isinstance(places, list):
        for p in places:
            if isinstance(p, Mapping):
                out.place.extend(_num(p.get(c)) for c in corners)
                out.place_confidence.append(_num(p.get("confidence")))
    elif kind in ("point", "box"):
        out.place = [_num(raw.get(c)) for c in corners]
    probs = raw.get("probabilities")
    if isinstance(probs, Mapping):
        for label, p in probs.items():
            out.labels.append(str(label))
            out.probabilities.append(_num(p))
    return out


class DecisionEngine:
    """Asks the configured questions about a frame and returns an :class:`Outcome`."""

    def __init__(
        self,
        client: Any,
        ids: Sequence[str],
        questions: Mapping[str, Any],
        model: Optional[str] = None,
        boosters: Sequence[Any] = (),
        image_id: str = "camera",
    ) -> None:
        self.client = client
        self.ids = list(ids)
        self.questions = dict(questions)
        self.model = model or None
        self.boosters = list(boosters) or None
        self.image_id = image_id

    def set_boosters(self, boosters: Sequence[Any]) -> None:
        """The boosters of every request from now on; one already sent keeps its own."""
        self.boosters = list(boosters) or None

    def decide(self, image: Optional[bytes], state: Any = None) -> Outcome:
        images = [dn.Image(self.image_id, data=image)] if image else None
        kwargs: Dict[str, Any] = {"questions": self.questions, "images": images, "model": self.model, "boosters": self.boosters}
        if state is not None:
            kwargs["state"] = state
        try:
            decision = self.client.decide(**kwargs)
        except dn.DecisionNodeError as exc:
            return error_outcome(exc)
        return decision_outcome(decision, self.ids)


def decision_outcome(decision: Any, ids: Sequence[str]) -> Outcome:
    raw = decision.raw if isinstance(getattr(decision, "raw", None), Mapping) else {}
    answers = raw.get("answers") if isinstance(raw.get("answers"), Mapping) else {}
    cost = (raw.get("usage") or {}).get("cost") if isinstance(raw.get("usage"), Mapping) else None
    evidence = raw.get("evidence")
    return Outcome(
        ok=True,
        answers=[answer_out(qid, answers.get(qid)) for qid in ids],
        request_id=decision.request_id or "",
        model=decision.model or "",
        latency_ms=_num(decision.latency_ms),
        cost_usd=_num(cost.get("usd")) if isinstance(cost, Mapping) else NAN,
        evidence_json=json.dumps(evidence, ensure_ascii=False) if isinstance(evidence, Mapping) else "",
    )


def reply_outcome(reply: Any, ids: Sequence[str]) -> Outcome:
    """A session's reply to one frame."""
    raw = reply.raw if isinstance(getattr(reply, "raw", None), Mapping) else {}
    answers = raw.get("answers") if isinstance(raw.get("answers"), Mapping) else {}
    cost = (raw.get("usage") or {}).get("cost") if isinstance(raw.get("usage"), Mapping) else None
    return Outcome(
        ok=True,
        answers=[answer_out(qid, answers.get(qid)) for qid in ids],
        latency_ms=_num(getattr(reply, "latency_ms", None)),
        cost_usd=_num(cost.get("usd")) if isinstance(cost, Mapping) else NAN,
    )


def error_outcome(exc: BaseException) -> Outcome:
    error_type = getattr(exc, "error_type", None) or type(exc).__name__
    message = str(getattr(exc, "message", None) or exc)
    request_id = getattr(exc, "request_id", None) or ""
    return Outcome(ok=False, error_type=str(error_type), error_message=message, request_id=str(request_id))


def is_nan(value: float) -> bool:
    return isinstance(value, float) and math.isnan(value)
