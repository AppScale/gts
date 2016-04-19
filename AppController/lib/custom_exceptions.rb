# Custom exceptions raised in AppController context.

# A class of exceptions that can be thrown if HAProxy has no knowledge
# of running application backends. The HAProxy status report is empty for that
# application.
class ApplicationBackendMissing < StandardError
end


# A class of exceptions that can be thrown if the AppController is put into an
# irrecoverable state, or a state that we would not normally expect a perfectly
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
