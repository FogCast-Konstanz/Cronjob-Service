#!/usr/bin/python3
import os
from datetime import datetime
from cron.jobs.cronjob_base import CronjobBase as Cronjob_Interface
from cron.jobs.open_meteo import OpenMeteoCronjob
from cron.settings import settings

import logging

os.makedirs(settings.log_dir, exist_ok=True)
log_file_path = settings.log_dir + '/cron.log'
logging.basicConfig(filename=log_file_path, filemode='w', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class JobScheduler:

    __jobs = {
        # Alle 5 Miuten
        5: [
            
        ],

        # Jede Stunde
        60: [
            OpenMeteoCronjob
        ],
    }

    def __init__(self) -> None:
        self._logger = logging.getLogger()
        self._run_single_job_now = None


    def run(self):
        try:
            self._logger.info('## Cron gestartet')
            dt = datetime.now()
            self._logger.info('CronJob: dt.hour = {0}, dt.minute = {1}'.format(dt.hour, dt.minute))
            startTime = int(dt.timestamp())
            if self._run_single_job_now == None:
                jobs = self.getJobs(dt)
            else:
                jobs = self.getRunSingleJobNow()

            for jobName in jobs:

                runTimeJobStart = self._getTimestamp()
                jobNameAsStr = jobName.__name__
                taskOk = True
                
                job: Cronjob_Interface = jobName()
                self._logger.info('CronJob ' + jobNameAsStr + ': Prüfen')

                # datetime übergeben, da die Abarbeitung der Jobs lange dauern könnte
                if (job.shouldStart(dt) or self._run_single_job_now is not None):
                    self._logger.info('CronJob ' + jobNameAsStr + ': Start')

                    try: 
                        # Cronjob starten
                        if (job.start(dt) == False):
                            self._logger.warning('CronJob ' + jobNameAsStr + ': Kontrollierter Abbruch')

                            # Bei kontrolliertem Abbruch Bereinigung starten
                            job.cleanUpAfterError()

                        runTimeJob = self._getTimestamp() - runTimeJobStart
                        self._logger.info('CronJob ' + jobNameAsStr + ': Beendet Laufzeit in s: ' + str(runTimeJob))
                    except Exception:
                        taskOk = False
                        self._logger.exception('Abbruch durch Fehler im CronJob: ' + jobNameAsStr)

                        if 'job' in locals():
                            job.cleanUpAfterError()

                else: 
                    runTimeJob = self._getTimestamp() - runTimeJobStart
                    self._logger.info('CronJob ' + jobNameAsStr + ': Nichts zu tun. Laufzeit in s: ' + str(runTimeJob))

            runTimeCron = self._getTimestamp() - startTime
            self._logger.info('## Cron Durchlauf beendet; Laufzeit in s: ' + str(runTimeCron))

        except Exception:
            self._logger.exception('Abbruch durch Fehler in der cron Logik')


    '''Gibt Jobs zurück, welche in diesem Lauf ausgeführt werden sollen'''
    def getJobs(self, datetime: datetime) ->list:
        keys = self.__jobs.keys()
        jobs = []
        for key in keys:
            if (datetime.minute % key == 0):
                jobs += self.__jobs[key]
        return jobs

    '''Gibt alle Jobs zurück'''
    def getAllJobs(self) -> list:
        keys = self.__jobs.keys()
        jobs = []
        for key in keys:
            jobs += self.__jobs[key]
        return jobs

    '''Wenn per dediziertem Aufruf nur ein spezieller Job gestartet werden soll'''
    def getRunSingleJobNow(self) -> list:
        runJobs = []
        allJobs = self.getAllJobs()
        for job in allJobs:
            if job.__name__ == self._run_single_job_now:
                runJobs.append(job)
                break
        if len(runJobs) == 0:
            self._logger.error ("Job '{0}' wurde nicht gefunden!")
        return runJobs

    '''Gibt einen timestamp als int zurück'''
    def _getTimestamp(self) -> int:
        return int(datetime.now().timestamp())

    '''Bei Scriptaufruf übergebene Parameter anwenden'''
    def applyArguments(self, args:list) -> None:
        if len(args) > 1:
            for i in range (1, len(args), 1):
                if ('=' not in args[i]):
                    self._logger.exception ("Argument '{0}' ungültig formatiert, korrekt wäre: 'key=value'.".format(args[i]))
                    raise Exception ("Argument '{0}' not properly defined, use syntax like 'key=value'.".format(args[i]))
                else:
                    myArg = args[i].split('=',maxsplit=1)
                    argKey = myArg[0].lower()
                    argValue = myArg[1]

                    self._logger.info("Wende Parameter '{0}' mit Wert '{1}' an".format(argKey, argValue))                    
                    if (argKey == "dummy"):
                        self._logger.info ("Dummy-parameter erkannt, Wert: '{0}'\nNichts zu tun.".format(argValue))
                    elif argKey == "run_single_job_now":
                        self._run_single_job_now = argValue
                    else: # Falls ein Parameter nicht angewendet wurde, Fehler melden und abbrechen.
                        self._logger.exception ("Argument '{0}' unbekannt, breche ab.".format(args[i]))
                        raise Exception ("Unknown argument key: {0}".format(argKey))
