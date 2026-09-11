# File walkthrough: `support_agent/__init__.py`

This file marks `support_agent` as a Python package, so its modules can be
imported and run with commands such as `python -m support_agent.data`.

It contains only a package description. Importing the package does not load
models, read the dataset, download files or call an API. Each module will load
its own optional resources when its corresponding operation is requested.

The root now contains only `__init__.py` and the main CLI `__main__.py`.
Feature packages group the implementation; their `__init__.py` files also only
describe the package. See [structure.md](structure.md) for the complete layout
and the package command entry points.
