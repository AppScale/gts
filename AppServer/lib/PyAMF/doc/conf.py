# -*- coding: utf-8 -*-
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.
#
# Documentation build configuration file.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this file.
#
# All configuration values have a default value; values that are commented out
# serve to show the default value.

import sys, os, time
from shutil import copyfile

from docutils.core import publish_parts

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute.
sys.path.insert(0, os.path.abspath('..'))
sys.path.append(os.path.abspath('.'))
sys.path.append(os.path.abspath('html'))

def rst2html(input, output):
    """
    Create html file from rst file.
    
    :param input: Path to rst source file
    :type: `str`
    :param output: Path to html output file
    :type: `str`
    """
    file = os.path.abspath(input)
    rst = open(file, 'r').read()
    html = publish_parts(rst, writer_name='html')
    body = html['html_body']

    tmp = open(output, 'w')
    tmp.write(body)
    tmp.close()
    
    return body

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
# 
# Grab sphinxcontrib.epydoc from http://packages.python.org/sphinxcontrib-epydoc
extensions = ['sphinx.ext.intersphinx', 'sphinxcontrib.epydoc']

# Paths that contain additional templates, relative to this directory.
templates_path = ['html']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8'

# create content template for the homepage
readme = rst2html('../README.txt', 'html/intro.html')
readme = copyfile('../CHANGES.txt', 'changelog.rst')

# General substitutions.
project = 'PyAMF'
url = 'http://pyamf.org'
description = 'AMF for Python'
copyright = "Copyright &#169; 2007-%s The <a href='%s'>%s</a> Project. All rights reserved." % (
            time.strftime('%Y'), url, project)

# We look for the __init__.py file in the current PyAMF source tree
# and replace the values accordingly.
import pyamf

# The full version, including alpha/beta/rc tags.
version = str(pyamf.version)

# The short X.Y version.
release = version[:3]

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
today_fmt = '%B %d, %Y'

# List of documents that shouldn't be included in the build.
#unused_docs = []

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['build', 'tutorials/examples']

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
#pygments_style = 'pygments'

# A list of ignored prefixes for module index sorting.
#modindex_common_prefix = []

# A dictionary mapping URIs to a list of regular expression.
#
# Each key of this dictionary is a base url of an epydoc-generated
# documentation. Each value is a list of regular expressions, the reference
# target must match (see re.match()) to be cross-referenced with the base url.
epydoc_mapping = {
   # TODO: don't harcode version nr
   'http://api.pyamf.org/0.6.1/': [r'pyamf\.'],
}

# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# Note: you can download the 'beam' theme from:
# http://github.com/collab-project/sphinx-themes
# and place it in a 'themes' directory relative to this config file.
html_theme = 'beam'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#html_theme_options = {}

# Add any paths that contain custom themes here, relative to this directory.
html_theme_path = ['themes']

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
html_title = '%s - %s' % (project, description)

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['html/static']

# The name of an image file (.ico) that is the favicon of the docs.
html_favicon = 'html/static/pyamf.ico'

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Additional templates that should be rendered to pages, maps page names to
# template names.
html_additional_pages = {
    'index': 'defindex.html',
    'tutorials/index': 'tutorials.html',
}

# If false, no module index is generated.
html_use_modindex = True

# If true, the reST sources are included in the HTML build as _sources/<name>.
html_copy_source = False

# Output an OpenSearch description file.
html_use_opensearch = 'http://pyamf.org'

# Output file base name for HTML help builder.
htmlhelp_basename = 'pyamf' + release.replace('.', '')

# Split the index
html_split_index = True


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'PyAMF.tex', html_title,
   copyright, 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
latex_logo = 'html/static/logo.png'

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# Additional stuff for the LaTeX preamble.
#latex_preamble = ''

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_use_modindex = True

# refer to the Python standard library.
intersphinx_mapping = {'python': ('http://docs.python.org', None)}
