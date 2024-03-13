from datetime import datetime
import os
import sys
import subprocess

sys.path.insert(0, os.path.abspath(".."))

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information ------
project = "vessim"
author = "Philipp Wiesner"
copyright = f"{datetime.now().year} {author}"


# Fetch the latest Git tag
def get_latest_git_tag():
    tag_description = (
        subprocess.check_output(["git", "describe", "--tags"], cwd=os.path.dirname(__file__))
        .decode("utf-8")
        .strip()
    )
    return tag_description.split("-")[0]


version = get_latest_git_tag()


# The full version, including alpha/beta/rc tags
release = version

# -- General configuration -------

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "nbsphinx",
]

autodoc_member_order = "bysource"

html_css_files = ["custom.css"]
html_static_path = ["_static"]
html_logo = "_static/logo.png"

html_theme_options = {
    "top_of_page_button": None,
    "light_css_variables": {
        "color-brand-primary": "#4FACB3",
        "color-brand-content": "#4FACB3",
    },
    "dark_css_variables": {
        "color-brand-primary": "#4FACB3",
        "color-brand-content": "#4FACB3",
    },
}

html_title = f"Vessim {version}"
templates_path = ["_templates"]

source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

pygments_style = "default"
pygments_dark_style = "gruvbox-dark"

# -- Options for HTML output ------
html_theme = "furo"
