import abc
from datetime import datetime
from discord import SyncWebhook
from cron.settings_utils import get_discord_webhook_url


class CronjobBase(metaclass=abc.ABCMeta):
    '''Basis-Klasse für Cronjobs'''

    def __init__(self):
        discord_webhook_url = get_discord_webhook_url()
        self._webhook = SyncWebhook.from_url(
            discord_webhook_url) if discord_webhook_url != "" else None

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
