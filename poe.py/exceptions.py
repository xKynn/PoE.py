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


class BRFilterException(Exception):
    """
    Raised when an invalid filter value is supplied.
    """
    pass