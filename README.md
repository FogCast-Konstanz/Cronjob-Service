# Cronjob Service

A comprehensive weather data collection and processing service that runs scheduled jobs to gather meteorological data from multiple sources, process it, and store it in InfluxDB for analysis and visualization. The service includes model benchmarking capabilities and water level monitoring.

## 🌤️ Data Sources

The service collects data from the following sources:
- **[Open-Meteo](https://open-meteo.com/)**: Weather forecast data from 35+ weather models
- **[Pegel Online](https://www.pegelonline.wsv.de/gast/start)**: Water level measurements from German waterways
- **[DWD](https://dwd.api.bund.dev/)**: German Weather Service data

## 📁 Repository Structure

```
Cronjob-Service/
├── compose.yaml                 # Docker Compose configuration
├── cron-logs/                   # Cron execution logs
├── cron-runner/                 # Main application directory
│   ├── bin/                     # Command-line utilities
│   │   ├── main.py             # Main entry point for cron jobs
│   │   ├── transfer_csv_to_influx.py
│   │   ├── get_models_with_ids.py
│   │   ├── get_model_with_no_data_for_location.py
│   │   └── fix_time.py
│   ├── config/                  # Configuration files
│   │   ├── model_ids.csv       # Weather model identifiers
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
│   ├── csv-data/               # Local CSV data storage
│   ├── logs/                   # Application logs
│   └── pyproject.toml          # Python package configuration
├── cron-status/                # Status monitoring service
│   ├── app.py                  # Flask monitoring application
│   └── Dockerfile
└── csv-data/                   # Shared CSV data directory
```

## ✨ Features

### Core Functionality
- **Multi-source Data Collection**: Automated fetching from OpenMeteo, Pegel Online, and DWD
- **InfluxDB Integration**: Real-time data storage and time-series management
- **CSV Export**: Local data storage in structured CSV format
- **Model Benchmarking**: Automated performance analysis of weather prediction models
- **Water Level Monitoring**: Lake Constance and Rhein water level tracking

### System Architecture
- **Type-safe Configuration**: Modern settings management with validation
- **Robust Error Handling**: Comprehensive error recovery and logging
- **Docker Deployment**: Containerized services with Docker Compose
- **Scalable Design**: Modular job system for easy extension
- **Monitoring Dashboard**: Real-time status monitoring via Flask application

### Supported Weather Models (35+)
- **ECMWF**: IFS04, IFS025, AIFS025
- **NOAA**: GFS Global, GFS Seamless, GFS GraphCast025
- **DWD**: ICON Global, ICON EU, ICON D2, ICON Seamless
- **MeteoFrance**: AROME, ARPEGE World/Europe
- **UKMO**: Global Deterministic, UK Deterministic 2km
- **JMA**: GSM, MSM, Seamless
- **And many more...**

## 🚀 Quick Start

### Prerequisites
- **Python 3.12.7+**
- **Docker & Docker Compose**
- **InfluxDB instance** (local or remote)

### Development Setup

1. **Clone and Setup Environment**
```bash
git clone <repository-url>
cd Cronjob-Service/cron-runner
python -m venv venv
source venv/bin/activate  # Linux/Mac
# .\venv\Scripts\activate  # Windows
```

2. **Install Dependencies**
```bash
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
docker-compose up -d --build
```

## ⚙️ Configuration

### Settings Architecture

The system uses a hierarchical configuration system:

1. **Default Settings** (`cron/settings.json`): Base configuration
2. **User Overrides** (`settings.user.json`): Environment-specific settings
3. **Settings Utils** (`cron/settings_utils.py`): Type-safe access layer

### Default Configuration
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

## 🔧 Usage

### Command Line Tools

All tools are available as console commands after installation:

```bash
# Main cron job scheduler
cron-main

# Data transfer utilities
transfer-csv-to-influx
get-models-with-ids
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
- **OpenMeteoCronjob**: Every 5 minutes
- **BenchmarkingCronjob**: Every 60 minutes  
- **PegelOnlineCronjob**: Every 1440 minutes (daily)

## 📊 Job Descriptions

### Data Collection Jobs

#### **OpenMeteoCronjob**
- **Purpose**: Fetches weather forecast data from OpenMeteo API
- **Frequency**: Every 5 minutes
- **Output**: Raw weather data for all configured models
- **Storage**: CSV files and/or InfluxDB

#### **OpenMeteoCSVCronjob**
- **Purpose**: Processes and stores weather data as CSV files
- **Features**: Structured data export, timestamp management
- **Storage**: `csv-data/` directory with timestamped folders

#### **OpenMeteoInfluxCronjob**
- **Purpose**: Transfers weather data directly to InfluxDB
- **Features**: Real-time data streaming, optimized batch writes
- **Storage**: InfluxDB time-series database

### Analysis Jobs

#### **BenchmarkingCronjob**
- **Purpose**: Evaluates weather model prediction accuracy
- **Metrics**: MAE, MSE, RMSE for different weather parameters
- **Timeframes**: 
  - Short-term (24 hours): 35 models
  - Medium-term (3 days): 23 models  
  - Long-term (7 days): 17 models
- **Output**: Performance scores in InfluxDB

#### **PegelOnlineCronjob**
- **Purpose**: Monitors water levels at measurement stations
- **Locations**: Konstanz Rhein, Konstanz Bodensee
- **Frequency**: Daily updates
- **Storage**: InfluxDB with station metadata

## 🛠️ Development

### Code Architecture

#### **Modern Python Packaging**
- Uses `pyproject.toml` for dependency management
- Editable installation with `pip install -e .`
- Console scripts for all utilities

#### **Type-Safe Configuration**
```python
from cron.settings_utils import get_influx_config, get_coordinates

# Type-safe access
influx_config = get_influx_config()
client = InfluxDBClient(url=influx_config["url"])

latitude, longitude = get_coordinates()
```

#### **Robust Error Handling**
- Comprehensive exception handling
- Detailed logging and monitoring
- Graceful degradation on service failures

#### **Modular Design**
- Base classes for extensibility (`CronjobBase`)
- Plugin-style job architecture
- Separation of concerns

### Adding New Jobs

1. **Create Job Class**
```python
from cron.jobs.cronjob_base import CronjobBase

class MyCustomCronjob(CronjobBase):
    def start(self, local_dt: datetime) -> bool:
        # Implementation
        return True
    
    def cleanUpAfterError(self):
        # Cleanup logic
        pass
```

2. **Register in Scheduler**
```python
# In job_scheduler.py
self.jobs = [
    (MyCustomCronjob(), 15),  # Run every 15 minutes
    # ... other jobs
]
```

### Testing

```bash
# Test imports
python -c "from cron.jobs.open_meteo.open_meteo_cronjob import OpenMeteoCronjob"

# Test job execution
python bin/main.py run_single_job_now=MyCustomCronjob
```

## 🐳 Docker Deployment

### Services
- **cron-runner**: Main application container
- **cron-status**: Monitoring dashboard
- **InfluxDB**: Time-series database (external)

### Environment Variables
```yaml
environment:
  - PYTHONPATH=/app
  - TZ=UTC
```

### Volume Mounts
```yaml
volumes:
  - ./csv-data:/app/csv-data
  - ./cron-logs:/app/logs
```

## 📈 Monitoring

### Status Dashboard
Access at `http://localhost:5001` (cron-status service)

### Logs
- **Application Logs**: `cron-runner/logs/`
- **Cron Logs**: `cron-logs/`
- **Container Logs**: `docker logs fogcast-cron-runner`

### Health Checks
```bash
# Check service status
docker ps

# View recent logs
docker logs --tail 100 fogcast-cron-runner

# Execute commands in container
docker exec -it fogcast-cron-runner python bin/main.py --help
```

## 🔄 Data Flow

1. **Collection**: Jobs fetch data from external APIs
2. **Processing**: Data transformation and validation
3. **Storage**: Dual storage in CSV files and InfluxDB
4. **Analysis**: Benchmarking and quality assessment
5. **Monitoring**: Real-time status and alerting

## 🤝 Contributing

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/amazing-feature`
3. **Follow code style**: Use type hints and proper error handling
4. **Add tests**: Test new job implementations
5. **Submit pull request**: Include detailed description

### Code Style
- Python 3.12+ features
- Type hints for all functions
- Comprehensive error handling
- Detailed logging

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🚧 Future Enhancements

### Planned Features
- **Solar Log Integration**: Automated solar data collection
- **Advanced Analytics**: ML-based forecast accuracy prediction
- **API Gateway**: RESTful API for data access
- **Real-time Alerting**: Discord/Slack notifications for anomalies

### Infrastructure
- **Automated Backups**: Regular data and configuration backups
- **High Availability**: Multi-instance deployment
- **Performance Optimization**: Caching and batch processing improvements
- **Security Hardening**: Authentication and authorization

## 📞 Support

For issues, questions, or contributions:
- **GitHub Issues**: [Repository Issues](https://github.com/FogCast-Konstanz/Cronjob-Service/issues)
- **Documentation**: [FogCast Main Repository](https://github.com/FogCast-Konstanz/FogCast)

---

**Note**: This service is part of the larger FogCast weather prediction system. For deployment instructions and integration details, refer to the main FogCast repository.
