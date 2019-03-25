
$:.unshift File.join(File.dirname(__FILE__), "..")
require 'djinn'

$:.unshift File.join(File.dirname(__FILE__), "..", "lib")
require 'cron_helper'

require 'rubygems'
require 'test/unit'
require 'flexmock/test_unit'


class TestCronHelper < Test::Unit::TestCase

  def test_update_cron
    # TODO
  end

  def test_clear_app_crontabs
    flexmock(Djinn).should_receive(:log_run).
      with("rm -f /etc/cron.d/appscale-*").and_return("")
    CronHelper.clear_app_crontabs
  end

  def test_clear_app_crontab
    flexmock(Djinn).should_receive(:log_run).
      with("rm -f /etc/cron.d/appscale-app").and_return("")
    CronHelper.clear_app_crontab("app")
  end

  def test_valid_crontab_line
    # TODO
  end

  def test_write_app_crontab
    # TODO
  end

  def test_fix_ords
    # TODO
  end

  def test_fix_months
    # Test with one month.
    months = "january"
    expected = "jan"
    actual = CronHelper.fix_months(months)
    assert_equal(expected, actual)

    # Test multiple in mixed format.
    months = "february,mar,april"
    expected = "feb,mar,apr"
    actual = CronHelper.fix_months(months)
    assert_equal(expected, actual)

    # Test wildcard
    months = "every"
    expected = "*"
    actual = CronHelper.fix_months(months)
    assert_equal(expected, actual)
  end

  def test_fix_days
    # Test with one day.
    days = "friday"
    expected = "fri"
    actual = CronHelper.fix_days(days)
    assert_equal(expected, actual)

    # Test multiple days in mixed format.
    days = "monday,tue,thursday,sun"
    expected = "mon,tue,thu,sun"
    actual = CronHelper.fix_days(days)
    assert_equal(expected, actual)

    # Test wildcard
    days = "day"
    expected = "*"
    actual = CronHelper.fix_days(days)
    assert_equal(expected, actual)
  end

  def test_convert_messy_format
    # Test format:
    # every N (hours|mins|minutes)
    # TODO

    # Test format:
    # ("every"|ordinal) (days) ["of" (monthspec)] (time)
    # TODO
    schedule = '2 of month 16:00'
    expected = ['0 16 2 * *']
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    schedule = '2 of jan,feb,march,april,may,june,july,aug,sep,oct,nov,dec 16:00'
    expected = ['0 16 2 jan,feb,mar,apr,may,jun,jul,aug,sep,oct,nov,dec *']
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    schedule = '2 of jan, feb, march, april, may, june, july, aug, sep, oct, nov, dec 16:00'
    expected = ['0 16 2 jan,feb,mar,apr,may,jun,jul,aug,sep,oct,nov,dec *']
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    schedule = '2 of jan , feb , march, april, may, june, july, aug, sep, oct, nov, dec 16:00'
    expected = ['0 16 2 jan,feb,mar,apr,may,jun,jul,aug,sep,oct,nov,dec *']
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # Test format:
    # every N (hours|mins|minutes) "from" (time) "to" (time)

    schedule = 'every 2 hours from 10:00 to 14:00'
    expected = ['0 10-14/2 * * *']
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # increment_type = hours, h1 < h2, m1 < m2
    schedule = "every 7 hours from 04:30 to 10:50"
    expected = ["30 4-10/7 * * *"]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # increment_type = hours, h1 < h2, m1 >= m2
    schedule = "every 7 hours from 00:30 to 04:20"
    expected = ["30 0-3/7 * * *"]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # increment_type = hours, h1 > h2, m1 < m2
    schedule = "every 7 hours from 22:00 to 07:20"
    expected = ["0 22-23/7 * * *",
                "0 5-7/7 * * *"]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # increment_type = hours, h1 > h2, m1 >= m2
    schedule = "every 7 hours from 20:10 to 11:00"
    expected = ["10 20-23/7 * * *",
                "10 3-10/7 * * *"]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # increment_type = minutes, h1 < h2, m1 < m2
    schedule = "every 7 minutes from 06:05 to 07:15"
    expected = ["5,12,19,26,33,40,47,54 6 * * *",
                "1,8,15 7 * * *"]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # increment_type = minutes, h1 < h2, m1 >= m2
    schedule = "every 7 minutes from 08:20 to 09:15"
    expected = ["20,27,34,41,48,55 8 * * *",
                "2,9 9 * * *"]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # increment_type = minutes, h1 >= h2, m1 < m2
    schedule = "every 7 minutes from 10:40 to 02:20"
    expected = ["40,47,54 10 * * *",
                "1,8,15,22,29,36,43,50,57 11 * * *",
                "4,11,18,25,32,39,46,53 12 * * *",
                "0,7,14,21,28,35,42,49,56 13 * * *",
                "3,10,17,24,31,38,45,52,59 14 * * *",
                "6,13,20,27,34,41,48,55 15 * * *",
                "2,9,16,23,30,37,44,51,58 16 * * *",
                "5,12,19,26,33,40,47,54 17 * * *",
                "1,8,15,22,29,36,43,50,57 18 * * *",
                "4,11,18,25,32,39,46,53 19 * * *",
                "0,7,14,21,28,35,42,49,56 20 * * *",
                "3,10,17,24,31,38,45,52,59 21 * * *",
                "6,13,20,27,34,41,48,55 22 * * *",
                "2,9,16,23,30,37,44,51,58 23 * * *",
                "5,12,19,26,33,40,47,54 0 * * *",
                "1,8,15,22,29,36,43,50,57 1 * * *",
                "4,11,18 2 * * *"]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # increment_type = minutes, h1 >= h2, m1 >= m2
    schedule = "every 7 minutes from 12:40 to 03:40"
    expected = ["40,47,54 12 * * *",
                "1,8,15,22,29,36,43,50,57 13 * * *",
                "4,11,18,25,32,39,46,53 14 * * *",
                "0,7,14,21,28,35,42,49,56 15 * * *",
                "3,10,17,24,31,38,45,52,59 16 * * *",
                "6,13,20,27,34,41,48,55 17 * * *",
                "2,9,16,23,30,37,44,51,58 18 * * *",
                "5,12,19,26,33,40,47,54 19 * * *",
                "1,8,15,22,29,36,43,50,57 20 * * *",
                "4,11,18,25,32,39,46,53 21 * * *",
                "0,7,14,21,28,35,42,49,56 22 * * *",
                "3,10,17,24,31,38,45,52,59 23 * * *",
                "6,13,20,27,34,41,48,55 0 * * *",
                "2,9,16,23,30,37,44,51,58 1 * * *",
                "5,12,19,26,33,40,47,54 2 * * *",
                "1,8,15,22,29,36 3 * * *"]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # every 24 hours
    schedule = "every 24 hours from 01:30 to 01:29"
    expected = ["30 1 * * *"]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # every 26 hours
    schedule = "every 26 hours from 01:30 to 01:29"
    expected = []
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # 1 of month 01:00
    schedule = "1 of month 01:00"
    expected = ["0 1 1 * *"]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # 2 of may 00:00
    schedule = "2 of may 00:00"
    expected = ["0 0 2 may *"]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # every 65 minutes
    schedule = "every 65 minutes from 12:26 to 03:10"
    expected = ["26 12 * * *",
                "31 13 * * *",
                "36 14 * * *",
                "41 15 * * *",
                "46 16 * * *",
                "51 17 * * *",
                "56 18 * * *",
                "1 20 * * *",
                "6 21 * * *",
                "11 22 * * *",
                "16 23 * * *",
                "21 0 * * *",
                "26 1 * * *",
                "31 2 * * *"]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # same t1 and t2
    schedule = "every 11 minutes from 12:01 to 12:01"
    expected = []
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # Every 5 minutes from 5-19.
    schedule = 'every 5 minutes from 5:00 to 19:00'
    expected = [
      '0,5,10,15,20,25,30,35,40,45,50,55 5 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 6 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 7 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 8 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 9 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 10 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 11 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 12 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 13 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 14 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 15 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 16 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 17 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 18 * * *',
      '0 19 * * *'
    ]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)

    # Every 5 minutes from 19-5.
    schedule = 'every 5 minutes from 19:00 to 5:00'
    expected = [
      '0,5,10,15,20,25,30,35,40,45,50,55 19 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 20 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 21 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 22 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 23 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 0 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 1 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 2 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 3 * * *',
      '0,5,10,15,20,25,30,35,40,45,50,55 4 * * *',
      '0 5 * * *'
    ]
    actual = CronHelper.convert_messy_format(schedule)
    self.assert_equal(expected, actual)
  end

  def test_generate_simple_cron
    expected = ['0 0 * * *']
    actual = CronHelper.simple_cron_lines(24, 'hours')
    self.assert_equal(expected, actual)

    expected = ['0 0 * * *']
    actual = CronHelper.simple_cron_lines(1440, 'mins')
    self.assert_equal(expected, actual)

    expected = ['0 0 * * *']
    actual = CronHelper.simple_cron_lines(1440, 'minutes')
    self.assert_equal(expected, actual)

    expected = ['0 */1 * * *']
    actual = CronHelper.simple_cron_lines(1, 'hours')
    self.assert_equal(expected, actual)

    expected = ['0 */3 * * *']
    actual = CronHelper.simple_cron_lines(180, 'mins')
    self.assert_equal(expected, actual)

    expected = ['*/15 * * * *']
    actual = CronHelper.simple_cron_lines(15, 'minutes')
    self.assert_equal(expected, actual)

    expected = ['*/30 * * * *']
    actual = CronHelper.simple_cron_lines(30, 'minutes')
    self.assert_equal(expected, actual)

    expected = [
        '0,45 0,3,6,9,12,15,18,21 * * *',
        '30 1,4,7,10,13,16,19,22 * * *',
        '15 2,5,8,11,14,17,20,23 * * *',
    ]
    actual = CronHelper.simple_cron_lines(45, 'minutes')
    self.assert_equal(expected, actual)

    expected = [
        '0 0,3,6,9,12,15,18,21 * * *',
        '30 1,4,7,10,13,16,19,22 * * *',
    ]
    actual = CronHelper.simple_cron_lines(90, 'minutes')
    self.assert_equal(expected, actual)

    expected = [
        '0 0 * * *'
    ]
    actual = CronHelper.simple_cron_lines(13, 'hours')
    self.assert_equal(expected, actual)

    expected = [
        '0,19,38,57 0,19 * * *',
        '16,35,54 1,20 * * *',
        '13,32,51 2,21 * * *',
        '10,29,48 3,22 * * *',
        '7,26 4,23 * * *',
        '45 4 * * *',
        '4,23,42 5 * * *',
        '1,20,39,58 6 * * *',
        '17,36,55 7 * * *',
        '14,33,52 8 * * *',
        '11,30,49 9 * * *',
        '8,27,46 10 * * *',
        '5,24,43 11 * * *',
        '2,21,40,59 12 * * *',
        '18,37,56 13 * * *',
        '15,34,53 14 * * *',
        '12,31,50 15 * * *',
        '9,28,47 16 * * *',
        '6,25,44 17 * * *',
        '3,22,41 18 * * *'
    ]
    actual = CronHelper.simple_cron_lines(19, 'mins')
    self.assert_equal(expected, actual)
  end

  def test_convert_schedule_to_cron
    # TODO
  end

  def test_get_from_xml
    # TODO
  end
end
