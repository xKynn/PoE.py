class RequestException(Exception):
    """
    General purpose exception, base class for other request related exceptions.
    """
    pass


class NotFoundException(RequestException):
    """
    For the 404s
    """
    pass


class ServerException(RequestException):
    """
    Exception that signifies that the server failed to respond with valid data.
    """
    pass

class OutdatedPoBException(Exception):
    """
    Raised when PoB XML indicates it is old and is missing stats.
    """

class AbsentItemBaseException(Exception):
    """
    Raised when a base in PoB can not be found on the wiki.
    """

class BRFilterException(Exception):
    """
    Raised when an invalid filter value is supplied.
    """
    pass