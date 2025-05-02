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
      - `. venv/bin/activate (Linux) or ./venv/Scripts/activate (Win) or source ./venv/bin/activate (Mac)`
   - Deactivate virtual env
      - `deactivate`

- Install the project in an editable state `pip install -e .`

## Transfer data from local to remote (Not needed anymore)

`scp <local_file_path> weatherForecast@141.37.176.3:~/<remote_dir_path>`


## Update the code on the remote server

- SSH into the remote server
- Go to the project directory `cd /home/weatherForecast/Cronjob-Service`
- Fetch and pull the latest changes `git fetch & git pull`


## Configuration

The default configuration in `config/settings.json` is:

```json
{
  "latitude" : 47.6952,
  "longitude" : 9.1307,
  "model_ids_path" : "./config/model_ids.csv",
  "hourly_fields_path" : "./config/hourly_fields.csv",
  "data_dir" : "./data"
}
```

All fields that end on `_path` or `_dir` will be treated as paths.
If a path is relative, it will be relative to the root of the project.
So on the server they will be relative to `/home/weatherForecast/Cronjob-Service`.

You can overwrite the default config by creating a `config/settings.user.json` and overwriting the single values.
The `settings.user.json` is ignored by git.

If you e.g. want to change the path where the results are located, create a `config/settings.user.json` with the contents:

```json
{
  "data_dir" : "<CUSTOM_PATH>"
}
```