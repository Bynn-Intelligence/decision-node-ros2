# DecisionNode for ROS 2

DecisionNode is a decision engine. You ask it questions about what a camera sees, and it
returns typed answers: true or false, one of your options, a score, a number, a point or a
box, each with its confidence. This repository brings it to ROS 2 as two packages:

| Package | What it is |
|---|---|
| `decisionnode_ros` | An `rclpy` node. It reads frames from an image topic, asks your questions at a rate you set, and publishes each set of answers. |
| `decisionnode_msgs` | The `Decision` and `Answer` messages and the `DecideOnce` service. |

Supported: ROS 2 Jazzy (Ubuntu 24.04) and Humble (Ubuntu 22.04), on amd64 and arm64.

## Safety: decisions, never the controller

**Answers are decisions only. They are never the sole means of controlling a robot, a
vehicle, an aircraft, a machine or any other system whose failure could cause death,
injury or damage.**

The DecisionNode [Terms of Service](https://decisionnode.com/legal/terms#c-7-6) say so in
their section on safety-critical use, and they apply to everything this node publishes. If
you use answers anywhere near such a system, you must:

- keep control in a controller designed, tested and, where required, certified for that
  purpose, and use answers only as one input to it;
- keep independent safety controls, limits and fallback behaviour that bring and keep the
  system in a safe state without any answer, including when an answer is late, dropped,
  unavailable or wrong;
- test and validate the system together with DecisionNode in the conditions it will be used
  in, before use and after every change of model, settings or software;
- hold every certification, authorisation and insurance, and follow every law, that applies
  to the system and its operation;
- never let anyone believe that DecisionNode controls the system or is responsible for its
  safety.

DecisionNode gives no warranty that the service or any answer is suitable, safe, timely,
available or reliable for a safety-critical system, and such use is at your own risk. This
software is provided under the MIT license, without warranty of any kind.

In practice: subscribe to `decision` from your own logic, check `ok`, read `header.stamp`
to know how old the frame was, and treat a missing or stale answer as "no answer". The
[control loops guide](https://decisionnode.com/docs/patterns/control-loops) shows the
pattern.

## Quickstart (5 minutes)

You need ROS 2 Jazzy or Humble and a DecisionNode API key from the
[console](https://decisionnode.com/console).

**1. Build the packages.**

```sh
mkdir -p ~/dn_ws/src && cd ~/dn_ws/src
git clone https://github.com/Bynn-Intelligence/decision-node-ros2.git
cd ~/dn_ws
source /opt/ros/$ROS_DISTRO/setup.bash
rosdep install --from-paths src --ignore-src -y
```

The node uses the DecisionNode Python SDK, which is installed with pip:

```sh
# Jazzy (Ubuntu 24.04)
python3 -m pip install --break-system-packages "bynn-decisionnode>=0.3.2,<0.4"
# Humble (Ubuntu 22.04)
python3 -m pip install "bynn-decisionnode>=0.3.2,<0.4"
```

Then:

```sh
colcon build --packages-select decisionnode_msgs decisionnode_ros
source install/setup.bash
```

**2. Start a camera.** A USB webcam with `usb_cam`:

```sh
sudo apt install ros-$ROS_DISTRO-usb-cam
ros2 run usb_cam usb_cam_node_exe
```

Or play a recorded bag that has an image topic:

```sh
ros2 bag play my_recording --loop --remap /camera/image_raw:=/image_raw
```

**3. Run the node** in another terminal:

```sh
source ~/dn_ws/install/setup.bash
export DECISIONNODE_API_KEY=your-api-key
ros2 launch decisionnode_ros decisionnode.launch.py
```

**4. Read the decisions:**

```sh
ros2 topic echo /decision
```

You get one `decisionnode_msgs/Decision` a second, answering the three example questions
(is there a person, what hazard is in view, how many people).

## Your own questions

Copy [`config/example.yaml`](decisionnode_ros/config/example.yaml), edit it, and launch
with it:

```sh
ros2 launch decisionnode_ros decisionnode.launch.py params:=/path/to/my_params.yaml
```

Questions live under `questions`, in the order `ids` gives:

```yaml
decisionnode:
  ros__parameters:
    image_topic: /image_raw
    model: decisionnode-flash
    max_rate_hz: 2.0
    questions:
      ids: [blocked, surface, door]
      blocked:
        type: truth
        instructions: Is the path ahead blocked?
      surface:
        type: choice
        instructions: What is the floor surface ahead?
        options: [concrete, carpet, grass, gravel, wet]
      door:
        type: box
        instructions: Where is the nearest door?
```

| `type` | Fields | The answer in `Answer` |
|---|---|---|
| `truth` | `instructions` | `truth` (0 to 1) |
| `choice` | `instructions`, `options` | `choice`, with `labels` and `probabilities` |
| `score` | `instructions`, `levels` (lowest first) | `score` |
| `number` | `instructions`, optional `min`, `max`, `step` | `number` and `expected` |
| `point` | `instructions`, optional `units`, `max` | `place` as `[x, y]`, `present` |
| `box` | `instructions`, optional `units`, `max` | `place` as `[x1, y1, x2, y2]`, `present` |

With `max` above 1, `place` holds every point or box one after another, `count` says how
many, and `place_confidence` holds one confidence each. A value the answer does not carry
is `NaN`, `0` or empty. `raw_json` holds the answer exactly as the API sent it.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `image_topic` | `image` | The image topic to read. |
| `compressed` | `false` | `true` to read `sensor_msgs/CompressedImage` (JPEG, PNG or WebP), sent as it is. Otherwise `sensor_msgs/Image` in `rgb8`, `bgr8`, `rgba8`, `bgra8` or `mono8`, encoded as JPEG. |
| `state_topic` | empty | An optional `std_msgs/String` topic holding JSON, sent with every frame as the state (speed, mode, what the robot is doing). |
| `decision_topic` | `decision` | Where decisions are published. |
| `model` | `decisionnode-flash` | The model to ask. |
| `boosters` | none | Boosters to add, for example `[age]`. |
| `max_rate_hz` | `1.0` | The most decisions a second. |
| `max_in_flight` | `1` | Requests running at once. |
| `timeout_s` | `10.0` | The time one request may take. |
| `jpeg_quality` | `85` | JPEG quality for raw images. |
| `image_id` | `camera` | The image's name in the request. |
| `session_mode` | `false` | `true` to stream frames into one live session instead of one request each. |
| `session_window` | `0` | The session's window of recent frames (0: the default). |
| `api_key_file` | empty | A file holding the API key, instead of `DECISIONNODE_API_KEY`. |

### Rate limiting

Cameras send far more frames than decisions are worth asking for. The node keeps one slot
for the newest frame: a newer frame replaces a waiting one, and nothing ever queues. A frame
is sent only when fewer than `max_in_flight` requests are running and at least
`1 / max_rate_hz` seconds have passed since the last one started. Each `Decision` says in
`frames_dropped` how many frames were replaced before it.

### The API key

The key comes from the `DECISIONNODE_API_KEY` environment variable, or from the file
`api_key_file` names (keep it at mode 600). It is never a parameter's value, because
parameters can be read by anything on the ROS graph, and the node never logs it. Without a
key the node refuses to start.

## Messages

`decisionnode_msgs/Decision`:

| Field | Meaning |
|---|---|
| `header` | The frame's header: its stamp and frame id. |
| `ok` | `true` when the answers are there. |
| `answers` | One `Answer` per question, in the order of `ids`. |
| `request_id` | The request's id, for support. |
| `model` | The model that answered. |
| `latency_ms` | The time the decision took. |
| `cost_usd` | What it cost, `NaN` when not sent. |
| `error_type`, `error_message` | Why there are no answers, when `ok` is `false`. |
| `frames_dropped` | Frames replaced by newer ones before this one was sent. |

When a request fails, the node publishes a `Decision` with `ok: false` and the
`error_type` from the API (for example `insufficient_credit` or `rate_limit_error`), so your
logic always knows that no answer came.

### One decision on demand

The `decide_once` service (`decisionnode_msgs/srv/DecideOnce`) answers the configured
questions about the image you send, or about the latest frame when you send none:

```sh
ros2 service call /decide_once decisionnode_msgs/srv/DecideOnce \
  "{state_json: '{\"mode\": \"inspect\"}'}"
```

## Tests

```sh
colcon test --packages-select decisionnode_msgs decisionnode_ros
colcon test-result --verbose
```

The tests run against a local mock server and never call the API.

## Help

Documentation: [decisionnode.com/docs](https://decisionnode.com/docs). Questions and
problems: [hello@bynn.com](mailto:hello@bynn.com).

## License

MIT. See [LICENSE](LICENSE).
