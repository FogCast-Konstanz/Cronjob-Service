import os
import logging
from datetime import datetime, timezone
from typing import List, Type, Optional, Dict

from discord import SyncWebhook

from cron.jobs.cronjob_base import CronjobBase
from cron.jobs.open_meteo.open_meteo_csv_cronjob import OpenMeteoCsvCronjob
from cron.jobs.open_meteo.open_meteo_influx_cronjob import OpenMeteoInfluxCronjob
from cron.jobs.water_level.pegel_online_cronjob import PegelOnlineCronjob
from cron.jobs.model_benchmarking.benchmarking_cronjob import BenchmarkingCronjob
from cron.settings import settings


# Constants
MINUTES_5 = 5
MINUTES_60 = 60
MINUTES_1440 = 1440  # Daily

# Configure logging
os.makedirs(settings.log_dir, exist_ok=True)
log_file_path = os.path.join(settings.log_dir, 'cron.log')
logging.basicConfig(
    filename=log_file_path,
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class JobScheduler:
    """
    Manages and executes cron jobs based on their scheduled intervals.
    
    Jobs are organized by interval in minutes:
    - 5: Every 5 minutes
    - 60: Every hour
    - 1440: Every day
    """
    
    # Job configuration organized by interval (in minutes)
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

    def __init__(self) -> None:
        """Initialize the job scheduler with logging and Discord webhook."""
        self._logger = logging.getLogger(__name__)
        self._run_single_job_now: Optional[str] = None
        self._webhook = self._initialize_webhook()

    def _initialize_webhook(self) -> Optional[SyncWebhook]:
        """Initialize Discord webhook if URL is configured."""
        try:
            webhook_url = getattr(settings, 'discord', {}).get('webhook_url', '')
            return SyncWebhook.from_url(webhook_url) if webhook_url else None
        except Exception as e:
            self._logger.warning(f"Failed to initialize Discord webhook: {e}")
            return None

    def run(self) -> None:
        """Main entry point to run scheduled jobs."""
        try:
            self._logger.info('## Cron scheduler started')
            current_time = datetime.now(timezone.utc).astimezone()
            self._logger.info(f'Current time: hour={current_time.hour}, minute={current_time.minute}')
            
            jobs_to_run = self._get_jobs_to_run(current_time)
            self._execute_jobs(jobs_to_run, current_time)
            
        except Exception as e:
            self._logger.exception('Critical error in cron scheduler logic')
            raise

    def _get_jobs_to_run(self, current_time: datetime) -> List[Type[CronjobBase]]:
        """Determine which jobs should run based on current time or manual override."""
        if self._run_single_job_now is not None:
            return self._get_single_job()
        return self._get_scheduled_jobs(current_time)

    def _execute_jobs(self, jobs: List[Type[CronjobBase]], current_time: datetime) -> None:
        """Execute a list of jobs."""
        for job_class in jobs:
            self._execute_single_job(job_class, current_time)

    def _execute_single_job(self, job_class: Type[CronjobBase], current_time: datetime) -> None:
        """Execute a single job with proper error handling and logging."""
        job_name = job_class.__name__
        start_time = self._get_timestamp()
        
        try:
            self._logger.info(f'Checking job: {job_name}')
            job_instance = job_class()
            
            should_run = job_instance.shouldStart(current_time) or self._run_single_job_now is not None
            
            if should_run:
                self._logger.info(f'Starting job: {job_name}')
                success = job_instance.start(current_time)
                
                if not success:
                    self._logger.warning(f'Job controlled termination: {job_name}')
                    job_instance.cleanUpAfterError()
                
                execution_time = self._get_timestamp() - start_time
                self._logger.info(f'Job completed: {job_name}, execution time: {execution_time}s')
            else:
                execution_time = self._get_timestamp() - start_time
                self._logger.info(f'Job skipped: {job_name}, check time: {execution_time}s')
                
        except Exception as e:
            self._handle_job_error(job_name, e, job_instance if 'job_instance' in locals() else None)

    def _handle_job_error(self, job_name: str, error: Exception, job_instance: Optional[CronjobBase]) -> None:
        """Handle job execution errors with logging and notification."""
        error_msg = f'Job failed with error: {job_name}'
        self._logger.exception(error_msg)
        print(f'{error_msg}\n{error}')
        
        # Send Discord notification if webhook is configured
        if self._webhook:
            self._send_error_notification(job_name, error)
        
        # Cleanup if job instance exists
        if job_instance:
            try:
                job_instance.cleanUpAfterError()
            except Exception as cleanup_error:
                self._logger.exception(f'Cleanup failed for job {job_name}: {cleanup_error}')

    def _send_error_notification(self, job_name: str, error: Exception) -> None:
        """Send error notification via Discord webhook."""
        try:
            error_message = (
                f"**⚠️ Cronjob Error**\n"
                f"**Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                f"**Job:** `{job_name}`\n"
                f"**Error:**\n"
                f"```\n{str(error)}\n```"
            )
            self._webhook.send(error_message)
        except Exception as webhook_error:
            self._logger.error(f'Failed to send Discord notification: {webhook_error}')


    def _get_scheduled_jobs(self, current_time: datetime) -> List[Type[CronjobBase]]:
        """Get jobs that should run based on current time."""
        jobs_to_run = []
        for interval_minutes, job_list in self._job_config.items():
            if current_time.minute % interval_minutes == 0:
                jobs_to_run.extend(job_list)
        return jobs_to_run

    def _get_all_jobs(self) -> List[Type[CronjobBase]]:
        """Get all configured jobs."""
        all_jobs = []
        for job_list in self._job_config.values():
            all_jobs.extend(job_list)
        return all_jobs

    def _get_single_job(self) -> List[Type[CronjobBase]]:
        """Get a single job to run (used for manual execution)."""
        if not self._run_single_job_now:
            return []
        
        all_jobs = self._get_all_jobs()
        for job_class in all_jobs:
            if job_class.__name__ == self._run_single_job_now:
                return [job_class]
        
        self._logger.error(f"Job '{self._run_single_job_now}' not found!")
        return []

    @staticmethod
    def _get_timestamp() -> int:
        """Get current timestamp as integer."""
        return int(datetime.now().timestamp())

    def apply_arguments(self, args: List[str]) -> None:
        """Apply command line arguments to configure the scheduler."""
        if len(args) <= 1:
            return
        
        for arg in args[1:]:
            self._process_argument(arg)

    def _process_argument(self, arg: str) -> None:
        """Process a single command line argument."""
        if '=' not in arg:
            error_msg = f"Argument '{arg}' not properly formatted, use 'key=value' format"
            self._logger.error(error_msg)
            raise ValueError(error_msg)
        
        key, value = arg.split('=', 1)
        key = key.lower()
        
        self._logger.info(f"Applying parameter '{key}' with value '{value}'")
        
        if key == "dummy":
            self._logger.info(f"Dummy parameter detected, value: '{value}'. Nothing to do.")
        elif key == "run_single_job_now":
            self._run_single_job_now = value
        else:
            error_msg = f"Unknown argument key: {key}"
            self._logger.error(error_msg)
            raise ValueError(error_msg)
