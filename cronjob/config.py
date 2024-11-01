#!/usr/bin/python3

import pathlib

_package_dir = pathlib.Path(__package__).parent.resolve()

config_dir = _package_dir / "config"
data_dir = _package_dir / "data"

model_ids_path = config_dir / "models.csv"
hourly_fields_path = config_dir / "hourly_fields.csv"