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

import locale
import gettext
import os
import logging


class GetText(object):

    """
    Handles language translations and Initializes global _() function
    """

    def __init__(self):
        """Initialize GetText
        """
        code, encoding = locale.getlocale()
        try:
            filename = os.path.join('locale', '{}.mo'.format(code))
            trans = gettext.GNUTranslations(open(filename, "rb"))
            logging.debug('{} Loaded'.format(filename))
        except IOError:
            trans = gettext.NullTranslations()

        trans.install()
