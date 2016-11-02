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

import tests.TestCase as TestCase


class TestImport(TestCase.TestCase):

    """
    Tests that inline and separated imports are working
    """

    def test_inline_import(self):
        from cron_descriptor import Options, DescriptionTypeEnum, ExpressionDescriptor
        options = Options()
        options.use_24hour_time_format = True
        ceh = ExpressionDescriptor("* * * * *", options)
        self.assertEqual(
            "Every minute",
            ceh.get_description(DescriptionTypeEnum.FULL))

    def test_full_import(self):
        from cron_descriptor.Options import Options
        from cron_descriptor.DescriptionTypeEnum import DescriptionTypeEnum
        from cron_descriptor.ExpressionDescriptor import ExpressionDescriptor

        options = Options()
        options.use_24hour_time_format = True
        ceh = ExpressionDescriptor("* * * * *", options)
        self.assertEqual(
            'Every minute',
            ceh.get_description(DescriptionTypeEnum.FULL))
