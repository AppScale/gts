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
from cron_descriptor import Options, DescriptionTypeEnum, ExpressionDescriptor


class TestApi(TestCase.TestCase):

    """
    Testing that API of ExpressionDescriptor is working as specified in DOCs
    """

    def test_full(self):
        options = Options()
        options.use_24hour_time_format = True
        ceh = ExpressionDescriptor("* * * * *", options)
        self.assertEqual(
            "Every minute",
            ceh.get_description(DescriptionTypeEnum.FULL))

    def test_default(self):
        self.assertEqual(
            "Every minute",
            ExpressionDescriptor("* * * * *").get_description())

    def test_to_str(self):
        self.assertEqual(
            "Every minute",
            str(ExpressionDescriptor("* * * * *")))

    def test_to_repr(self):
        self.assertIsInstance(ExpressionDescriptor("* * * * *"), ExpressionDescriptor)

    def test_to_kargs(self):
        self.assertEqual(
            "At 17:17",
            str(ExpressionDescriptor("17 17 * * *", use_24hour_time_format=True)))
