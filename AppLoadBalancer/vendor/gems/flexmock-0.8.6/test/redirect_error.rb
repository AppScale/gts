require 'stringio'

class FlexMock
  module RedirectError
    def redirect_error
      require 'stringio'
      old_err = $stderr
      $stderr = StringIO.new
      yield
      $stderr.string
    ensure
      $stderr = old_err
    end
    private :redirect_error
  end
end
