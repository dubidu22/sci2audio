"""Conformance suites every plugin must pass (#6, PE-07, PE-10).

Plain functions that raise `AssertionError` with a clear message, so plugin authors can
call them from any test runner. They import neither pytest nor hypothesis (those are not
run-time dependencies). This package sits beside `app` in the layers: it may import the
pipeline stages and core; nothing imports it.
"""
