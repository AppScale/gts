# Programmer: Navraj Chohan

# A class of exceptions that can be thrown if the AppController is put into an
# unrecoverable state, or a state that we would not normally expect a perfectly
# working AppScale system to get into.
class AppScaleException < Exception
end

# A class of exceptions that can be thrown if the AppController 
# (or its associated libraries) attempts to execute shell commands which 
# do not return properly (specifically, not having a return value of zero).
class FailedShellExec < Exception
end

