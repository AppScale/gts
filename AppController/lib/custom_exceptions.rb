# Programmer: Navraj Chohan

# A class of exceptions that can be thrown if the AppController is put into an
# unrecoverable state, or a state that we would not normally expect a perfectly
# working AppScale system to get into.
class AppScaleException < StandardError
end


# A class of exceptions that can be thrown if the AppController fails to secure
# copy over a file to another node.
class AppScaleSCPException < StandardError
end


# A class of exceptions that can be thrown if the AppController believes that
# the node it is talking to has failed.
class FailedNodeException < AppScaleException
end


# A class of exceptions that can be thrown if the AppController 
# (or its associated libraries) attempts to execute shell commands which 
# do not return properly (specifically, not having a return value of zero).
class FailedShellExec < StandardError
end


# A class of exceptions that can be thrown when the AppController detects
# an application that should be running doesn't have entries in haproxy.
class AppNotRunningException < AppScaleException
end


# A class of exceptions that can be thrown when the AppController detects
# when an application's appservers are not running (ie the application is
# effectively down).
class AppIsDownException < AppScaleException
end
