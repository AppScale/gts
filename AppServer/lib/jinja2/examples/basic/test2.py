from __pypy__ import tproxy


def make_proxy(obj, proxy):
    if tproxy is None:
        return proxy
    def operation_handler(operation, *args, **kwargs):
        if operation in ('__getattribute__', '__getattr__'):
            return getattr(proxy, args[0])
        elif operation == '__setattr__':
            proxy.__setattr__(*args, **kwargs)
        else:
            return getattr(proxy, operation)(*args, **kwargs)
    return tproxy(type(obj), operation_handler)
