# -*- coding: utf-8 -*-

import datetime
import calendar
from email.utils import formatdate
from webob import datetime_utils
from nose.tools import ok_, eq_, assert_raises

def test_UTC():
    """Test missing function in _UTC"""
    x = datetime_utils.UTC
    ok_(x.tzname(datetime.datetime.now())=='UTC')
    eq_(x.dst(datetime.datetime.now()), datetime.timedelta(0))
    eq_(x.utcoffset(datetime.datetime.now()), datetime.timedelta(0))
    eq_(repr(x), 'UTC')

def test_parse_date():
    """Testing datetime_utils.parse_date.
    We need to verify the following scenarios:
        * a nil submitted value
        * a submitted value that cannot be parse into a date
        * a valid RFC2822 date with and without timezone
    """
    ret = datetime_utils.parse_date(None)
    ok_(ret is None, "We passed a None value "
        "to parse_date. We should get None but instead we got %s" %\
        ret)
    ret = datetime_utils.parse_date(u'Hi There')
    ok_(ret is None, "We passed an invalid value "
        "to parse_date. We should get None but instead we got %s" %\
        ret)
    ret = datetime_utils.parse_date(1)
    ok_(ret is None, "We passed an invalid value "
        "to parse_date. We should get None but instead we got %s" %\
        ret)
    ret = datetime_utils.parse_date(u'á')
    ok_(ret is None, "We passed an invalid value "
        "to parse_date. We should get None but instead we got %s" %\
        ret)
    ret = datetime_utils.parse_date('Mon, 20 Nov 1995 19:12:08 -0500')
    eq_(ret, datetime.datetime(
        1995, 11, 21, 0, 12, 8, tzinfo=datetime_utils.UTC))
    ret = datetime_utils.parse_date('Mon, 20 Nov 1995 19:12:08')
    eq_(ret,
        datetime.datetime(1995, 11, 20, 19, 12, 8, tzinfo=datetime_utils.UTC))

def test_serialize_date():
    """Testing datetime_utils.serialize_date
    We need to verify the following scenarios:
        * passing an unicode date, return the same date but str
        * passing a timedelta, return now plus the delta
        * passing an invalid object, should raise ValueError
    """
    ret = datetime_utils.serialize_date(u'Mon, 20 Nov 1995 19:12:08 GMT')
    assert type(ret) is (str)
    eq_(ret, 'Mon, 20 Nov 1995 19:12:08 GMT')
    dt = formatdate(
        calendar.timegm(
            (datetime.datetime.now()+datetime.timedelta(1)).timetuple()), usegmt=True)
    eq_(dt, datetime_utils.serialize_date(datetime.timedelta(1)))
    assert_raises(ValueError, datetime_utils.serialize_date, None)

def test_parse_date_delta():
    """Testing datetime_utils.parse_date_delta
    We need to verify the following scenarios:
        * passing a nil value, should return nil
        * passing a value that fails the conversion to int, should call
          parse_date
    """
    ok_(datetime_utils.parse_date_delta(None) is None, 'Passing none value, '
        'should return None')
    ret = datetime_utils.parse_date_delta('Mon, 20 Nov 1995 19:12:08 -0500')
    eq_(ret, datetime.datetime(
        1995, 11, 21, 0, 12, 8, tzinfo=datetime_utils.UTC))
    WHEN = datetime.datetime(2011, 3, 16, 10, 10, 37, tzinfo=datetime_utils.UTC)
    #with _NowRestorer(WHEN): Dammit, only Python 2.5 w/ __future__
    nr = _NowRestorer(WHEN)
    nr.__enter__()
    try:
        ret = datetime_utils.parse_date_delta(1)
        eq_(ret, WHEN + datetime.timedelta(0, 1))
    finally:
        nr.__exit__(None, None, None)


def test_serialize_date_delta():
    """Testing datetime_utils.serialize_date_delta
    We need to verify the following scenarios:
        * if we pass something that's not an int or float, it should delegate
          the task to serialize_date
    """
    eq_(datetime_utils.serialize_date_delta(1), '1')
    eq_(datetime_utils.serialize_date_delta(1.5), '1')
    ret = datetime_utils.serialize_date_delta(u'Mon, 20 Nov 1995 19:12:08 GMT')
    assert type(ret) is (str)
    eq_(ret, 'Mon, 20 Nov 1995 19:12:08 GMT')

def test_timedelta_to_seconds():
    val = datetime.timedelta(86400)
    result = datetime_utils.timedelta_to_seconds(val)
    eq_(result, 7464960000)


class _NowRestorer(object):
    def __init__(self, new_now):
        self._new_now = new_now
        self._old_now = None

    def __enter__(self):
        import webob.datetime_utils
        self._old_now = webob.datetime_utils._now
        webob.datetime_utils._now = lambda: self._new_now

    def __exit__(self, exc_type, exc_value, traceback):
        import webob.datetime_utils
        webob.datetime_utils._now = self._old_now
