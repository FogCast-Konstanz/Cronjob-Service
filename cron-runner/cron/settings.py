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

def merge_dict(default, override):
    for key, value in override.items():
        if key in default and isinstance(default[key], dict) and isinstance(value, dict):
            merge_dict(default[key], value)
        else:
            default[key] = value

def convert_paths(obj, project_root):
    for key, value in obj.items():
        if isinstance(value, str) and (key.endswith("_path") or key.endswith("_dir")):
            obj[key] = os.path.join(project_root, value) if not os.path.isabs(value) else value
        elif isinstance(value, dict):
            convert_paths(value, project_root)

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

        # Merge user settings, overriding defaults where necessary using recursive merge
        merge_dict(settings_json, user_settings)

    # Convert paths to be relative to the root of the repository
    convert_paths(settings_json, project_root)

    # Return a Settings instance initialized with the JSON data
    return Settings(**settings_json)

# Usage
settings = load_settings()
