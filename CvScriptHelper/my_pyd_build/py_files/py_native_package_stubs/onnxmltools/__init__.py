# tf_stubs/tensorflow/__init__.py
__version__ = "99.99.99-stub"
def __getattr__(name):
    raise ImportError(f"tensorflow.{name} not available (stub)")