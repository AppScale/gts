require 'flexmock'

class FlexMock
  module MockContainer

    def rails_version
      Rails::VERSION::STRING
    end

    # Declare that the Rails controller under test should render the
    # named view.  If a view template name is given, it will be an
    # error if the named view is not rendered during the execution of
    # the contoller action.  If no template name is given, then the
    # any view may be rendered. If no view is actually rendered, then
    # an assertion failure will occur.
    #
    #  def test_my_action_does_what_it_should
    #    should_render_view 'show'
    #   
    #    get :show, :id => 1
    #
    #    assert_response :success
    #  end
    #
    def should_render_view(template_name=nil)
      if rails_version <= '1.2.4'
        should_render_view_prior_version_124(template_name)
      elsif rails_version <= '2.0.0'
        should_render_view_after_version_124(template_name)
      elsif rails_version < '2.2'
        should_render_view_after_version_202(template_name)
      elsif rails_version < '2.3'
        should_render_view_22x(template_name)    
      else
        should_render_view_23x(template_name)    
      end
    end

    private

    # This version of should_render_view will work for Rails 1.2.4
    # (and prehaps some number of prior versions).
    def should_render_view_prior_version_124(template_name) # :nodoc:
      view = flexmock("MockView")
      view.should_receive(
        :assigns => {},
        :render_file => true,
        :render_partial => true,
        :first_render => "dummy_template"
        )
      if template_name
        view.should_receive(:file_exists?).with(/#{template_name}$/).once.
          and_return(true)
      end
      view.should_receive(:file_exists?).with(any).and_return(true)
      view_class = flexmock("MockViewClasss")
      view_class.should_receive(:new).and_return(view)
      flexmock(@controller.class).should_receive(:view_class).once.
        and_return(view_class)
    end

    # This version of should_render_view will work with versions of
    # Rails after Version 1.2.4.
    def should_render_view_after_version_124(template_name)
      view = flexmock("MockView")
      view.should_receive(
        :assigns => {},
        :render_file => true,
        :render_partial => true,
        :template_format => :dummy_format,
        :view_paths => :dummy_view_paths,
        :pick_template_extension => :dummy_extension
        )
      if template_name
        view.should_receive(:file_exists?).with(/#{template_name}$/).once.
          and_return(true)
      end
      view.should_receive(:file_exists?).with(any).and_return(true)
      
      # The number of times this is called changes from version 1.2.6
      # to 2.0.  The important thing is that it is checked at least once.
      flexmock(@response).should_receive(:template).and_return(view).
        at_least.once
    end
    
    # This version of should_render_view will work with versions of
    # Rails at Version 2.0.2 and after
    def should_render_view_after_version_202(template_name)
      viewmock = flexmock("ViewMock")
      viewmock.should_receive(
        :assigns => {},
        :pick_template_extension => ".html",
        :template_format =>nil,
        :view_paths => nil,
        :file_exists? => true,
        :first_render => "")
      if template_name
        viewmock.should_receive(:render_file).with(/\/#{template_name}$/, any, any).
          and_return(nil).once
        viewmock.should_receive(:render_file).and_return(nil)
      else
        viewmock.should_receive(:render_file).at_least.once.and_return(nil)
      end
      flexmock(ActionView::Base).should_receive(:new).and_return(viewmock)
    end

    # This version of should_render_view will work with versions of
    # Rails at Version 2.2.x.
    def should_render_view_22x(template_name)
      viewmock = flexmock("ViewMock")
      viewmock.should_receive(
        :helpers => viewmock,
        :include => nil,
        :template_format =>nil,
        :render => "RENDERED TEXT",
        :assigns => {})
      if template_name
        viewmock.should_receive(:_exempt_from_layout?).with(/\/#{template_name}$/).
          and_return(true).once
        viewmock.should_receive(:_exempt_from_layout?).and_return(true)
      else
        viewmock.should_receive(:_exempt_from_layout?).at_least.once.and_return(true)
      end
      flexmock(ActionView::Base).should_receive(:new).and_return(viewmock)
    end

    # This version of should_render_view will work with versions of
    # Rails at Version 2.3.x.
    def should_render_view_23x(template_name)
      viewmock = flexmock("ViewMock")
      viewmock.should_receive(
        :view_paths => viewmock,
        :render => "RENDERED TEXT")
      if template_name
        viewmock.should_receive(:find_template).
          with(/\/#{template_name}$/, any).
          and_return(FlexMock.undefined).
          at_least.once
      end
      viewmock.should_ignore_missing
      flexmock(ActionView::Base).should_receive(:new).and_return(viewmock)
    end
  end
end
