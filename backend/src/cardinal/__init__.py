"""Cardinal: deterministic synthetic data generator for US retail credit cards.

This package is the walking skeleton. It proves the architecture end to end
with a minimal slice: YAML specs in, deterministic Parquet out, one real
event handler, one real lagged dependency. Everything later plugs into the
three protocols in `cardinal.spec` and nothing else.
"""

__version__ = "0.1.0"
