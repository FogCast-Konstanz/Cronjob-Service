import abc
from datetime import datetime
from discord import SyncWebhook
from cron.settings import settings

class CronjobBase(metaclass=abc.ABCMeta):
    '''Basis-Klasse für Cronjobs'''

    def __init__(self):
        self._webhook = SyncWebhook.from_url(settings.discord.webhook_url) if settings.discord.webhook_url != "" else None

    def shouldStart(self, local_dt: datetime) -> bool:
         '''Ob der job in der aktuellen Umgebung ausgeführt werden darf.
            Kann evtl. Zusatzbedingungen für einen Cronjob definieren, die vor Ausführung
            geprüft werden.
         '''
         return True

    @abc.abstractmethod
    def start(self, local_dt: datetime) -> bool:
        '''Führt diesen Job aus'''
        raise NotImplementedError

    @abc.abstractmethod
    def cleanUpAfterError(self):
        '''Trat während der Verarbeitung ein Fehler auf, dann können in dieser Funktion Aufräumarbeiten gemacht werden'''
        raise NotImplementedError