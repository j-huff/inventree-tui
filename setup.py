from setuptools import setup, find_packages
try:
    import pypandoc
    long_description = pypandoc.convert_file('README.md', 'rst')
except(IOError, ImportError):
    long_description = open('README.md').read()

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
    description='Terminal UI for InvenTree',
    long_description=long_description,
)
