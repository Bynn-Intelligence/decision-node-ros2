^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Changelog for package decisionnode_ros
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Forthcoming
-----------
* Boosters with settings: an entry of ``boosters`` may be a JSON object in the API's form, such as ``{"name": "bynn_segment", "options": {"prompt": ["purple gate"]}}``, beside a booster's name.
* The boosters' readings are published in ``Decision.evidence_json``, exactly as the API sent them.
* The README shows Depth Vision (``bynn_depth``) and Segment Vision (``bynn_segment``) for robots and drones.
* ``boosters`` with ``session_mode`` refuse to start: a live session takes no boosters.
* Knowledge: the ``knowledge.`` parameters (``collection``, ``scope``, ``top_k``, ``require``, ``query``, ``max_tokens``, ``pinned``, ``min_score``, ``match``, ``filter``, ``include_text``, ``timeout_ms``) send the ``knowledge`` booster with every request, so each decision is given the passages of your own documents that apply to it. Its reading, with the cited passages, comes back in ``Decision.evidence_json`` under ``knowledge``.
* The ``knowledge.`` parameters can change while the node runs (``ros2 param set``), for a new mission or another robot model; a change that cannot be sent is refused and the node keeps the one it had.
* The README shows an operating manual scoped by robot model.

0.1.1 (2026-10-13)
------------------
* A node whose start fails (no API key, a bad question) shuts down cleanly on newer rclpy, which destroys such a node with its context.
* Where the DecisionNode Python SDK is not installed, the tests that need it are skipped without failing collection on any distribution.
* Rolling is built and tested beside Jazzy and Humble.

0.1.0 (2026-10-13)
------------------
* First release: the ``decisionnode`` node asks the questions in its parameters about the frames on an image topic and publishes ``decisionnode_msgs/Decision``.
* Rate limited: the newest frame wins, at most ``max_rate_hz`` decisions a second and ``max_in_flight`` requests, nothing queues.
* An optional live session mode and the ``decide_once`` service.
* The API key from ``DECISIONNODE_API_KEY`` or ``api_key_file``, never a parameter's value, never logged.
* A launch file and example parameters; ROS 2 Jazzy and Humble.
