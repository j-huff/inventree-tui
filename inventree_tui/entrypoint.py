import argparse
import os
import sys
from .settings import load_yaml_config, generate_default_settings

def create_env(args):
    env_file = args.output_filename
    if os.path.exists(env_file):
        raise FileExistsError(f"The {env_file} file already exists.")

    inventree_api_host = input("Enter the value for INVENTREE_API_HOST: ")
    inventree_api_token = input("Enter the value for INVENTREE_API_TOKEN: ")

    with open(env_file, "w") as file:
        file.write(f"INVENTREE_API_HOST={inventree_api_host}\n")
        file.write(f"INVENTREE_API_TOKEN={inventree_api_token}\n")

    print(f"The {env_file} file has been created successfully.")

def create_parser():
    parser = argparse.ArgumentParser(
        description="Inventree TUI - A Text User Interface for InvenTree",
        epilog="For more information, visit https://inventree.readthedocs.io/"
    )
    subparsers = parser.add_subparsers(dest="command", title="commands", metavar="<command>")

    # Create the "create-env" subparser
    create_env_parser = subparsers.add_parser(
        "create-env",
        help="Create a .env file with environment variables",
        description="Generate a .env file with placeholder values for InvenTree API configuration."
    )
    create_env_parser.add_argument(
        "-o", "--output-filename",
        default="./.env",
        help="Specify the output filename for the .env file (default: ./.env)"
    )

    # Add the "app" subparser
    app_parser = subparsers.add_parser(
        "app",
        help="Run the Inventree TUI application",
        description="Launch the main Inventree Text User Interface application."
    )
    app_parser.add_argument(
        "-c", "--config-filename",
        default=None,
        type=str,
        help="Specify a custom configuration file to use (default: None, uses built-in defaults)"
    )

    # Add the "generate-config" subparser
    generate_config_parser = subparsers.add_parser(
        "generate-config",
        help="Generate a default configuration file",
        description="Create a YAML configuration file with default settings for the Inventree TUI."
    )
    generate_config_parser.add_argument(
        "-o", "--output-filename",
        default="config.yaml",
        help="Specify the output filename for the configuration file (default: config.yaml)"
    )

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "create-env":
        create_env(args)
    elif args.command == "generate-config":
        generate_config(args)
    else:  # Default to "app" command
        if args.command is None:
            # If no command was provided, manually set it to "app" and reparse
            args = parser.parse_args(['app'] + sys.argv[1:])

        if args.config_filename is not None:
            load_yaml_config(args.config_filename)

        from inventree_tui.app import InventreeApp
        app = InventreeApp()
        app.run()

def generate_config(args):
    filename = args.output_filename
    if os.path.exists(filename):
        overwrite = input(f"The file {filename} already exists. Overwrite? (y/N): ").lower().strip()
        if overwrite != 'y':
            print("Config generation cancelled.")
            return

    generate_default_settings(filename)
