from webob.byterange import Range, ContentRange, _is_content_range_valid

from nose.tools import assert_true, assert_false, assert_equal, assert_raises

# Range class

def test_satisfiable():
    range = Range( ((0,99),) )
    assert_true(range.satisfiable(100))
    assert_true(range.satisfiable(99))

def test_not_satisfiable():
    range = Range.parse('bytes=-100')
    assert_false(range.satisfiable(50))
    range = Range.parse('bytes=100-')
    assert_false(range.satisfiable(50))


def test_range_for_length():
    range = Range( ((0,99), (100,199) ) )
    assert_equal( range.range_for_length( 'None'), None )

def test_range_content_range_length_none():
    range = Range( ((0, 100),) )
    assert_equal( range.content_range( None ), None )

def test_range_content_range_length_ok():
    range = Range( ((0, 100),) )
    assert_true( range.content_range( 100 ).__class__, ContentRange )

def test_range_for_length_more_than_one_range():
    # More than one range
    range = Range( ((0,99), (100,199) ) )
    assert_equal( range.range_for_length(100), None )

def test_range_for_length_one_range_and_length_none():
    # One range and length is None
    range = Range( ((0,99), ) )
    assert_equal( range.range_for_length( None ), None )

def test_range_for_length_end_is_none():
    # End is None
    range = Range( ((0, None), ) )
    assert_equal( range.range_for_length(100), (0,100) )

def test_range_for_length_end_is_none_negative_start():
    # End is None and start is negative
    range = Range( ((-5, None), ) )
    assert_equal( range.range_for_length(100), (95,100) )

def test_range_start_none():
    # Start is None
    range = Range( ((None, 99), ) )
    assert_equal( range.range_for_length(100), None )

def test_range_str_end_none():
    range = Range( ((0, 100), ) )
    # Manually set test values
    range.ranges = ( (0, None), )
    assert_equal( str(range), 'bytes=0-' )

def test_range_str_end_none_negative_start():
    range = Range( ((0, 100), ) )
    # Manually set test values
    range.ranges = ( (-5, None), )
    assert_equal( str(range), 'bytes=-5' )

def test_range_str_1():
    # Single range
    range = Range( ((0, 100), ) )
    assert_equal( str(range), 'bytes=0-99' )

def test_range_str_2():
    # Two ranges
    range = Range( ((0, 100), (101, 200) ) )
    assert_equal( str(range), 'bytes=0-99,101-199' )

def test_range_str_3():
    # Negative start
    range = Range( ((-1, 100),) )
    assert_raises( ValueError, range.__str__ )

def test_range_str_4():
    # Negative end
    range = Range( ((0, 100),) )
    # Manually set test values
    range.ranges = ( (0, -100), )
    assert_raises( ValueError, range.__str__ )

def test_range_repr():
    range = Range( ((0, 99),) )
    assert_true( range.__repr__(), '<Range bytes 0-98>' )

def test_parse_valid_input():
    range = Range( ((0, 100),) )
    assert_equal( range.parse( 'bytes=0-99' ).__class__, Range )

def test_parse_missing_equals_sign():
    range = Range( ((0, 100),) )
    assert_equal( range.parse( 'bytes 0-99' ), None )

def test_parse_invalid_units():
    range = Range( ((0, 100),) )
    assert_equal( range.parse( 'words=0-99' ), None )

def test_parse_bytes_valid_input():
    range = Range( ((0, 100),) )
    assert_equal( range.parse_bytes( 'bytes=0-99' ), ('bytes', [(0,100)] ) )

def test_parse_bytes_missing_equals_sign():
    range = Range( ((0, 100),) )
    assert_equal( range.parse_bytes( 'bytes 0-99'), None )

def test_parse_bytes_missing_dash():
    range = Range( ((0, 100),) )
    assert_equal( range.parse_bytes( 'bytes=0 99'), None )

def test_parse_bytes_null_input():
    range = Range( ((0, 100),) )
    assert_raises( TypeError, range.parse_bytes, '' )

def test_parse_bytes_two_many_ranges():
    range = Range( ((0, 100),) )
    assert_equal( range.parse_bytes( 'bytes=-100,-100' ), None )

def test_parse_bytes_negative_start():
    range = Range( ((0, 100),) )
    assert_equal( range.parse_bytes( 'bytes=-0-99' ), None )

def test_parse_bytes_start_greater_than_end():
    range = Range( ((0, 100),) )
    assert_equal( range.parse_bytes( 'bytes=99-0'), None )

def test_parse_bytes_start_greater_than_last_end():
    range = Range( ((0, 100),) )
    assert_equal( range.parse_bytes( 'bytes=0-99,0-199'), None )

def test_parse_bytes_only_start():
    range = Range( ((0, 100),) )
    assert_equal( range.parse_bytes( 'bytes=0-'), ('bytes', [(0, None)]) )

# ContentRange class

def test_contentrange_bad_input():
    assert_raises( ValueError, ContentRange, None, 99, None )

def test_contentrange_repr():
    contentrange = ContentRange( 0, 99, 100 )
    assert_true( contentrange.__repr__(), '<ContentRange bytes 0-98/100>' )

def test_contentrange_str_length_none():
    contentrange = ContentRange( 0, 99, 100 )
    contentrange.length = None
    assert_equal( str(contentrange), 'bytes 0-98/*' )

def test_contentrange_str_start_none():
    contentrange = ContentRange( 0, 99, 100 )
    contentrange.start = None
    contentrange.stop = None
    assert_equal( str(contentrange), 'bytes */100' )

def test_contentrange_iter():
    contentrange = ContentRange( 0, 99, 100 )
    assert_true( type(contentrange.__iter__()), iter )

def test_cr_parse_ok():
    contentrange = ContentRange( 0, 99, 100 )
    assert_true( contentrange.parse( 'bytes 0-99/100' ).__class__, ContentRange )

def test_cr_parse_none():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( contentrange.parse( None ), None )

def test_cr_parse_no_bytes():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( contentrange.parse( '0-99 100' ), None )

def test_cr_parse_missing_slash():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( contentrange.parse( 'bytes 0-99 100' ), None )

def test_cr_parse_invalid_length():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( contentrange.parse( 'bytes 0-99/xxx' ), None )

def test_cr_parse_no_range():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( contentrange.parse( 'bytes 0 99/100' ), None )

def test_cr_parse_range_star():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( contentrange.parse( 'bytes */100' ).__class__, ContentRange )

def test_cr_parse_parse_problem_1():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( contentrange.parse( 'bytes A-99/100' ), None )

def test_cr_parse_parse_problem_2():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( contentrange.parse( 'bytes 0-B/100' ), None )

def test_cr_parse_content_invalid():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( contentrange.parse( 'bytes 99-0/100' ), None )

def test_contentrange_str_length_start():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( contentrange.parse('bytes 0 99/*'), None )

# _is_content_range_valid function

def test_is_content_range_valid_start_none():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( _is_content_range_valid( None, 99, 90), False )

def test_is_content_range_valid_stop_none():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( _is_content_range_valid( 99, None, 90), False )

def test_is_content_range_valid_start_stop_none():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( _is_content_range_valid( None, None, 90), True )

def test_is_content_range_valid_start_none():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( _is_content_range_valid( None, 99, 90), False )

def test_is_content_range_valid_length_none():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( _is_content_range_valid( 0, 99, None), True )

def test_is_content_range_valid_stop_greater_than_length_response():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( _is_content_range_valid( 0, 99, 90, response=True), False )

def test_is_content_range_valid_stop_greater_than_length():
    contentrange = ContentRange( 0, 99, 100 )
    assert_equal( _is_content_range_valid( 0, 99, 90), True )
