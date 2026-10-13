^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Changelog for package decisionnode_ros
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
