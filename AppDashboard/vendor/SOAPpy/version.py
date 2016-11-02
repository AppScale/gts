try:
    import pkg_resources
    __version__ = pkg_resources.get_distribution("SOAPpy").version
except:
    __version__="xxx"
