from . import state
from .registration import register, unregister


def __getattr__(name):
    if name in {
        "git_instance",
        "check_and_init_git",
        "init_git_on_load",
        "is_data_restricted",
        "_group_expanded",
    }:
        return getattr(state, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "register",
    "unregister",
    "git_instance",
    "check_and_init_git",
    "init_git_on_load",
    "is_data_restricted",
    "_group_expanded",
]
