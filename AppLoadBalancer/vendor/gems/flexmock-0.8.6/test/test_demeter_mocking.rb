#!/usr/bin/env ruby

require 'test/unit'
require 'flexmock'
require 'test/asserts'

class TestDemeterMocking < Test::Unit::TestCase
  include FlexMock::TestCase
  include FlexMock::FailureAssertion

  def test_demeter_mocking
    m = flexmock("A")
    m.should_receive("children.first").and_return(:first)
    assert_kind_of FlexMock, m
    assert_kind_of FlexMock, m.children
    assert_equal :first, m.children.first
  end

  def test_demeter_mocking_with_operators
    m = flexmock("A")
    m.should_receive("children.+@.last").and_return(:value)
    assert_kind_of FlexMock, m
    assert_kind_of FlexMock, m.children
    assert_kind_of FlexMock, + m.children
    assert_equal :value, (+ m.children).last
  end

  def test_demeter_mocking_with_multiple_operators
    m = flexmock("A")
    m.should_receive("+@.-@.~").and_return(:value)
    assert_equal :value, ~-+m
  end

  def test_multiple_demeter_mocks_on_same_branch_is_ok
    m = flexmock("A")
    m.should_receive("child.x.y.z.first").and_return(:first)
    m.should_receive("child.x.y.z.last").and_return(:last)
    assert_equal :first, m.child.x.y.z.first
    assert_equal :last, m.child.x.y.z.last
  end

  def test_multi_level_deep_demeter_violation
    a = flexmock("a")
    a.should_receive("b.c.d.e.f.g.h.i.j.k").and_return(:xyzzy)
    assert_equal :xyzzy, a.b.c.d.e.f.g.h.i.j.k
  end

  def test_final_method_can_have_multiple_expecations
    a = flexmock("a")
    a.should_receive("b.c.d.last").with(1).and_return(:one).once
    a.should_receive("b.c.d.last").with(2).and_return(:two).once
    assert_equal :one, a.b.c.d.last(1)
    assert_equal :two, a.b.c.d.last(2)
  end

  def test_conflicting_mock_declarations_raises_an_error
    m = flexmock("A")
    ex = assert_raise(FlexMock::UsageError) do
      m.should_receive("child").and_return(:xyzzy)
      m.should_receive("child.other").and_return(:other)
      m.child.other
    end
    assert_match(/conflicting/i, ex.message)
    assert_match(/mock\s+declaration/i, ex.message)
    assert_match(/child/i, ex.message)
  end

  def test_conflicting_mock_declarations_in_reverse_order_does_not_raise_error
    # Not all conflicting definitions can be detected.
    m = flexmock("A")
    assert_failure() do
      m.should_receive("child.other").and_return(:other)
      m.should_receive("child").and_return(:xyzzy)
      assert_equal :xyzzy, m.child.other
    end
  end

  def test_preestablishing_existing_mock_is_ok
    engine = flexmock("engine")
    car = flexmock("A")
    car.should_receive(:engine).and_return(engine)
    car.should_receive("engine.cylinder").and_return(:cyl)
    assert_equal :cyl, car.engine.cylinder
  end

  def test_quick_defs_can_use_demeter_mocking
    a = flexmock("a")
    a.should_receive("b.c.d.x").and_return(:x)
    a.should_receive("b.c.d.y").and_return(:y)
    a.should_receive("b.c.d.z").and_return(:z)
    assert_equal :x, a.b.c.d.x
    assert_equal :y, a.b.c.d.y
    assert_equal :z, a.b.c.d.z
  end

  def test_quick_defs_can_use_demeter_mocking_two
    a = flexmock("a", "b.c.d.xx" => :x, "b.c.d.yy" => :y, "b.c.d.zz" => :z)
    assert_equal :x, a.b.c.d.xx
    assert_equal :y, a.b.c.d.yy
    assert_equal :z, a.b.c.d.zz
  end

  def test_errors_on_ill_formed_method_names
    m = flexmock("a")
    [
      'a(2)', '0a', 'a-b', 'a b', ' ', 'a ', ' b', 'a!b', "a?b", 'a=b'
    ].each do |method|
      assert_raise FlexMock::UsageError do m.should_receive(method) end
    end
  end

  def test_no_errors_on_well_formed_method_names
    m = flexmock("a")
    [
      'a', 'a?', 'a!', 'a=', 'z0', 'save!'
    ].each do |method|
      assert_nothing_raised do m.should_receive(method) end
    end
  end

  def test_readme_example_1
    cog = flexmock("cog")
    cog.should_receive(:turn).once.and_return(:ok).mock
    joint = flexmock("gear", :cog => cog)
    axle = flexmock("axle", :universal_joint => joint)
    chassis = flexmock("chassis", :axle => axle)
    car = flexmock("car", :chassis => chassis)
    assert_equal :ok, car.chassis.axle.universal_joint.cog.turn
  end

  def test_readme_example_2
    car = flexmock("car")
    car.should_receive("chassis.axle.universal_joint.cog.turn" => :ok).once
    assert_equal :ok, car.chassis.axle.universal_joint.cog.turn
  end

  def test_readme_example_3
    car = flexmock("car")
    car.should_receive("chassis.axle.universal_joint.cog.turn").once.
      and_return(:ok)
    assert_equal :ok, car.chassis.axle.universal_joint.cog.turn
  end

end
