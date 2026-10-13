from glob import glob

from setuptools import find_packages, setup

package_name = "decisionnode_ros"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Bynn Intelligence, Inc.",
    maintainer_email="hello@bynn.com",
    description="DecisionNode for ROS 2. DecisionNode is a decision engine.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={"console_scripts": ["decisionnode = decisionnode_ros.node:main"]},
)
