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
from cron_descriptor import Options, DescriptionTypeEnum, ExpressionDescriptor, MissingFieldException, FormatException


class TestExceptions(TestCase.TestCase):

    """
    Tests that Exceptions are/not propery raised
    """

    def test_none_cron_expression_exception(self):
        options = Options()
        options.throw_exception_on_parse_error = True
        ceh = ExpressionDescriptor(None, options)
        self.assertRaises(
            MissingFieldException,
            ceh.get_description,
            DescriptionTypeEnum.FULL)

    def test_empty_cron_expression_exception(self):
        options = Options()
        options.throw_exception_on_parse_error = True
        ceh = ExpressionDescriptor('', options)
        self.assertRaises(
            MissingFieldException,
            ceh.get_description,
            DescriptionTypeEnum.FULL)

    def test_none_cron_expression_error(self):
        options = Options()
        options.throw_exception_on_parse_error = False
        ceh = ExpressionDescriptor(None, options)
        self.assertEqual(
            "Field 'ExpressionDescriptor.expression' not found.",
            ceh.get_description(DescriptionTypeEnum.FULL))

    def test_invalid_cron_expression_exception(self):
        options = Options()
        options.throw_exception_on_parse_error = True
        ceh = ExpressionDescriptor("INVALID", options)
        self.assertRaises(
            FormatException,
            ceh.get_description,
            DescriptionTypeEnum.FULL)

    def test_invalid_cron_expression_error(self):
        options = Options()
        options.throw_exception_on_parse_error = False
        ceh = ExpressionDescriptor("INVALID CRON", options)
        self.assertEqual(
            "Error: Expression only has 2 parts.  At least 5 part are required.",
            ceh.get_description(DescriptionTypeEnum.FULL))

    def test_invalid_syntax_exception(self):
        options = Options()
        options.throw_exception_on_parse_error = True
        ceh = ExpressionDescriptor("* $ * * *", options)
        self.assertRaises(
            FormatException,
            ceh.get_description,
            DescriptionTypeEnum.FULL)
