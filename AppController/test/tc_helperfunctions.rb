# Programmer: Chris Bunch

$:.unshift File.join(File.dirname(__FILE__), "..", "lib")
require 'helperfunctions'


require 'rubygems'
require 'flexmock/test_unit'


class TestHelperFunctions < Test::Unit::TestCase
  def test_obscure_creds
    creds = {
      'ec2_access_key' => 'ABCDEFG',
      'ec2_secret_key' => 'HIJKLMN',
      'CLOUD1_EC2_ACCESS_KEY' => 'OPQRSTU',
      'CLOUD1_EC2_SECRET_KEY' => 'VWXYZAB'
    }

    expected = {
      'ec2_access_key' => '***DEFG',
      'ec2_secret_key' => '***KLMN',
      'CLOUD1_EC2_ACCESS_KEY' => '***RSTU',
      'CLOUD1_EC2_SECRET_KEY' => '***YZAB'
    }

    actual = HelperFunctions.obscure_creds(creds)
    assert_equal(expected['ec2_access_key'], actual['ec2_access_key'])
    assert_equal(expected['ec2_secret_key'], actual['ec2_secret_key'])
    assert_equal(expected['CLOUD1_EC2_ACCESS_KEY'],
      actual['CLOUD1_EC2_ACCESS_KEY'])
    assert_equal(expected['CLOUD1_EC2_SECRET_KEY'],
      actual['CLOUD1_EC2_SECRET_KEY'])
  end
end
