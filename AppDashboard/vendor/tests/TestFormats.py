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
from cron_descriptor import Options, get_description


class TestFormats(TestCase.TestCase):

    """
    Tests formated cron expressions
    """

    def test_every_minute(self):

        self.assertEqual("Every minute", get_description("* * * * *"))

    def test_every1_minute(self):

        self.assertEqual("Every minute", get_description("*/1 * * * *"))
        self.assertEqual("Every minute", get_description("0 0/1 * * * ?"))

    def test_every_hour(self):

        self.assertEqual("Every hour", get_description("0 0 * * * ?"))
        self.assertEqual("Every hour", get_description("0 0 0/1 * * ?"))

    def test_time_of_day_certain_days_of_week(self):

        self.assertEqual(
            "At 11:00 PM, Monday through Friday",
            get_description("0 23 ? * MON-FRI"))

    def test_every_second(self):

        self.assertEqual("Every second", get_description("* * * * * *"))

    def test_every45_seconds(self):

        self.assertEqual("Every 45 seconds", get_description("*/45 * * * * *"))

    def test_every5_minutes(self):

        self.assertEqual("Every 05 minutes", get_description("*/5 * * * *"))
        self.assertEqual("Every 10 minutes", get_description("0 0/10 * * * ?"))

    def test_every5_minutes_on_the_second(self):

        self.assertEqual("Every 05 minutes", get_description("0 */5 * * * *"))

    def test_weekdays_at_time(self):

        self.assertEqual(
            "At 11:30 AM, Monday through Friday",
            get_description("30 11 * * 1-5"))

    def test_daily_at_time(self):

        self.assertEqual("At 11:30 AM", get_description("30 11 * * *"))

    def test_minute_span(self):

        self.assertEqual(
            "Every minute between 11:00 AM and 11:10 AM", get_description("0-10 11 * * *"))

    def test_one_month_only(self):

        self.assertEqual(
            "Every minute, only in March",
            get_description("* * * 3 *"))

    def test_two_months_only(self):

        self.assertEqual(
            "Every minute, only in March and June",
            get_description("* * * 3,6 *"))

    def test_two_times_each_afternoon(self):

        self.assertEqual(
            "At 02:30 PM and 04:30 PM",
            get_description("30 14,16 * * *"))

    def test_three_times_daily(self):

        self.assertEqual(
            "At 06:30 AM, 02:30 PM and 04:30 PM",
            get_description("30 6,14,16 * * *"))

    def test_once_a_week(self):

        self.assertEqual(
            "At 09:46 AM, only on Monday",
            get_description("46 9 * * 1"))

    def test_day_of_month(self):

        self.assertEqual(
            "At 12:23 PM, on day 15 of the month",
            get_description("23 12 15 * *"))

    def test_month_name(self):

        self.assertEqual(
            "At 12:23 PM, only in January",
            get_description("23 12 * JAN *"))

    def test_day_of_month_with_question_mark(self):

        self.assertEqual(
            "At 12:23 PM, only in January",
            get_description("23 12 ? JAN *"))

    def test_month_name_range2(self):

        self.assertEqual(
            "At 12:23 PM, January through February", get_description("23 12 * JAN-FEB *"))

    def test_month_name_range3(self):

        self.assertEqual(
            "At 12:23 PM, January through March",
            get_description("23 12 * JAN-MAR *"))

    def test_day_of_week_name(self):

        self.assertEqual(
            "At 12:23 PM, only on Sunday",
            get_description("23 12 * * SUN"))

    def test_day_of_week_range(self):

        self.assertEqual(
            "Every 05 minutes, at 03:00 PM, Monday through Friday", get_description("*/5 15 * * MON-FRI"))

    def test_day_of_week_once_in_month(self):

        self.assertEqual(
            "Every minute, on the third Monday of the month", get_description("* * * * MON#3"))

    def test_last_day_of_the_week_of_the_month(self):

        self.assertEqual(
            "Every minute, on the last Thursday of the month", get_description("* * * * 4L"))

    def test_last_day_of_the_month(self):

        self.assertEqual(
            "Every 05 minutes, on the last day of the month, only in January", get_description("*/5 * L JAN *"))

    def test_last_weekday_of_the_month(self):

        self.assertEqual(
            "Every minute, on the last weekday of the month", get_description("* * LW * *"))

    def test_last_weekday_of_the_month2(self):

        self.assertEqual(
            "Every minute, on the last weekday of the month", get_description("* * WL * *"))

    def test_first_weekday_of_the_month(self):

        self.assertEqual(
            "Every minute, on the first weekday of the month", get_description("* * 1W * *"))

    def test_thirteenth_weekday_of_the_month(self):

        self.assertEqual(
            "Every minute, on the weekday nearest day 13 of the month", get_description("* * 13W * *"))

    def test_first_weekday_of_the_month2(self):

        self.assertEqual(
            "Every minute, on the first weekday of the month", get_description("* * W1 * *"))

    def test_particular_weekday_of_the_month(self):

        self.assertEqual(
            "Every minute, on the weekday nearest day 5 of the month", get_description("* * 5W * *"))

    def test_particular_weekday_of_the_month2(self):

        self.assertEqual(
            "Every minute, on the weekday nearest day 5 of the month", get_description("* * W5 * *"))

    def test_time_of_day_with_seconds(self):

        self.assertEqual("At 02:02:30 PM", get_description("30 02 14 * * *"))

    def test_second_internvals(self):

        self.assertEqual(
            "Seconds 05 through 10 past the minute",
            get_description("5-10 * * * * *"))

    def test_second_minutes_hours_intervals(self):

        self.assertEqual((
            "Seconds 05 through 10 past the minute, "
            "minutes 30 through 35 past the hour, "
            "between 10:00 AM and 12:59 PM"), get_description("5-10 30-35 10-12 * * *"))

    def test_every5_minutes_at30_seconds(self):

        self.assertEqual(
            "At 30 seconds past the minute, every 05 minutes", get_description("30 */5 * * * *"))

    def test_minutes_past_the_hour_range(self):

        self.assertEqual((
            "At 30 minutes past the hour, "
            "between 10:00 AM and 01:59 PM, "
            "only on Wednesday and Friday"), get_description("0 30 10-13 ? * WED,FRI"))

    def test_seconds_past_the_minute_interval(self):

        self.assertEqual(
            "At 10 seconds past the minute, every 05 minutes", get_description("10 0/5 * * * ?"))

    def test_between_with_interval(self):

        self.assertEqual(
            ("Every 03 minutes, minutes 02 through 59 past the hour, "
             "at 01:00 AM, 09:00 AM, and 10:00 PM, between day 11 and 26 of the month, "
             "January through June"), get_description("2-59/3 1,9,22 11-26 1-6 ?"))

    def test_recurring_first_of_month(self):

        self.assertEqual("At 06:00 AM", get_description("0 0 6 1/1 * ?"))

    def test_minutes_past_the_hour(self):

        self.assertEqual(
            "At 05 minutes past the hour",
            get_description("0 5 0/1 * * ?"))

    def test_one_year_only_with_seconds(self):

        self.assertEqual(
            "Every second, only in 2013",
            get_description("* * * * * * 2013"))

    def test_one_year_only_without_seconds(self):

        self.assertEqual(
            "Every minute, only in 2013",
            get_description("* * * * * 2013"))

    def test_two_years_only(self):

        self.assertEqual(
            "Every minute, only in 2013 and 2014", get_description("* * * * * 2013,2014"))

    def test_year_range2(self):

        self.assertEqual(
            "At 12:23 PM, January through February, 2013 through 2014", get_description("23 12 * JAN-FEB * 2013-2014"))

    def test_year_range3(self):

        self.assertEqual(
            "At 12:23 PM, January through March, 2013 through 2015", get_description("23 12 * JAN-MAR * 2013-2015"))

    def test_hour_range(self):

        self.assertEqual((
            "Every 30 minutes, between 08:00 AM and 09:59 AM, "
            "on day 5 and 20 of the month"), get_description("0 0/30 8-9 5,20 * ?"))

    def test_day_of_week_modifier(self):

        self.assertEqual(
            "At 12:23 PM, on the second Sunday of the month", get_description("23 12 * * SUN#2"))

    def test_day_of_week_modifier_with_sunday_start_one(self):

        options = Options()
        options.day_of_week_start_index_zero = False

        self.assertEqual(
            "At 12:23 PM, on the second Sunday of the month", get_description("23 12 * * 1#2", options))

    def test_day_of_week_modifier_with_day_of_month(self):
        self.assertEqual("At 00:00 AM, on day 1, 2, and 3 of the month, only on Wednesday and Friday",
                         get_description("0 0      0 1,2,3 * WED,FRI"))

    def test_hour_range_with_every_portion(self):

        self.assertEqual((
            "At 25 minutes past the hour, every 13 hours, "
            "between 07:00 AM and 07:59 PM"), get_description("0 25 7-19/13 ? * *"))

    def test_hour_range_with_trailing_zero_with_every_portion(self):

        self.assertEqual((
            "At 25 minutes past the hour, every 13 hours, "
            "between 07:00 AM and 08:59 PM"), get_description("0 25 7-20/13 ? * *"))

    def test_every3_day(self):

        self.assertEqual(
            "At 08:00 AM, every 3 days",
            get_description("0 0 8 1/3 * ? *"))

    def tests_every3_day_of_the_week(self):

        self.assertEqual(
            "At 10:15 AM, every 3 days of the week",
            get_description("0 15 10 ? * */3"))

    def test_every3_month(self):

        self.assertEqual(
            "At 07:05 AM, on day 2 of the month, every 3 months", get_description("0 5 7 2 1/3 ? *"))

    def test_every2_years(self):

        self.assertEqual(
            "At 06:15 AM, on day 1 of the month, only in January, every 2 years", get_description("0 15 6 1 1 ? 1/2"))

    def test_muti_part_range_seconds(self):

        self.assertEqual(
            "At 02 and 04 through 05 minutes past the hour, at 01:00 AM", get_description("2,4-5 1 * * *"))

    def test_muti_part_range_seconds2(self):

        self.assertEqual(
            "At 02 and 26 through 28 minutes past the hour, at 06:00 PM", get_description("2,26-28 18 * * *"))

    def test_individual_weekdays_and_range(self):
        self.assertEqual('At 08:38 PM, only on Sunday, Tuesday, and Wednesday through Saturday',
                         get_description('38 20 * * 0,2,3-6'))
