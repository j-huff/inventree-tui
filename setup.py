from setuptools import setup, find_packages

long_description = open("README.md").read()

setup(
    name="inventree-tui",
    version="0.2.1",
    auther="John Huff",
    description="Terminal UI for InvenTree",
    url='https://github.com/j-huff/inventree-tui',
    packages=find_packages(),
    install_requires=[
        "textual",
        "inventree>=0.14.0",
        "pydantic",
        "pydantic-settings",
        "python-dotenv",
        "textual-autocomplete==2.1.0b0",
        "fuzzywuzzy",
        "setuptools",
        "httpx",
        "numpy",
        "wave",
        "pygame",
        "gTTS",
        "PyYAML"
    ],
    entry_points={
        "console_scripts": [
            "inventree-tui = inventree_tui.entrypoint:main",
        ],
    },
    long_description=long_description,
    long_description_content_type="text/markdown",
    package_data={
        "inventree_tui": ["*.tcss"],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
