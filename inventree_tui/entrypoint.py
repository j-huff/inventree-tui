import argparse

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

def main():
    parser = argparse.ArgumentParser(description="Inventree TUI")
    subparsers = parser.add_subparsers(dest="command", title="commands", metavar="<command>")

    # Create the "create-env" subparser
    create_env_parser = subparsers.add_parser("create-env", help="Create a .env file")
    create_env_parser.add_argument("-o", "--output-filename", default="./.env",
                                   help="Output filename for the .env file (default: ./.env)")

    # Add a default subparser for the main application
    app_parser = subparsers.add_parser("app", help="Run the Inventree TUI application")

    args = parser.parse_args()

    if args.command == "create-env":
        create_env(args)
    elif args.command == "app" or args.command is None:
        from inventree_tui.app import InventreeApp
        app = InventreeApp()
        app.run()
    else:
        parser.print_help()
