# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import importlib.util
import os
import re
import sys

# --------------------------------------------------------------------------
# Paths
#
# This `docs/` folder lives *inside* the addon, so the addon root is the parent
# directory and the folder autodoc has to import from is the grandparent — the
# one holding `dms_certify_portal/` as a package. The reference project
# (addons_project_github) puts `docs/` beside the addon instead, which is why
# its paths are one level shallower than these.
# --------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))

ADDON = "dms_certify_portal"
_ADDON_ROOT = os.path.abspath(os.path.join(_HERE, ".."))

sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

# -- Project information -----------------------------------------------------

project = "DMS Certificate Portal"
copyright = "2026, Méthode"
author = "Méthode"
release = "19.0.6.0.0"
version = "19.0"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.linkcode",
    "sphinx.ext.extlinks",
    "sphinx.ext.todo",
    "sphinx.ext.intersphinx",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# --------------------------------------------------------------------------
# What autodoc has to pretend exists.
#
# `odoo` is mocked unconditionally, even when a real Odoo is installed. Odoo 19
# asserts that every models.Model subclass is imported under `odoo.addons.*`
# (MetaModel raises "Invalid import of …, it should start with 'odoo.addons'"),
# so importing this addon as the plain `dms_certify_portal` package fails the
# moment a real MetaModel is in play. Mocking it keeps the docs buildable from a
# plain `pip install -r requirements.txt` venv, with no Odoo and no database.
#
# `pymupdf`/`fitz` and `qrcode` are the addon's own external dependencies, used
# by tools/seal.py. They are mocked only when genuinely absent, so an Odoo venv
# that has them reports real types.
# --------------------------------------------------------------------------
autodoc_mock_imports = ["odoo"]

for _optional in ("pymupdf", "fitz", "qrcode"):
    if importlib.util.find_spec(_optional) is None:
        autodoc_mock_imports.append(_optional)

autodoc_member_order = "bysource"
# No default `members`: the reference pages list what they document explicitly,
# so that prose can sit between entries. A blanket default would silently
# re-document every member a second time.
autodoc_default_options = {
    "show-inheritance": True,
}

# A stray `.. todo::` is a hole in the documentation, so make it loud rather
# than letting it build silently into a published page.
todo_include_todos = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# --------------------------------------------------------------------------
# Source links
#
# Most reference pages here are hand-written: an Odoo model is a `models.Model`
# subclass whose fields only exist once a registry is built, so there is nothing
# for autodoc to introspect without a database. `linkcode` still decorates those
# — it reads the `module`/`fullname` on the signature node, whoever emitted it —
# so every symbol gets a link out to the real source on GitHub, hand-written or
# autodoc'd alike.
#
# `viewcode` is deliberately NOT enabled: it and `linkcode` both claim the same
# "[source]" slot, and only one of them can resolve an unimportable module.
# --------------------------------------------------------------------------
GITHUB_REPO = "https://github.com/Methode-dev/dms-methode"
# Overridable so a tagged build can point its links at that tag rather than at
# a moving branch.
GITHUB_REF = os.environ.get("DMS_CERTIFY_DOCS_GIT_REF", "main")
# Where the addon sits inside that repository. `dms-methode` is a flat
# collection of addons, so this is just the addon name.
REPO_SUBDIR = ADDON

# Both spellings reach the same file: `dms_certify_portal.models.x` is what
# autodoc imports, `odoo.addons.dms_certify_portal.models.x` is the name the
# module answers to at runtime and therefore what the hand-written pages declare.
_MODULE_PREFIXES = ("odoo.addons.%s." % ADDON, "%s." % ADDON)


def _module_to_path(module):
    """Relative path of ``module`` inside the addon, or None if it is foreign."""
    for prefix in _MODULE_PREFIXES:
        if module.startswith(prefix):
            tail = module[len(prefix):]
            break
    else:
        return None
    relative = os.path.join(*tail.split(".")) + ".py"
    if not os.path.isfile(os.path.join(_ADDON_ROOT, relative)):
        return None
    return relative


def _find_line(relative_path, fullname):
    """Line number where ``fullname`` is defined, or None.

    Grepping the file rather than importing it: the whole point of the
    hand-written pages is that these modules cannot be imported here.
    """
    if not fullname:
        return None
    name = fullname.split(".")[-1]
    patterns = [
        re.compile(r"^\s*(?:async\s+)?(?:class|def)\s+%s\b" % re.escape(name)),
        # Module-level constants, and Odoo fields declared on a class body.
        re.compile(r"^\s*%s\s*(?::[^=]+)?=" % re.escape(name)),
    ]
    try:
        with open(os.path.join(_ADDON_ROOT, relative_path), encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return None
    for pattern in patterns:
        for number, line in enumerate(lines, start=1):
            if pattern.match(line):
                return number
    return None


def linkcode_resolve(domain, info):
    if domain != "py":
        return None
    relative = _module_to_path(info.get("module") or "")
    if not relative:
        return None
    url = "%s/blob/%s/%s/%s" % (GITHUB_REPO, GITHUB_REF, REPO_SUBDIR, relative)
    line = _find_line(relative, info.get("fullname"))
    return "%s#L%s" % (url, line) if line else url


# For everything that is not a Python object — view XML, data XML, the CSV
# access matrix, SCSS, JS. Used as :ghsrc:`views/menus.xml`.
extlinks = {
    "ghsrc": (
        "%s/blob/%s/%s/%%s" % (GITHUB_REPO, GITHUB_REF, REPO_SUBDIR),
        "%s",
    ),
}
extlinks_detect_hardcoded_links = True

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_title = "DMS Certificate Portal %s" % release
html_theme_options = {
    "navigation_depth": 3,
    "collapse_navigation": False,
}

rst_prolog = """
.. |addon| replace:: ``dms_certify_portal``
"""
