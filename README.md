# Cronjob Service

This repository contains a cron job service that fetches weather data from the OpenMeteo API.


## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License.

## Development Setup

- Install [python 3.12.7](https://www.python.org/downloads/release/python-3127/) 

- Use a virtual environment
   - Create virtual env
      - `python -m venv venv`
   - Activate virtual env
      - `. venv/bin/activate (Linux) or ./venv/Scripts/activate (Win)`
   - Deactivate virtual env
      - `deactivate`

- Install the project in an editable state `pip install -e .`

## Transfer data from local to remote

`scp <local_file_path> weatherForecast@141.37.176.3:~/<remote_dir_path>`