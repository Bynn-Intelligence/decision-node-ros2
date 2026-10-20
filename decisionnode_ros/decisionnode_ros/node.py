"""The decisionnode_ros node: camera frames in, typed decisions out.

DecisionNode is a decision engine. This node asks it the questions configured in its
parameters about the frames on an image topic, at a bounded rate, and publishes each
set of answers as a ``decisionnode_msgs/Decision``. Answers are inputs to your own
logic, never the sole means of control: see the README's safety section.
"""

import json
import threading
from typing import Any, Dict, List, Optional

import decisionnode as dn
import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import String

from decisionnode_msgs.msg import Answer, Decision
from decisionnode_msgs.srv import DecideOnce

from .engine import ApiKeyError, DecisionEngine, Outcome, error_outcome, read_api_key, reply_outcome
from .gate import FrameGate
from .images import ImageError, compressed_bytes, raw_to_jpeg
from .questions import BoosterError, QuestionError, parse_boosters, parse_knowledge, parse_questions, with_knowledge

DEFAULTS: Dict[str, Any] = {
    "image_topic": "image",
    "compressed": False,
    "state_topic": "",
    "decision_topic": "decision",
    "model": "decisionnode-flash",
    "boosters": [""],
    "max_rate_hz": 1.0,
    "max_in_flight": 1,
    "timeout_s": 10.0,
    "jpeg_quality": 85,
    "image_id": "camera",
    "session_mode": False,
    "session_window": 0,
    "api_key_file": "",
    "base_url": "",
}


class _Frame:
    __slots__ = ("header", "msg", "compressed")

    def __init__(self, header: Any, msg: Any, compressed: bool) -> None:
        self.header = header
        self.msg = msg
        self.compressed = compressed


class DecisionNodeRos(Node):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            "decisionnode",
            allow_undeclared_parameters=True,
            automatically_declare_parameters_from_overrides=True,
            **kwargs,
        )
        # Set before anything here can raise: rclpy destroys a node whose constructor
        # failed when its context shuts down, and destroy_node reads these.
        self._stopping = threading.Event()
        self._session: Any = None
        self._threads: List[threading.Thread] = []
        self.gate: Optional[FrameGate] = None
        self.p = {name: self._param(name, default) for name, default in DEFAULTS.items()}
        self.p["boosters"] = parse_boosters(self.p["boosters"])
        boosters = with_knowledge(self.p["boosters"], parse_knowledge(self._knowledge_params()))
        if boosters and self.p["session_mode"]:
            raise BoosterError("boosters cannot be used with session_mode: a live session takes no boosters")
        prefixed = self.get_parameters_by_prefix("questions")
        self.ids, self.questions = parse_questions({name: param.value for name, param in prefixed.items()})

        key = read_api_key(self.p["api_key_file"])
        options: Dict[str, Any] = {"api_key": key, "timeout": float(self.p["timeout_s"])}
        if self.p["base_url"]:
            options["base_url"] = self.p["base_url"]
        self.client = dn.DecisionNode(**options)
        del key
        self.engine = DecisionEngine(
            self.client, self.ids, self.questions, self.p["model"], boosters, self.p["image_id"]
        )
        # knowledge.* may change while the node runs (a new mission, another robot model):
        # the next request sends the new booster, and a change that cannot be sent is refused.
        self.add_on_set_parameters_callback(self._on_set_parameters)

        self.publisher = self.create_publisher(Decision, self.p["decision_topic"], 10)
        self.gate = FrameGate(float(self.p["max_rate_hz"]), int(self.p["max_in_flight"]))
        self._latest: Optional[_Frame] = None
        self._state: Any = None
        self._lock = threading.Lock()
        self._seq_headers: Dict[int, Any] = {}

        kind = CompressedImage if self.p["compressed"] else Image
        self.create_subscription(kind, self.p["image_topic"], self._on_image, qos_profile_sensor_data)
        if self.p["state_topic"]:
            self.create_subscription(String, self.p["state_topic"], self._on_state, 10)
        self.create_service(DecideOnce, "decide_once", self._on_decide_once, callback_group=MutuallyExclusiveCallbackGroup())

        workers = 1 if self.p["session_mode"] else int(self.p["max_in_flight"])
        target = self._session_loop if self.p["session_mode"] else self._decide_loop
        self._threads = [threading.Thread(target=target, daemon=True) for _ in range(workers)]
        for t in self._threads:
            t.start()
        self.get_logger().info(
            "asking %d question(s) of %s about %s at up to %.2f decisions/s%s"
            % (len(self.ids), self.p["model"], self.p["image_topic"], float(self.p["max_rate_hz"]),
               ", in a live session" if self.p["session_mode"] else "")
        )

    # ---------------------------------------------------------------- parameters

    def _param(self, name: str, default: Any) -> Any:
        if not self.has_parameter(name):
            self.declare_parameter(name, default)
        return self.get_parameter(name).value

    def _knowledge_params(self) -> Dict[str, Any]:
        return {name: param.value for name, param in self.get_parameters_by_prefix("knowledge").items()}

    def _on_set_parameters(self, params: List[Any]) -> SetParametersResult:
        changed = {p.name[len("knowledge."):]: p.value for p in params if p.name.startswith("knowledge.")}
        if not changed:
            return SetParametersResult(successful=True)
        try:
            knowledge = parse_knowledge(dict(self._knowledge_params(), **changed))
            boosters = with_knowledge(self.p["boosters"], knowledge)
            if boosters and self.p["session_mode"]:
                raise BoosterError("knowledge cannot be used with session_mode: a live session takes no boosters")
        except BoosterError as exc:
            return SetParametersResult(successful=False, reason=str(exc))
        self.engine.set_boosters(boosters)
        return SetParametersResult(successful=True)

    # ---------------------------------------------------------------- inputs

    def _on_image(self, msg: Any) -> None:
        frame = _Frame(msg.header, msg, bool(self.p["compressed"]))
        with self._lock:
            self._latest = frame
        self.gate.offer(frame)

    def _on_state(self, msg: String) -> None:
        try:
            state = json.loads(msg.data)
        except ValueError:
            state = msg.data
        with self._lock:
            self._state = state

    def _image_bytes(self, frame: _Frame) -> bytes:
        m = frame.msg
        if frame.compressed:
            return compressed_bytes(m.format, m.data)
        return raw_to_jpeg(m.encoding, m.width, m.height, m.step, m.data, int(self.p["jpeg_quality"]))

    # ---------------------------------------------------------------- one request per frame

    def _decide_loop(self) -> None:
        while not self._stopping.is_set():
            taken = self.gate.take(timeout=0.5)
            if taken is None:
                continue
            frame, dropped = taken
            try:
                outcome = self._decide(frame)
            finally:
                self.gate.done()
            self._publish(outcome, frame.header, dropped)

    def _decide(self, frame: _Frame, state: Any = None) -> Outcome:
        try:
            image = self._image_bytes(frame)
        except ImageError as exc:
            return Outcome(ok=False, error_type="image_error", error_message=str(exc))
        if state is None:
            with self._lock:
                state = self._state
        return self.engine.decide(image, state)

    # ---------------------------------------------------------------- a live session

    def _session_loop(self) -> None:
        reader: Optional[threading.Thread] = None
        while not self._stopping.is_set():
            if self._session is None:
                try:
                    self._session = self._open_session()
                except dn.DecisionNodeError as exc:
                    self._publish(error_outcome(exc), None, 0)
                    self._stopping.wait(2.0)
                    continue
                reader = threading.Thread(target=self._read_session, args=(self._session,), daemon=True)
                reader.start()
            taken = self.gate.take(timeout=0.5)
            if taken is None:
                continue
            frame, dropped = taken
            try:
                image = self._image_bytes(frame)
                seq = self._session.send(image=dn.Image(self.p["image_id"], data=image))
                with self._lock:
                    self._seq_headers[seq] = (frame.header, dropped)
            except ImageError as exc:
                self._publish(Outcome(ok=False, error_type="image_error", error_message=str(exc)), frame.header, dropped)
            except dn.DecisionNodeError as exc:
                self._publish(error_outcome(exc), frame.header, dropped)
            finally:
                self.gate.done()

    def _open_session(self) -> Any:
        options: Dict[str, Any] = {"questions": self.questions, "model": self.p["model"]}
        with self._lock:
            if self._state is not None:
                options["state"] = self._state
        if int(self.p["session_window"]) > 0:
            options["window"] = int(self.p["session_window"])
        session = self.client.open_session(**options)
        session.connect()
        return session

    def _read_session(self, session: Any) -> None:
        for event in session.replies():
            if self._stopping.is_set():
                return
            seq = getattr(event, "seq", None)
            with self._lock:
                header, dropped = self._seq_headers.pop(seq, (None, 0))
            if isinstance(event, dn.Reply):
                self._publish(reply_outcome(event, self.ids), header, dropped)
            elif isinstance(event, dn.FrameError):
                self._publish(Outcome(ok=False, error_type=event.error_type or "frame_error", error_message=event.message or ""), header, dropped)
            else:  # SessionClosed: the loop opens a new one
                self._publish(Outcome(ok=False, error_type="session_closed", error_message="code %s" % getattr(event, "code", "")), None, 0)
                if self._session is session:
                    self._session = None
                return

    # ---------------------------------------------------------------- the service

    def _on_decide_once(self, request: Any, response: Any) -> Any:
        frame: Optional[_Frame] = None
        if request.compressed_image.data:
            frame = _Frame(request.compressed_image.header, request.compressed_image, True)
        elif request.image.data:
            frame = _Frame(request.image.header, request.image, False)
        else:
            with self._lock:
                frame = self._latest
        state = None
        if request.state_json:
            try:
                state = json.loads(request.state_json)
            except ValueError:
                state = request.state_json
        if frame is None:
            outcome = Outcome(ok=False, error_type="no_frame", error_message="no image given and none received yet")
            response.decision = self._to_msg(outcome, None, 0)
            return response
        response.decision = self._to_msg(self._decide(frame, state), frame.header, 0)
        return response

    # ---------------------------------------------------------------- output

    def _publish(self, outcome: Outcome, header: Any, dropped: int) -> None:
        self.publisher.publish(self._to_msg(outcome, header, dropped))

    def _to_msg(self, outcome: Outcome, header: Any, dropped: int) -> Decision:
        msg = Decision()
        if header is not None:
            msg.header = header
        else:
            msg.header.stamp = self.get_clock().now().to_msg()
        msg.ok = outcome.ok
        msg.request_id = outcome.request_id
        msg.model = outcome.model
        msg.latency_ms = outcome.latency_ms
        msg.cost_usd = outcome.cost_usd
        msg.evidence_json = outcome.evidence_json
        msg.error_type = outcome.error_type
        msg.error_message = outcome.error_message
        msg.frames_dropped = int(dropped)
        answers: List[Answer] = []
        for a in outcome.answers:
            m = Answer()
            for name in ("id", "type", "truth", "choice", "score", "number", "expected", "confidence", "present",
                         "place", "place_confidence", "count", "complete", "image", "width", "height",
                         "labels", "probabilities", "raw_json"):
                setattr(m, name, getattr(a, name))
            answers.append(m)
        msg.answers = answers
        return msg

    def destroy_node(self) -> bool:
        self._stopping.set()
        if self.gate is not None:
            self.gate.close()
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # noqa: BLE001 - closing on the way out
                pass
        return super().destroy_node()


def main(args: Optional[List[str]] = None) -> None:
    rclpy.init(args=args)
    try:
        node = DecisionNodeRos()
    except (ApiKeyError, QuestionError, BoosterError, ValueError) as exc:
        rclpy.logging.get_logger("decisionnode").fatal(str(exc))
        rclpy.try_shutdown()
        raise SystemExit(1) from None
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, getattr(rclpy.executors, "ExternalShutdownException", KeyboardInterrupt)):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
