import os
import subprocess

from setuptools.command.bdist_wheel import bdist_wheel
from setuptools.command.build_py import build_py
import setuptools

from mautrix import __version__

encryption_dependencies = ["unpaddedbase64", "pycryptodome"]
test_dependencies = ["aiosqlite", "asyncpg", "ruamel.yaml", *encryption_dependencies]


class BuildPyWithGo(build_py):
    def run(self) -> None:
        subprocess.run(
            ["go", "build", "-buildmode=c-shared", "-o", os.path.abspath("mautrix/libgothon.so")],
            cwd="gothon",
            check=True,
        )
        super().run()


class PlatformWheel(bdist_wheel):
    def finalize_options(self) -> None:
        super().finalize_options()
        self.root_is_pure = False

    def get_tag(self) -> tuple[str, str, str]:
        _, _, platform = super().get_tag()
        return "py3", "none", platform


setuptools.setup(
    name="mautrix",
    version=__version__,
    url="https://github.com/mautrix/python",
    project_urls={
        "Changelog": "https://github.com/mautrix/python/blob/master/CHANGELOG.md",
    },

    author="Tulir Asokan",
    author_email="tulir@maunium.net",

    description="A Python 3 asyncio Matrix framework.",
    long_description=open("README.rst").read(),

    packages=setuptools.find_packages(),

    install_requires=[
        "aiohttp>=3,<4",
        "attrs>=18.1.0",
        "yarl>=1.5,<2",
    ],
    extras_require={
        "detect_mimetype": ["python-magic>=0.4.15,<0.5"],
        "lint": ["black~=25.1", "isort"],
        "test": ["pytest", "pytest-asyncio", *test_dependencies],
        "encryption": encryption_dependencies,
    },
    tests_require=test_dependencies,
    python_requires="~=3.10",

    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Topic :: Communications :: Chat",
        "Framework :: AsyncIO",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],

    package_data={
        "mautrix": ["py.typed", "libgothon.so"],
        "mautrix.types.event": ["type.pyi"],
        "mautrix.util": ["opt_prometheus.pyi", "variation_selector.json"],
        "mautrix.util.formatter": ["html_reader.pyi"],
    },
    cmdclass={"build_py": BuildPyWithGo, "bdist_wheel": PlatformWheel},
)
