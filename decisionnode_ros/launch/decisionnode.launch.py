"""Start the decisionnode node with a params file.

    ros2 launch decisionnode_ros decisionnode.launch.py params:=/path/to/params.yaml image_topic:=/image_raw
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    example = os.path.join(get_package_share_directory("decisionnode_ros"), "config", "example.yaml")
    return LaunchDescription([
        DeclareLaunchArgument("params", default_value=example, description="The node's parameters file"),
        DeclareLaunchArgument("image_topic", default_value="/image_raw", description="The camera topic"),
        Node(
            package="decisionnode_ros",
            executable="decisionnode",
            name="decisionnode",
            output="screen",
            parameters=[LaunchConfiguration("params"), {"image_topic": LaunchConfiguration("image_topic")}],
        ),
    ])
