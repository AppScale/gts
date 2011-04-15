ActionController::Routing::Routes.draw do |map|

  map.with_options :controller => "users" do |user|
    user.new          '/users/new',          :action => :new
    user.create       '/users/create',       :action => :create
    user.login        '/users/login',        :action => :login
    user.logout       '/users/logout',       :action => :logout
    user.authenticate '/users/authenticate', :action => :authenticate   
    user.confirm      '/users/confirm',      :action => :confirm
    user.verify       '/users/verify',       :action => :verify
  end

  map.connect "/login", :controller => :users, :action => :login
  map.connect "/logout", :controller => :users, :action => :logout

  map.connect "/status", :controller => :status, :action => :cloud

  map.connect "/authorize", :controller => :authorize, :action => :cloud
  map.connect "/authorize/update", :controller => :authorize, :action => :update

  map.with_options :controller => "apps" do |app|
    app.new     '/apps/new',     :action => :new
    app.create  '/apps/create',  :action => :create
    app.upload  '/apps/upload',  :action => :upload
    app.delete  '/apps/delete',  :action => :delete
    app.destroy '/apps/destroy', :action => :destroy
  end

  map.connect "/apps/:name/*anything", :controller => :apps, :action => :redirect, :id => :name

  map.root :controller => :landing
end
