from setuptools import setup, find_packages

import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = "\n" + f.read()

open_api_packages = [f"carbon_sdk_client.{package}"
                     for package in find_packages(where="carbon_sdk_client", exclude=["test", "tests"])]


if __name__ == "__main__":
    setup(
        name="vessim",
        use_scm_version=True,
        author="Philipp Wiesner",
        author_email="wiesner@tu-berlin.de",
        description="A simulator for virtualized energy systems",
        # long_description=long_description,
        # long_description_content_type='text/markdown',
        # keywords=["carbon awareness", "federated learning", "client selection", "flower"],
        url="https://github.com/dos-group/vessim",
        packages=[],
        # license="MIT",
        python_requires=">=3.7",
        setup_requires=['setuptools_scm'],
        install_requires=[
            # TODO
        ],
        classifiers=[
            # TODO
        ],
    )
