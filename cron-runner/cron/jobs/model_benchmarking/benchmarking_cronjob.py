from datetime import datetime
import pandas as pd

from cron.jobs.cronjob_base import CronjobBase
from cron.settings import settings
from cron.jobs.model_benchmarking.benchmarking import BenchmarkingService

import logging

class BenchmarkingCronjob(CronjobBase):

    def __init__(self):
        super().__init__()
        
    def start(self, local_dt: datetime) -> bool:
        try:
            service = BenchmarkingService()
            service.run_benchmark()
            return True
        except BaseException as e:
            logging.exception(f"Error in BenchmarkingCronjob", exc_info=e)
            return False
        
    def cleanUpAfterError(self):
        pass