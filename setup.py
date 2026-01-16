"""Setup file for Holiday Finder."""

from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="holiday-finder",
    version="1.0.0",
    description="Automatically find and rank the best holidays based on user criteria",
    author="Holiday Finder Team",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "holiday-finder=src.ui.cli:app",
        ],
    },
)
