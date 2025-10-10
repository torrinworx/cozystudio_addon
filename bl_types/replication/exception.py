# ##### BEGIN GPL LICENSE BLOCK #####
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####


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
