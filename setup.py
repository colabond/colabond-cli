from importlib_metadata import entry_points
from setuptools import setup

setup(
    name="colabond",
    version="0.1.0",
    author="Aria Ghora Prabono",
    author_email="hello@ghora.net",
    description="Colabond command-line tool",
    license="MIT",
    py_modules=["colabond", "fileutil"],
    entry_points={
        "console_scripts": [
            "colabond = colabond:main",
        ]
    },
)
