# Cronjob Service

This repository contains a cron job service that runs regularly job to collect weather data from several sources and processes it for various use cases, including transferring data to InfluxDB and benchmarking models.

## Data Sources

Currently we collect data from these sources:
- [Open-Meteo](https://open-meteo.com/)
- [Pegel Online](https://www.pegelonline.wsv.de/gast/start)
- [DWD](https://dwd.api.bund.dev/)

## Folder Structure

- **cron-runner/**: Includes scripts and configurations for running cron jobs.
  - `bin/`: Contains Python scripts for specific tasks like fixing time, transferring CSV data, and fetching models.
  - `config/`: Stores configuration files such as `model_ids.csv` and `hourly_fields.csv`.
  - `cron/`: Contains the main cron job logic and job scheduler.
    - `jobs/`: Includes specific cron job implementations like OpenMeteo and model benchmarking.
- **cron-status/**: Contains a Flask application for monitoring the status of cron jobs.

## Features

- Fetch weather data from the OpenMeteo API.
- Transfer data to InfluxDB.
- Benchmark models using cron jobs.
- Monitor cron job status via a Flask application.

## Development Setup

- Install [Python 3.12.7](https://www.python.org/downloads/release/python-3127/).
- Use a virtual environment:
  - Create virtual env: `python -m venv venv`
  - Activate virtual env: `. venv/bin/activate (Linux/Mac)` or `./venv/Scripts/activate (Win)`
  - Deactivate virtual env: `deactivate`
- Install the project in an editable state: `pip install -e .`
- Create development settings.user.json (`cron-runner/settings.user.json`) file and add your influx credentials: 
`
{
  "influx": {
    "url": "",
    "token": "",
    "org": "",
    "bucket": ""
  }
}
`
- Build project in docker `docker-compose up -d --build`

## Configuration

The default configuration in `config/settings.json` is:

```json
{
  "latitude": 47.6952,
  "longitude": 9.1307,
  "model_ids_path": "./config/model_ids.csv",
  "hourly_fields_path": "./config/hourly_fields.csv",
  "data_dir": "./csv-data",
  "log_dir": "./logs",
  "influx": {
    "url": "http://fogcast-influxdb:8086",
    "token": "TOKEN",
    "org": "FogCast",
    "bucket": "WeatherForecast"
  },
  "discord": {
    "webhook_url": ""  
  }
}
```

You can overwrite the default config by creating a `config/settings.user.json` and overwriting single values. For example:

```json
{
  "influx": {
    "url": "http://fogcast-influxdb:8086",
    "token": "ANOTHER_TOKEN",
    "org": "FogCast",
    "bucket": "WeatherForecast"
  },
  "discord": {
    "webhook_url": "A_WEBHOOK_URL"  
  }
}
```

## Usage

### Run a Single Cronjob

Get in the docker container:
```bash
docker exec -it fogcast-cron-runner /bin/sh
```
Run the Cronjob now:
```bash
python bin/main.py run_single_job_now=<cronjob_class_name>
```



### Update Code on Remote Server

To update the code on the remote server please read adn follow these instructions: [FogCast](https://github.com/FogCast-Konstanz/FogCast)

## Detailed Description of Cron Jobs and Files

### Cron Jobs

- **OpenMeteoCronJob** (`open_meteo_cronjob.py`): Fetches weather data from the OpenMeteo API and processes it for storage or further analysis.
- **OpenMeteoCSVJob** (`open_meteo_csv_cronjob.py`): Converts weather data into CSV format for local storage.
- **OpenMeteoInfluxJob** (`open_meteo_influx_cronjob.py`): Transfers weather data to an InfluxDB instance for real-time monitoring and analysis.
- **BenchmarkingCronJob** (`benchmarking_cronjob.py`): Benchmarks weather models by comparing their predictions against actual data.
- **PegelOnlineCronjob** (`pegel_online_cronjob.py`): Fetches the water levels of Lake of Constance and Seerhein from Pegel Online and DWD.

### Key Files

#### `cron-runner/bin/`
- **`main.py`**: Entry point for running cron jobs and managing their execution.
- **`fix_time.py`**: Utility used to go from local time to UTC in the directory structure.
- **`get_model_with_no_data_for_location.py`**: Identifies models that lack data for specific locations.
- **`get_models_with_ids.py`**: Fetches model ids based on their name and stores them in the `model_ids.csv` file.
- **`transfer_csv_to_influx.py`**: Transfers CSV data to an InfluxDB instance.

#### `cron-runner/config/`
- **`model_ids.csv`**: Contains identifiers for weather models.
- **`hourly_fields.csv`**: Specifies hourly data fields to be fetched from the API.

#### `cron/jobs/`
- **`cronjob_base.py`**: Base class for all cron jobs, providing shared functionality.
- **`toDataFrame.py`**: Utility for converting raw data into pandas DataFrames for easier manipulation.

#### `cron-status/`
- **`app.py`**: Flask application for monitoring the status of cron jobs.
- **`wsgi.py`**: Entry point for deploying the Flask application.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License.

## Future Work
- **Backup**: Server and all the data should be backuped regularly.
- **Solar Log Data**: Save the SolarLog Data via Cronjob to the database.
