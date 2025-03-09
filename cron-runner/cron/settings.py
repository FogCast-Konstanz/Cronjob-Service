import pathlib
import json
import os

class Settings:
    def __init__(self, **entries):
        for key, value in entries.items():
            # If the value is a dictionary, create a nested Settings instance
            if isinstance(value, dict):
                value = Settings(**value)
            setattr(self, key, value)

    def __repr__(self):
        return f"<Settings {self.__dict__}>"

def load_settings():
    file_dir = pathlib.Path(__file__).parent
    project_root = file_dir.parent.resolve()
    
    # Load default settings from settings.json
    settings_path = project_root / "settings.json"
    with open(settings_path, "r") as f:
        settings_json = json.load(f)

    # Check if settings.user.json exists and load it if it does
    user_settings_path = project_root / "settings.user.json"
    if os.path.exists(user_settings_path):
        with open(user_settings_path, "r") as f:
            user_settings = json.load(f)

        # Merge user settings, overriding defaults where necessary
        settings_json.update(user_settings)

    # Convert paths to be relative to the root of the repository
    def convert_paths(obj):
        for key, value in obj.items():
            if isinstance(value, str) and (key.endswith("_path") or key.endswith("_dir")):
                obj[key] = os.path.join(project_root, value) if not os.path.isabs(value) else value
            elif isinstance(value, dict):
                convert_paths(value)
    
    convert_paths(settings_json)

    # Return a Settings instance initialized with the JSON data
    return Settings(**settings_json)

# Usage
settings = load_settings()
