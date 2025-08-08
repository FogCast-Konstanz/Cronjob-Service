import sys
from cron.job_scheduler import JobScheduler


def main():
    cron = JobScheduler()
    cron.apply_arguments(sys.argv)
    cron.run()


if __name__ == "__main__":
    main()
