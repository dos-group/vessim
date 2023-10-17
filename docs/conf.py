import os
import sys

from datetime import datetime

sys.path.insert(0, os.path.abspath('..'))

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'vessim'
author = 'Philipp Wiesner'
copyright = f"{datetime.now().year} {author}"

version = '0'
# The full version, including alpha/beta/rc tags
release = version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx.ext.napoleon', 'sphinx_copybutton']

html_static_path = ["_static"]
html_logo = "_static/logo_transparent.png"
html_theme_options = {
    "source_repository": "https://github.com/dos-group/vessim",
    "source_branch": "main",
    "source_directory": "docs/",
}
html_title = "Vessim Documentation"
templates_path = ['_templates']

source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

pygments_style = "sphinx"
pygments_dark_style = "monokai"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']
