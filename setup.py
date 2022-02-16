from importlib_metadata import entry_points
from setuptools import setup


with open("requirements.txt", encoding="utf-8") as f:
    requires = [x.strip() for x in f if x.strip()]


setup(
    name="colabond",
    version="0.1.1",
    author="Aria Ghora Prabono",
    author_email="hello@ghora.net",
    description="Colabond command-line tool",
    license="MIT",
    packages=["colabond"],
    install_requires=requires,
    entry_points={
        "console_scripts": [
            "colabond = colabond.colabond:main",
        ]
    },
)
