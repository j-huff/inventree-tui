import argparse
from .settings import load_yaml_config

def create_env(args):
    import os
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
    parser = argparse.ArgumentParser(description="Inventree TUI")
    subparsers = parser.add_subparsers(dest="command", title="commands", metavar="<command>")

    # Create the "create-env" subparser
    create_env_parser = subparsers.add_parser("create-env", help="Create a .env file")
    create_env_parser.add_argument("-o", "--output-filename", default="./.env",
                                   help="Output filename for the .env file (default: ./.env)")

    # Add the "app" subparser
    app_parser = subparsers.add_parser("app", help="Run the Inventree TUI application")
    app_parser.add_argument("-c", "--config-filename", default=None, type=str)

    return parser

def main():
    parser = create_parser()
    args, unknown = parser.parse_known_args()

    if args.command == "create-env":
        create_env(args)
    else:  # Default to "app" command
        if args.command is None:
            # If no command was provided, manually set it to "app" and reparse
            args = parser.parse_args(['app'] + unknown)

        if args.config_filename is not None:
            load_yaml_config(args.config_filename)

        from inventree_tui.app import InventreeApp
        app = InventreeApp()
        app.run()
