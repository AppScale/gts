#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.

# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

Spec::Runner.configure do |config|
   config.mock_with :flexmock
end

context "FlexMock in a RSpec example" do
  specify "should be able to create a mock" do
    m = flexmock()
  end
  
  specify "should have an error when a mock is not called" do
    m = flexmock("Expectation Failured")
    m.should_receive(:hi).with().once
  end
  
  specify "should be able to create a stub" do
    s = "Hello World"
    flexmock(:base, s).should_receive(:downcase).with().once.and_return("hello WORLD")
    
    s.downcase.should == "hello WORLD"
  end
  
  specify "Should show an example failure" do
    1.should == 2
  end

  specify "Should show how mocks are displayed in error messages" do
    m = flexmock("x")
    m.should == 2
  end

end
