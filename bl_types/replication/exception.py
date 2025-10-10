class NonAuthorizedOperationError(Exception):
    """Right authorization exception"""
    pass


class ContextError(Exception):
    """Context execution error"""
    pass

class UnsupportedTypeError(Warning):
    """Type not supported error"""
    pass

class StateError(Exception):
    """State error"""
    pass


class ServiceNetworkError(Exception):
    """Service networking error"""
    pass

class NetworkFrameError(Exception):
    """Networking frame error"""
    pass

class DataError(Exception):
    """Networking frame error"""
    pass
