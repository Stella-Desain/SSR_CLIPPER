"""The package contract shared by authoring tools and clip consumers.

No editor, SSR application, GUI, network, or third party Python dependency.
"""
from .package import TemplateError, export_template, inspect_package, install_package, load_template, instantiate

__all__ = ["TemplateError", "export_template", "inspect_package", "install_package", "load_template", "instantiate"]
