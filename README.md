
# Inventree TUI

Terminal User Interface for Inventree, built with [Textual](https://github.com/Textualize/textual). Project maintained on [GitHub](https://github.com/j-huff/inventree-tui).

## Installation

Inventree TUI can be install via PyPi using the command `pip install inventree-tui`.

Once installed, launch the TUI using the command `python -m inventree-tui`. You will have to configure the required environment variables first (see below).

## Configuration

To run inventree-tui, you must set the following environment variables: `INVENTREE_API_HOST`, `INVENTREE_API_TOKEN`

You can also set these in a file named `.env`:

```
# .env file
INVENTREE_API_HOST=https://example.com/
INVENTREE_API_TOKEN=inv-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-xxxxxxxx
```
