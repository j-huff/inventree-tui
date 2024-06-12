
# InvenTree TUI Development Tips

## Tips

Its suggested to do all development in a python virtual environment.

You can using `pip install -e .` to install the project in editable mode.

To view the logs live, run `textual console` in a different terminal. Running InvenIree TUI with the command `textual run --dev inventree_tui.__main__:main` will then connect to the Textual Development Console. Use `logging.info()`, `logging.error()`, etc to log messages.

## Design Philosophy

Whenever possible, the UI should be design to be usable both with and without a keyboard; It should be possible to use InvenTree TUI on a touchscreen device without a keyboard, or from a desktop with no mouse.
