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

# Indicates that a revision's source code is invalid.
class InvalidSource < StandardError
end

# Indicates that a service was unable to complete a correctly-formed request.
class InternalError < StandardError
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

# Indicates that the user being created already exists.
class UserExists < StandardError
end
