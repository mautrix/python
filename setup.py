import setuptools
import os

path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "mautrix", "__meta__.py")
__version__ = "UNKNOWN"
with open(path) as f:
    exec(f.read())

setuptools.setup(
    name="mautrix",
    version=__version__,
    url="https://github.com/tulir/mautrix-python/tree/matrix-restructure",

    author="Tulir Asokan",
    author_email="tulir@maunium.net",

    description="A Python 3 asyncio Matrix framework.",
    long_description=open("README.rst").read(),

    packages=setuptools.find_packages(),

    install_requires=[
        "aiohttp>=3.0.1,<4",
        "attrs>=18.1.0",
    ],
    extras_require={
        "detect_mimetype": ["python-magic>=0.4.15,<0.5"],
    },
    python_requires="~=3.6",

    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Topic :: Communications :: Chat",
        "Framework :: AsyncIO",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ]
)
