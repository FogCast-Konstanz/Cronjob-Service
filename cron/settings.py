import pathlib
import json
import os

class Settings:
    def __init__(self):
        self.data_dir = None
        self.model_ids_path = None
        self.hourly_fields_path = None
        self.latitude = None
        self.longitude = None
        self.log_dir = None

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
    settings = Settings()
    for key, value in settings_json.items():
        # Convert paths to be relative to the package directory if they end in '_path' or '_dir'
        if isinstance(value, str) and (key.endswith("_path") or key.endswith("_dir")):
            value = os.path.join(project_root, value) if not os.path.isabs(value) else value
        # Set the attribute on the Settings instance if it exists
        if hasattr(settings, key):
            setattr(settings, key, value)

    return settings

# Usage
settings = load_settings()