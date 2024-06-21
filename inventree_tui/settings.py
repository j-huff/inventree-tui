from pydantic import Field
from typing import Optional
import yaml
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()  # Load environment variables from .env file

class Settings(BaseSettings):
    # General settings
    app_name: str = Field("InvenTree TUI")
    sound_enabled: bool = Field(False)
    tts_enabled: bool = Field(False)

    inventree_api_host: str | None = Field(None, env="API_HOST")
    inventree_api_token: str | None = Field(None, env="API_TOKEN")

    model_config = SettingsConfigDict(
        env_prefix='INVENTREE_',
        env_file='.env',
        env_file_encoding='utf-8',
    )

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

# Usage example
if __name__ == "__main__":
    print(f"Current settings: {settings.dict()}")
    # Load from YAML file
    load_yaml_config("config.yaml")
    print(f"Settings after loading YAML: {settings.dict()}")
