import abc
from datetime import datetime

class CronjobBase(metaclass=abc.ABCMeta):
    '''Basis-Klasse für Cronjobs'''

    @abc.abstractmethod
    def start(self, dt: datetime) -> bool:
        '''Führt diesen Job aus'''
        raise NotImplementedError

    @abc.abstractmethod
    def clean_up_after_error(self):
        '''Trat während der Verarbeitung ein Fehler auf, dann können in dieser Funktion Aufräumarbeiten gemacht werden'''
        raise NotImplementedError