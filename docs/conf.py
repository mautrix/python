import os
import sys
sys.path.insert(0, os.path.abspath('..'))
import mautrix
mautrix.__optional_imports__ = True

project = 'mautrix-python'
copyright = '2021, Tulir Asokan'
author = 'Tulir Asokan'

release = mautrix.__version__

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.inheritance_diagram',
    'sphinx.ext.napoleon',
]

templates_path = ['_templates']

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

autodoc_typehints = "description"
autodoc_member_order = "groupwise"
autoclass_content = "class"
autodoc_class_signature = "separated"

autodoc_type_aliases = {
  "EventContent": "mautrix.types.EventContent",
  "StateEventContent": "mautrix.types.StateEventContent",
  "Event": "mautrix.types.Event",
}

autodoc_default_options = {
  "special-members": "__init__",
  "class-doc-from": "class",
  "members": True,
  "undoc-members": True,
  "show-inheritance": True,
}

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'aiohttp': ('https://aiohttp.readthedocs.io/en/stable/', None),
    'yarl': ('https://yarl.readthedocs.io/en/stable/', None),
}
