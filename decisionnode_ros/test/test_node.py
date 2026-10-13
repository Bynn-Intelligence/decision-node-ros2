"""The node itself, over ROS, against the mock API. Skipped where rclpy is not installed."""

import threading
import time

import pytest

rclpy = pytest.importorskip("rclpy")

from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from sensor_msgs.msg import CompressedImage  # noqa: E402

from decisionnode_msgs.msg import Decision  # noqa: E402
from decisionnode_msgs.srv import DecideOnce  # noqa: E402
from decisionnode_ros.images import raw_to_jpeg  # noqa: E402
from decisionnode_ros.node import DecisionNodeRos  # noqa: E402

FRAME = raw_to_jpeg("rgb8", 8, 8, 24, b"\x80" * 192)


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.try_shutdown()


def make_node(api, monkeypatch, **extra):
    monkeypatch.setenv("DECISIONNODE_API_KEY", "dn_test_key")
    overrides = {
        "image_topic": "/test/image/compressed", "compressed": True, "decision_topic": "/test/decision",
        "base_url": api.url, "max_rate_hz": 50.0,
        "questions.ids": ["person"], "questions.person.type": "truth", "questions.person.instructions": "Is there a person?",
    }
    overrides.update(extra)
    return DecisionNodeRos(parameter_overrides=[Parameter(k, value=v) for k, v in overrides.items()])


def spin(nodes):
    executor = MultiThreadedExecutor()
    for n in nodes:
        executor.add_node(n)
    t = threading.Thread(target=executor.spin, daemon=True)
    t.start()
    return executor


def test_a_frame_on_the_topic_is_answered(ros, api, monkeypatch):
    node = make_node(api, monkeypatch)
    probe = rclpy.create_node("probe")
    got = []
    probe.create_subscription(Decision, "/test/decision", got.append, 10)
    pub = probe.create_publisher(CompressedImage, "/test/image/compressed", 10)
    executor = spin([node, probe])
    try:
        deadline = time.monotonic() + 10
        while not got and time.monotonic() < deadline:
            pub.publish(CompressedImage(format="jpeg", data=FRAME))
            time.sleep(0.2)
        assert got, "no decision was published"
        d = got[0]
        assert d.ok and d.request_id == "req_mock_0001"
        assert [a.id for a in d.answers] == ["person"] and d.answers[0].truth == 0.91
        assert api.requests[0]["body"]["questions"]["person"]["type"] == "truth"
    finally:
        executor.shutdown()
        node.destroy_node()
        probe.destroy_node()


def test_decide_once_answers_the_image_given(ros, api, monkeypatch):
    node = make_node(api, monkeypatch)
    probe = rclpy.create_node("probe_service")
    client = probe.create_client(DecideOnce, "decide_once")
    executor = spin([node, probe])
    try:
        assert client.wait_for_service(timeout_sec=10)
        request = DecideOnce.Request()
        request.compressed_image = CompressedImage(format="jpeg", data=FRAME)
        request.state_json = '{"mission": "inspection"}'
        future = client.call_async(request)
        deadline = time.monotonic() + 10
        while not future.done() and time.monotonic() < deadline:
            time.sleep(0.05)
        decision = future.result().decision
        assert decision.ok and decision.answers[0].truth == 0.91
        assert api.requests[-1]["body"]["state"] == {"mission": "inspection"}
    finally:
        executor.shutdown()
        node.destroy_node()
        probe.destroy_node()


def test_no_key_refuses_to_start(ros, api, monkeypatch):
    monkeypatch.delenv("DECISIONNODE_API_KEY", raising=False)
    from decisionnode_ros.engine import ApiKeyError

    with pytest.raises(ApiKeyError):
        DecisionNodeRos(parameter_overrides=[
            Parameter("questions.ids", value=["p"]), Parameter("questions.p.type", value="truth"),
            Parameter("questions.p.instructions", value="?"),
        ])
