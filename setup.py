import setuptools

from mautrix import __version__

test_dependencies = ["aiosqlite", "sqlalchemy", "asyncpg"]

setuptools.setup(
    name="mautrix",
    version=__version__,
    url="https://github.com/mautrix/python",

    author="Tulir Asokan",
    author_email="tulir@maunium.net",

    description="A Python 3 asyncio Matrix framework.",
    long_description=open("README.rst").read(),

    packages=setuptools.find_packages(),

    install_requires=[
        "aiohttp>=3,<4",
        "attrs>=18.1.0",
        "yarl>=1,<2",
    ],
    extras_require={
        "detect_mimetype": ["python-magic>=0.4.15,<0.5"],
        "lint": ["black==21.12b0", "isort"],
        "test": ["pytest", "pytest-asyncio", *test_dependencies],
        ':python_version < "3.8"': ["typing_extensions"],
    },
    tests_require=test_dependencies,
    python_requires="~=3.7",

    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Topic :: Communications :: Chat",
        "Framework :: AsyncIO",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],

    package_data={
        "mautrix": ["py.typed"],
        "mautrix.types.event": ["type.pyi"],
        "mautrix.util": ["opt_prometheus.pyi"],
        "mautrix.util.formatter": ["html_reader.pyi"],
    },
)
