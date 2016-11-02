# Copyright (C) 2016 Adam Schubert <adam.schubert@sg1-game.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


class MissingFieldException(Exception):

    """
    Exception for cases when something is missing
    """

    def __init__(self, message):
        """Initialize MissingFieldException

        Args:
            message: Message of exception

        """
        super(MissingFieldException, self).__init__(
            "Field '{}' not found.".format(message))


class FormatException(Exception):

    """
    Exception for cases when something has wrong format
    """
    pass


class WrongArgumentException(Exception):

    """
    Exception for cases when wrong argument is passed
    """
    pass
