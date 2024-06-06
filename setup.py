from setuptools import setup, find_packages

long_description = open('README.md').read()

setup(
    name="inventree-tui",
    version="0.1.2",
    packages=find_packages(),
    install_requires=["textual","inventree","pydantic", "python-dotenv"],
    entry_points={
        "console_scripts": [
            "inventree-tui = inventree_tui.app:InventreeApp.run",
        ],
    },
    description='Terminal UI for InvenTree',
    long_description=long_description,
    long_description_content_type="text/markdown"
)
