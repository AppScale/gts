require 'rubygems'
gem 'test-unit'
require 'test/unit'

$:.unshift File.join(File.dirname(__FILE__))

# AppController library tests
require 'tc_error_app'
require 'tc_helperfunctions'
require 'tc_infrastructure_manager_client'
require 'tc_zkinterface'


# AppController tests
require 'tc_djinn'
