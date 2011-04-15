#!/usr/bin/env ruby

require 'test/unit'
require 'flexmock/rails/view_mocking'

module ViewTests
  def test_view_mocks_as_stub
    should_render_view
    render "controller/new.rthml"
  end

  def test_fails_if_no_render
    should_render_view
    assert_raise(Test::Unit::AssertionFailedError) do
      flexmock_verify
    end
  end

  def test_view_mocks_with_expectation
    should_render_view("new")
    render "controller/new"
  end

  def test_view_mocks_with_expectation_fails_with_different_template
    should_render_view("new")
    render "controller/edit"
    assert_raise(Test::Unit::AssertionFailedError) do
      flexmock_verify
    end
  end

  def test_view_mocks_with_expectation_and_multiple_templates
    should_render_view("new")
    render "controller/edit", "controller/show", "controller/new"
  end

  private

  def pretend_to_be_rails_version(version)
    flexmock(self).should_receive(:rails_version).and_return(version)
  end
end

######################################################################
class TestRailsViewStubForVersionsUpTo_1_2_4 < Test::Unit::TestCase
  include FlexMock::TestCase
  include ViewTests

  def setup
    @controller_class = flexmock("controller class")
    @controller = flexmock("controller", :class => @controller_class)
    pretend_to_be_rails_version("1.2.4")
  end

  # Simulate Rails rendering in version 1.2.4
  def render(*names)
    vc = @controller.class.view_class
    v = vc.new
    v.assigns(:x => :y)
    v.render_file
    v.first_render
    names.each do |name|
      v.file_exists?(name)
    end
  end

end

######################################################################
class TestRailsViewStubForVersionsAfter_1_2_4 < Test::Unit::TestCase
  include FlexMock::TestCase
  include ViewTests

  def setup
    @controller_class = flexmock("controller class")
    @controller = flexmock("controller", :class => @controller_class)
    @response = flexmock("Response")
    pretend_to_be_rails_version("2.0")
  end

  # Simulate Rails rendering after Rails version 1.2.4
  def render(*names)
    v = @response.template
    v.assigns(:x => :y)
    v.render_file
    v.template_format
    v.view_paths
    v.pick_template_extension
    names.each do |name|
      v.file_exists?(name)
    end
  end

end

######################################################################
class TestRailsViewStubForVersionsAfter_2_0_2 < Test::Unit::TestCase
  include FlexMock::TestCase
  include ViewTests

  def setup
    @controller_class = flexmock("controller class")
    @controller = flexmock("controller", :class => @controller_class)
    @response = flexmock("Response")
    pretend_to_be_rails_version("2.0.2")
  end

  # Simulate Rails rendering after Rails version 2.0.2
  def render(*names)
    v = ActionView::Base.new
    v.assigns(:x => :y)
    v.template_format
    v.view_paths
    v.pick_template_extension
    names.each do |name|
      v.file_exists?(name)
    end
    v.render_file(names.last, nil, nil)
  end

end

class FlexMock
  module MockContainer
    module Rails
      module VERSION
        STRING = 1
      end
    end
  end
end

class TestRailsVersion < Test::Unit::TestCase
  include FlexMock::TestCase
  def test_rails_version_to_get_code_coverage
    rails_version
  end
end

# Test Helper Classes

module ActionView
  class Base
  end
end
