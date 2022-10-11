"""
Dataflow exceptions for MultiWOZ 2.2.
"""

from opendf.exceptions.df_exception import ElementNotFoundException


class HotelNotFoundException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(
            "No such hotel found on the database.",
            node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)
