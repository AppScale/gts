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


class StringBuilder(object):

    """
    Builds string parts together acting like Java/.NET StringBuilder
    """

    def __init__(self):
        self.string = []

    def append(self, string):
        """Appends non empty string

        Args:
            string: String to append
        Returns:
            None
        """
        if string:
            self.string.append(string)

    def __str__(self):
        return ''.join(self.string)

    def __len__(self):
        return len(self.string)
