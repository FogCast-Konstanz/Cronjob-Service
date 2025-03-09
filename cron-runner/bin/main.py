import sys
from cron.job_scheduler import JobScheduler


cron = JobScheduler()
cron.applyArguments(sys.argv)
cron.run()