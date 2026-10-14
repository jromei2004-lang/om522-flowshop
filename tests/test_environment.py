"""Smoke test: the Pixi environment has the packages the project needs.

Placeholder until the three required tests exist. Without at least one test,
pytest exits with status 5 and `pixi run test` would report a failure.
"""


def test_required_packages_import():
    import matplotlib
    import numpy
    import pandas

    assert pandas.__version__
    assert numpy.__version__
    assert matplotlib.__version__
