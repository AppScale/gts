""" Defines basic common classes and constants for the API server. """


class CallNotFound(Exception):
    """ Raised by APIServer calls when the requested method is not found. """
    pass


class ApplicationError(Exception):
    """ Used to communicate API-specific errors. """
    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
