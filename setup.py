from setuptools import setup, find_packages

setup(
    name="inventree-tui",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["textual"],
    entry_points={
        "console_scripts": [
            "inventree-tui = inventree_tui.app:InventreeApp.run",
        ],
    },
)
