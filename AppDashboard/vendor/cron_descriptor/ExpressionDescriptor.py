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

import re
import datetime
import calendar

from .GetText import GetText
from .CasingTypeEnum import CasingTypeEnum
from .DescriptionTypeEnum import DescriptionTypeEnum
from .ExpressionParser import ExpressionParser
from .Options import Options
from .StringBuilder import StringBuilder
from .Exception import FormatException, WrongArgumentException


class ExpressionDescriptor(object):

    """
     Converts a Cron Expression into a human readable string
    """

    _special_characters = ['/', '-', ',', '*']
    _expression = ''
    _options = None
    _expression_parts = []
    _parsed = False

    def __init__(self, expression, options=None, **kwargs):
        """Initializes a new instance of the ExpressionDescriptorclass

        Args:
            expression: The cron expression string
            options: Options to control the output description
        Raises:
            WrongArgumentException: if kwarg is unknow

        """
        if options is None:
            options = Options()
        self._expression = expression
        self._options = options
        self._expression_parts = []
        self._parsed = False

        # if kwargs in _options, overwrite it, if not raise exeption
        for kwarg in kwargs:
            if hasattr(self._options, kwarg):
                setattr(self._options, kwarg, kwargs[kwarg])
            else:
                raise WrongArgumentException(
                    "Unknow {} configuration argument".format(kwarg))

        # Initializes localization
        GetText()

    def get_description(self, description_type=DescriptionTypeEnum.FULL):
        """Generates a human readable string for the Cron Expression

        Args:
            description_type: Which part(s) of the expression to describe
            options: Options to control the output description
        Returns:
            The cron expression description
        Raises:
            Exception: if throw_exception_on_parse_error is True

        """
        description = ''

        try:
            if self._parsed is False:
                parser = ExpressionParser(self._expression, self._options)
                self._expression_parts = parser.parse()
                self._parsed = True

            choices = {
                DescriptionTypeEnum.FULL: self.get_full_description,
                DescriptionTypeEnum.TIMEOFDAY: self.get_time_of_day_description,
                DescriptionTypeEnum.HOURS: self.get_hours_description,
                DescriptionTypeEnum.MINUTES: self.get_minutes_description,
                DescriptionTypeEnum.SECONDS: self.get_seconds_description,
                DescriptionTypeEnum.DAYOFMONTH: self.get_day_of_month_description,
                DescriptionTypeEnum.MONTH: self.get_month_description,
                DescriptionTypeEnum.DAYOFWEEK: self.get_day_of_week_description,
                DescriptionTypeEnum.YEAR: self.get_year_description,
            }

            description = choices.get(description_type, self.get_seconds_description)()

        except Exception as ex:
            if self._options.throw_exception_on_parse_error:
                raise
            else:
                description = str(ex)
        return description

    def get_full_description(self):
        """Generates the FULL description

        Returns:
            The FULL description
        Raises:
            FormatException: if formating fails and throw_exception_on_parse_error is True

        """
        description = ''

        try:
            time_segment = self.get_time_of_day_description()
            day_of_month_desc = self.get_day_of_month_description()
            month_desc = self.get_month_description()
            day_of_week_desc = self.get_day_of_week_description()
            year_desc = self.get_year_description()

            def day_of_wm(exp):
                if exp == "*":
                    return day_of_week_desc
                elif "," in exp:
                    return "{}{}".format(day_of_month_desc, day_of_week_desc)
                else:
                    return day_of_month_desc

            description = "{0}{1}{2}{3}".format(
                time_segment,
                day_of_wm(self._expression_parts[3]),
                month_desc,
                year_desc)

            description = self.transform_verbosity(
                description, self._options.verbose)
            description = self.transform_case(
                description,
                self._options.casing_type)
        except Exception:
            description = _(
                "An error occured when generating the expression description.  Check the cron expression syntax.")
            if self._options.throw_exception_on_parse_error:
                raise FormatException(description)

        return description

    def get_time_of_day_description(self):
        """Generates a description for only the TIMEOFDAY portion of the expression

        Returns:
            The TIMEOFDAY description

        """
        seconds_expression = self._expression_parts[0]
        minute_expression = self._expression_parts[1]
        hour_expression = self._expression_parts[2]

        description = StringBuilder()

        # handle special cases first
        if any(exp in minute_expression for exp in self._special_characters) is False and \
            any(exp in hour_expression for exp in self._special_characters) is False and \
                any(exp in seconds_expression for exp in self._special_characters) is False:
            # specific time of day (i.e. 10 14)
            description.append(_("At "))
            description.append(
                self.format_time(
                    hour_expression,
                    minute_expression,
                    seconds_expression))
        elif "-" in minute_expression and \
            "," not in minute_expression and \
                any(exp in hour_expression for exp in self._special_characters) is False:
            # minute range in single hour (i.e. 0-10 11)
            minute_parts = minute_expression.split('-')
            description.append(_("Every minute between {0} and {1}").format(
                self.format_time(hour_expression, minute_parts[0]), self.format_time(hour_expression, minute_parts[1])))
        elif "," in hour_expression and any(exp in minute_expression for exp in self._special_characters) is False:
            # hours list with single minute (o.e. 30 6,14,16)
            hour_parts = hour_expression.split(',')
            description.append(_("At"))
            for i, hour_part in enumerate(hour_parts):
                description.append(" ")
                description.append(
                    self.format_time(hour_part, minute_expression))

                if i < (len(hour_parts) - 2):
                    description.append(",")

                if i == len(hour_parts) - 2:
                    description.append(_(" and"))
        else:
            # default time description
            seconds_description = self.get_seconds_description()
            minutes_description = self.get_minutes_description()
            hours_description = self.get_hours_description()

            description.append(seconds_description)

            if description:
                description.append(", ")

            description.append(minutes_description)

            if description:
                description.append(", ")

            description.append(hours_description)
        return str(description)

    def get_seconds_description(self):
        """Generates a description for only the SECONDS portion of the expression

        Returns:
            The SECONDS description

        """
        return self.get_segment_description(
            self._expression_parts[0],
            _("every second"),
            lambda s: s.zfill(2),
            lambda s: _("every {0} seconds").format(s),
            lambda s: _("seconds {0} through {1} past the minute"),
            lambda s: _("at {0} seconds past the minute")
        )

    def get_minutes_description(self):
        """Generates a description for only the MINUTE portion of the expression

        Returns:
            The MINUTE description

        """
        return self.get_segment_description(
            self._expression_parts[1],
            _("every minute"),
            lambda s: s.zfill(2),
            lambda s: _("every {0} minutes").format(s.zfill(2)),
            lambda s: _("minutes {0} through {1} past the hour"),
            lambda s: '' if s == "0" else _("at {0} minutes past the hour")
        )

    def get_hours_description(self):
        """Generates a description for only the HOUR portion of the expression

        Returns:
            The HOUR description

        """
        expression = self._expression_parts[2]
        return self.get_segment_description(
            expression,
            _("every hour"),
            lambda s: self.format_time(s, "0"),
            lambda s: _("every {0} hours").format(s.zfill(2)),
            lambda s: _("between {0} and {1}"),
            lambda s: _("at {0}")
        )

    def get_day_of_week_description(self):
        """Generates a description for only the DAYOFWEEK portion of the expression

        Returns:
            The DAYOFWEEK description

        """
        def get_day_name(s):
            exp = s
            if "#" in s:
                exp, useless = s.split("#", 2)
            elif "L" in s:
                exp = exp.replace("L", '')
            return self.number_to_day(int(exp))

        def get_format(s):
            formated = None
            if "#" in s:
                day_of_week_of_month = s[s.find("#") + 1:]

                try:
                    day_of_week_of_month_numer = int(day_of_week_of_month)
                    choices = {
                        1: _("first"),
                        2: _("second"),
                        3: _("third"),
                        4: _("forth"),
                        5: _("fifth"),
                    }
                    day_of_week_of_month_description = choices.get(day_of_week_of_month_numer, None)
                except ValueError:
                    day_of_week_of_month_description = None

                formated = "{}{}{}".format(_(", on the "),
                                           day_of_week_of_month_description, _(" {0} of the month"))
            elif "L" in s:
                formated = _(", on the last {0} of the month")
            else:
                formated = _(", only on {0}")

            return formated

        return self.get_segment_description(
            self._expression_parts[5],
            _(", every day"),
            lambda s: get_day_name(s),
            lambda s: _(", every {0} days of the week").format(s),
            lambda s: _(", {0} through {1}"),
            lambda s: get_format(s)
        )

    def get_month_description(self):
        """Generates a description for only the MONTH portion of the expression

        Returns:
            The MONTH description

        """
        return self.get_segment_description(
            self._expression_parts[4],
            '',
            lambda s: datetime.date(datetime.date.today().year, int(s), 1).strftime("%B"),
            lambda s: _(", every {0} months").format(s),
            lambda s: _(", {0} through {1}"),
            lambda s: _(", only in {0}")
        )

    def get_day_of_month_description(self):
        """Generates a description for only the DAYOFMONTH portion of the expression

        Returns:
            The DAYOFMONTH description

        """
        description = None
        expression = self._expression_parts[3]
        expression = expression.replace("?", "*")

        if expression == "L":
            description = _(", on the last day of the month")
        elif expression == "LW" or expression == "WL":
            description = _(", on the last weekday of the month")
        else:
            regex = re.compile("(\\d{1,2}W)|(W\\d{1,2})")
            if regex.match(expression):
                m = regex.match(expression)
                day_number = int(m.group().replace("W", ""))

                day_string = _("first weekday") if day_number == 1 else _("weekday nearest day {0}").format(
                    day_number)
                description = _(", on the {0} of the month").format(
                    day_string)
            else:
                description = self.get_segment_description(
                    expression,
                    _(", every day"),
                    lambda s: s,
                    lambda s: _(", every day") if s == "1" else _(", every {0} days"),
                    lambda s: _(", between day {0} and {1} of the month"),
                    lambda s: _(", on day {0} of the month")
                )

        return description

    def get_year_description(self):
        """Generates a description for only the YEAR portion of the expression

        Returns:
            The YEAR description

        """
        return self.get_segment_description(
            self._expression_parts[6],
            '',
            lambda s: s.zfill(4),
            lambda s: _(", every {0} years").format(s),
            lambda s: _(", {0} through {1}"),
            lambda s: _(", only in {0}")
        )

    def get_segment_description(
        self,
        expression,
        all_description,
        get_single_item_description,
        get_interval_description_format,
        get_between_description_format,
        get_description_format
    ):
        """Returns segment description
        Args:
            expression: Segment to descript
            all_description: *
            get_single_item_description: 1
            get_interval_description_format: 1/2
            get_between_description_format: 1-2
            get_description_format: format get_single_item_description
        Returns:
            segment description

        """
        description = None
        if expression is None or expression == '':
            description = ''
        elif expression == "*":
            description = all_description
        elif any(ext in expression for ext in ['/', '-', ',']) is False:
            description = get_description_format(expression).format(
                get_single_item_description(expression))
        elif "/" in expression:
            segments = expression.split('/')
            description = get_interval_description_format(
                segments[1]).format(get_single_item_description(segments[1]))

            # interval contains 'between' piece (i.e. 2-59/3 )
            if "-" in segments[0]:
                between_segment_of_interval = segments[0]
                between_segements = between_segment_of_interval.split('-')
                between_segment_1_description = get_single_item_description(
                    between_segements[0])
                between_segment_2_description = get_single_item_description(
                    between_segements[1])
                between_segment_2_description = between_segment_2_description.replace(
                    ":00", ":59")
                description += ", " + get_between_description_format(between_segment_of_interval).format(
                    between_segment_1_description, between_segment_2_description)
        elif "," in expression:
            segments = expression.split(',')

            description_content = ''
            for i, segment in enumerate(segments):
                if i > 0 and len(segments) > 2:
                    description_content += ","

                    if i < len(segments) - 1:
                        description_content += " "

                if i > 0 and len(segments) > 1 and (i == len(segments) - 1 or len(segments) == 2):
                    description_content += _(" and ")

                if "-" in segment:
                    between_segments = segment.split('-')
                    between_segment_1_description = get_single_item_description(between_segments[0])
                    between_segment_2_description = get_single_item_description(between_segments[1])
                    between_segment_2_description = between_segment_2_description.replace(":00", ":59")
                    between_description = _(", {0} through {1}").format(
                        between_segment_1_description, between_segment_2_description)

                    between_description = between_description.replace(", ", "")

                    description_content += between_description
                else:
                    description_content += get_single_item_description(segment)

            description = get_description_format(
                expression).format(
                    description_content)
        elif "-" in expression:
            segments = expression.split('-')
            between_segment_1_description = get_single_item_description(segments[0])
            between_segment_2_description = get_single_item_description(segments[1])
            between_segment_2_description = between_segment_2_description.replace(
                ":00", ":59")
            description = get_between_description_format(expression).format(
                between_segment_1_description, between_segment_2_description)

        return description

    def format_time(
        self,
        hour_expression,
        minute_expression,
        second_expression=''
    ):
        """Given time parts, will contruct a formatted time description
        Args:
            hour_expression: Hours part
            minute_expression: Minutes part
            second_expression: Seconds part
        Returns:
            Formatted time description

        """
        hour = int(hour_expression)

        period = ''
        if self._options.use_24hour_time_format is False:
            period = " PM" if (hour >= 12) else " AM"
            if hour > 12:
                hour -= 12

        minute = str(int(minute_expression))  # !FIXME WUT ???
        second = ''
        if second_expression is not None and second_expression:
            second = "{}{}".format(":", str(int(second_expression)).zfill(2))

        return "{0}:{1}{2}{3}".format(str(hour).zfill(2), minute.zfill(2), second, period)

    def transform_verbosity(self, description, use_verbose_format):
        """Transforms the verbosity of the expression description by stripping verbosity from original description
        Args:
            description: The description to transform
            use_verbose_format: If True, will leave description as it, if False, will strip verbose parts
            second_expression: Seconds part
        Returns:
            The transformed description with proper verbosity

        """
        if use_verbose_format is False:
            description = description.replace(
                _(", every minute"), '')
            description = description.replace(_(", every hour"), '')
            description = description.replace(_(", every day"), '')
        return description

    def transform_case(self, description, case_type):
        """Transforms the case of the expression description, based on options
        Args:
            description: The description to transform
            case_type: The casing type that controls the output casing
            second_expression: Seconds part
        Returns:
            The transformed description with proper casing

        """
        if case_type == CasingTypeEnum.Sentence:
            description = "{}{}".format(
                description[0].upper(),
                description[1:])
        elif case_type == CasingTypeEnum.Title:
            description = description.title()
        else:
            description = description.lower()
        return description

    def number_to_day(self, day_number):
        """Returns localized day name by its CRON number

        Args:
            day_number: Number of a day
        Returns:
            Day corresponding to day_number
        Raises:
            IndexError: When day_number is not found
        """
        return [
            calendar.day_name[6],
            calendar.day_name[0],
            calendar.day_name[1],
            calendar.day_name[2],
            calendar.day_name[3],
            calendar.day_name[4],
            calendar.day_name[5]
        ][day_number]

    def __str__(self):
        return self.get_description()

    def __repr__(self):
        return self.get_description()


def get_description(expression, options=None):
    """Generates a human readable string for the Cron Expression
    Args:
        expression: The cron expression string
        options: Options to control the output description
    Returns:
        The cron expression description

    """
    descripter = ExpressionDescriptor(expression, options)
    return descripter.get_description(DescriptionTypeEnum.FULL)
