"""
File containing Dataflow debugging exception.
These exceptions are exception raised by Dataflow, that are not python errors, but are meant to the developer,
not the user.
"""


class DebugDFException(Exception):
    """
    The base debug Dataflow exception.
    """

    def __init__(self, message, node, original_exception=None):
        """
        Creates a DebugDFException.

        :param message: the message
        :type message: str
        :param node: the Node
        :type node: Node
        :param original_exception: the original exception
        :type original_exception: Exception or List[Exception]
        """
        super(DebugDFException, self).__init__(message, node, original_exception)
