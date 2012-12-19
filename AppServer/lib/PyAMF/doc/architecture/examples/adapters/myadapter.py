from pyamf.adapters import register_adapter


def when_imported(mod):
    """
    This function is called immediately after mymodule has been imported.
    It configures PyAMF to encode a list when an instance of mymodule.CustomClass
    is encountered.
    """
    import pyamf

    pyamf.add_type(mod.CustomClass, lambda obj: list(obj))


register_adapter('mymodule', when_imported)