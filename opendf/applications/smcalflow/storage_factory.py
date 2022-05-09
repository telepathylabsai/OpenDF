"""
Factory to create a unified instance of the storage system.
"""
from opendf.applications.smcalflow.database import Database
from opendf.applications.smcalflow.domain import GraphDB
from opendf.defs import use_database


class StorageFactory:
    """
    The storage factory.
    """
    __instance = None

    @staticmethod
    def get_instance():
        """
        Gets the unified instance of the Storage.

        :return: the unified instance of the Storage
        :rtype: Storage
        """
        if StorageFactory.__instance is None:
            if use_database:
                StorageFactory.__instance = Database.get_instance()
            else:
                StorageFactory.__instance = GraphDB.get_instance()

        return StorageFactory.__instance
