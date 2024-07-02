from pydantic import Field, BaseModel
from typing import Optional
import yaml
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()  # Load environment variables from .env file

class PartSearchTabSettings(BaseSettings):
    auto_expand: int = Field(5, ge=0, description="Number of items to auto-expand in the part search tab")

class StockOpsTabSettings(BaseSettings):
    history_delta_minutes: int = Field(0, ge=0, description="Minutes to look back in history")
    history_delta_hours: int = Field(8, ge=0, description="Hours to look back in history")
    history_delta_days: int = Field(0, ge=0, description="Days to look back in history")
    history_chunk_size: int = Field(10, ge=0, description="Number of history items to fetch every API call")

class Settings(BaseSettings):
    # General settings
    app_name: str = Field("InvenTree TUI", description="Name of the application")
    sound_enabled: bool = Field(False, description="Enable sound effects")
    tts_enabled: bool = Field(False, description="Enable text-to-speech")
    check_for_updates: bool = Field(True, description="Check for updates to the PyPi package on startup")

    inventree_api_host: str | None = Field(None, env="API_HOST", description="InvenTree API host URL")
    inventree_api_token: str | None = Field(None, env="API_TOKEN", description="InvenTree API token")

    # Nested settings
    part_search_tab: PartSearchTabSettings = Field(default_factory=PartSearchTabSettings, description="Settings for the part search tab")
    stock_ops_tab: StockOpsTabSettings = Field(default_factory=StockOpsTabSettings, description="Settings for the stock operations tab")

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8'
    )

    log_level: str = Field("WARNING", description="Minimum level for logging.")
    log_filename: None | str = Field(None, description="Output to log file. Disabled by default.")

    @classmethod
    def from_yaml(cls, yaml_file: str):
        with open(yaml_file, "r") as f:
            yaml_data = yaml.safe_load(f)
        return cls(**yaml_data)

# Create a global instance of the settings
settings = Settings()

def load_yaml_config(yaml_file: str):
    global settings
    settings = Settings.from_yaml(yaml_file)

def generate_default_settings(filename: str):
    # Create a default Settings instance
    default_settings = Settings()

    # Convert the settings to a dictionary
    settings_dict = default_settings.model_dump()

    # Generate YAML content with comments
    yaml_content = generate_yaml_with_inline_comments(settings_dict, default_settings)

    # Write the YAML content to a file
    with open(filename, 'w') as f:
        f.write(yaml_content)

    print(f"Default settings have been saved to {filename}")

def generate_yaml_with_inline_comments(data, obj):
    no_comments = generate_yaml_with_inline_comments_helper(data, obj, indent=0, with_comments=False)
    lines = no_comments.split('\n')
    max_max_width = 34
    max_width = 0
    for line in lines:
        if len(line) > max_max_width:
            continue
        max_width = max(len(line), max_width)

    with_comments = generate_yaml_with_inline_comments_helper(data, obj, indent=0, with_comments=True, align_comments_column=max_width)

    return with_comments

def generate_yaml_with_inline_comments_helper(data, obj, indent=0, with_comments=True, align_comments_column = 0):
    yaml_lines = []
    column = align_comments_column
    for key, value in data.items():
        comment = ""
        if with_comments and isinstance(obj, BaseModel) and key in obj.model_fields:
            field = obj.model_fields[key]
            if field.description:
                comment = f" # {field.description}"
        indent_s = f"{' ' * indent}"

        if isinstance(value, dict):
            line = f"{indent_s}{key}:"
            spacer = f"{' ' * max(0, column - len(line))}"
            yaml_lines.append(f"{line}{spacer}{comment}")
            nested_obj = getattr(obj, key, None)
            if isinstance(nested_obj, BaseModel):
                yaml_lines.append(generate_yaml_with_inline_comments_helper(value, nested_obj, indent + 2, with_comments=with_comments, align_comments_column=align_comments_column))
            else:
                yaml_lines.append(yaml.dump({key: value}, default_flow_style=False, indent=indent+2))
        else:
            if value is None:
                line = f"{indent_s}{key}: null"
            elif isinstance(value, (int, float)):
                line = f"{indent_s}{key}: {value}"
            elif isinstance(value, bool):
                line = f"{indent_s}{key}: {str(value).lower()}"
            else:
                line = f"{indent_s}{key}: '{value}'"

            spacer = f"{' ' * max(0, column - len(line))}"
            yaml_lines.append(f"{line}{spacer}{comment}")

    return '\n'.join(yaml_lines)
