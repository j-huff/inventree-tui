from setuptools import setup, find_packages

long_description = open('README.md').read()

setup(
    name="inventree-tui",
    version="0.1.5",
    packages=find_packages(),
    install_requires=["textual","inventree","pydantic", "python-dotenv"],
    entry_points={
        "console_scripts": [
            "inventree-tui = inventree_tui.entrypoint:main",
        ],
    },
    description='Terminal UI for InvenTree',
    long_description=long_description,
    long_description_content_type="text/markdown",
    package_data={
        "inventree_tui": ["*.tcss"],
    },
)
