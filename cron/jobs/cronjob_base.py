import abc
from datetime import datetime

class CronjobBase(metaclass=abc.ABCMeta):
    '''Basis-Klasse für Cronjobs'''

    def shouldStart(self, dt: datetime) -> bool:
         '''Ob der job in der aktuellen Umgebung ausgeführt werden darf.
            Kann evtl. Zusatzbedingungen für einen Cronjob definieren, die vor Ausführung
            geprüft werden.
         '''
         return True

    @abc.abstractmethod
    def start(self, dt: datetime) -> bool:
        '''Führt diesen Job aus'''
        raise NotImplementedError

    @abc.abstractmethod
    def cleanUpAfterError(self):
        '''Trat während der Verarbeitung ein Fehler auf, dann können in dieser Funktion Aufräumarbeiten gemacht werden'''
        raise NotImplementedError