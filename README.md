# Cronjob Service

A comprehensive weather data collection and processing service that runs scheduled jobs to gather meteorological data from multiple sources, process it, and store it in InfluxDB for analysis and visualization. The service includes model benchmarking capabilities and water level monitoring.

## Data Sources

The service collects data from the following sources:
- **[Open-Meteo](https://open-meteo.com/)**: Weather forecast data from different weather models
- **[Pegel Online](https://www.pegelonline.wsv.de/gast/start)**: Water level measurements from German waterways
- **[DWD](https://dwd.api.bund.dev/)**: German Weather Service data

## Repository Structure

```
Cronjob-Service/
├── compose.yaml                 # Docker Compose configuration
├── cron-runner/                 # Main application directory
│   ├── bin/                     # Command-line utilities
│   │   ├── main.py             # Main entry point for cron jobs
│   │   ├── transfer_csv_to_influx.py
│   │   ├── get_model_with_no_data_for_location.py
│   │   └── fix_time.py
│   ├── config/                  # Configuration files
│   │   ├── models.csv       # Weather model identifiers
│   │   └── hourly_fields.csv   # Data fields configuration
│   ├── cron/                   # Core cron job system
│   │   ├── settings.py         # Settings management
│   │   ├── settings_utils.py   # Type-safe settings utilities
│   │   ├── job_scheduler.py    # Job scheduling and execution
│   │   └── jobs/               # Individual job implementations
│   │       ├── cronjob_base.py
│   │       ├── open_meteo/     # OpenMeteo data collection
│   │       ├── model_benchmarking/  # Model performance analysis
│   │       └── water_level/    # Water level monitoring
│   └── pyproject.toml          # Python package configuration
├── cron-status/                # Status monitoring service
│   ├── app.py                  # Flask monitoring application
│   └── Dockerfile
```

## Features

### Core Functionality
- **Multi-source Data Collection**: Automated data collection from OpenMeteo, Pegel Online, and DWD
- **InfluxDB Integration**: Storage of the collected data in a time-series database for easy and fast access.
- **CSV Export**: Local data storage in structured CSV format
- **Model Benchmarking**: Automated performance analysis of weather prediction models
- **Water Level Monitoring**: Lake Constance and Rhein water level tracking

## Quick Start

### Prerequisites
- **Python 3.12.7+**
- **Docker & Docker Compose**
- **InfluxDB instance** (local or remote)

### Development Setup for the cronjobs

1. **Clone and Setup Environment**
```bash
git clone https://github.com/FogCast-Konstanz/Cronjob-Service.git
cd Cronjob-Service/cron-runner
python -m venv venv
source venv/bin/activate  # Linux/Mac
# .\venv\Scripts\activate  # Windows
```

2. **Install Dependencies**
```bash
cd cron-runner
pip install -e .  # Installs package in editable mode
```

3. **Configure Settings**
Create `cron-runner/settings.user.json`:
```json
{
  "influx": {
    "url": "http://your-influxdb:8086",
    "token": "your-influxdb-token",
    "org": "your-org",
    "bucket": "your-bucket"
  },
  "latitude": 47.6952,
  "longitude": 9.1307,
  "discord": {
    "webhook_url": "your-discord-webhook"
  }
}
```

4. **Build and Run with Docker**
```bash
docker compose build
docker compose up -d 
```

## Configuration

### Settings Architecture

The system uses a hierarchical configuration system:

1. **Default Settings** (`cron-runner/settings.json`): Base configuration
2. **User Overrides** (`settings.user.json`): User-specific settings

### Default Configuration

```json
{
  "latitude": 47.6952,
  "longitude": 9.1307,
  "models_path": "./config/models.csv",
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

### Configuration Override Examples
```json
{
  "latitude": 48.7758,
  "longitude": 9.1829,
  "influx": {
    "url": "https://my-influxdb.com:8086",
    "token": "my-production-token"
  }
}
```

## Usage

### Command Line Tools

All tools are available as console commands after installation:

```bash
# Main cron job scheduler
cron-main

# Data transfer utilities
transfer-csv-to-influx
get-model-with-no-data-for-location
fix-time
```

### Running Individual Jobs

#### Via Docker
```bash
# Enter container
docker exec -it fogcast-cron-runner /bin/sh

# Run specific job
python bin/main.py run_single_job_now=OpenMeteoCronjob
python bin/main.py run_single_job_now=BenchmarkingCronjob
python bin/main.py run_single_job_now=PegelOnlineCronjob
```

#### Direct Execution
```bash
cd cron-runner
python bin/main.py run_single_job_now=OpenMeteoInfluxCronjob
```

### Scheduled Execution

The job scheduler runs automatically with these intervals:
- Every 60 minutes:
    - OpenMeteoCsvCronjob
    - OpenMeteoInfluxCronjob
    - BenchmarkingCronjob
- Every Day:
    - PegelOnlineCronjob

## Development

### Adding New Jobs

1. **Create Job Class**
```python
from cron.jobs.cronjob_base import CronjobBase

class MyCustomCronjob(CronjobBase):
    def start(self, local_dt: datetime) -> bool:
        return True

    def cleanUpAfterError(self):
        pass
```

2. **Register in Scheduler**
```python
# In job_scheduler.py
_job_config: Dict[int, List[Type[CronjobBase]]] = {
    MINUTES_5: [
        # Jobs that run every 5 minutes
    ],
    MINUTES_60: [
        # Jobs that run every hour
        OpenMeteoCsvCronjob,
        OpenMeteoInfluxCronjob,
        BenchmarkingCronjob
    ],
    MINUTES_1440: [
        # Jobs that run daily
        PegelOnlineCronjob,
    ],
}
```

### Testing

```bash
# Test job execution
python bin/main.py run_single_job_now=MyCustomCronjob
```

## Docker Deployment

### Services
- **cron-runner**: Main application container
- **cron-status**: Monitoring dashboard
- **InfluxDB**: Time-series database (external)

### Volume Mounts

The OpenMeteoCsvCronjob stores the collected data in csv files located in a directory that is mapped to the hosts filesystem. We decided to call this directory `csv-data`.

```yaml
volumes:
    - type: bind
      source: ./csv-data
      target: /app/csv-data
    - type: bind
      source: ./cron-logs
      target: /app/logs
```

## Future Enhancements

### Planned Features
- **Solar Log Integration**: Automated solar data collection
- **Advanced Analytics**: ML-based forecast accuracy prediction
- **Real-time Alerting**: Discord/Slack notifications for anomalies

### Infrastructure
- **Automated Backups**: Regular data and configuration backups

---

**Note**: This service is part of the larger FogCast weather prediction system. For deployment instructions and integration details, refer to the main FogCast repository.
