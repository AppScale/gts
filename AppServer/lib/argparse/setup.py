import sys, os

from setuptools import setup, find_packages

import argparse

long_description = open('README.txt').read()


setup_args = dict(
    name="argparse",
    version=argparse.__version__,
    description='Python command-line parsing library',
    long_description=long_description,
    author="Steven Bethard",
    author_email="steven.bethard@gmail.com",
    download_url="http://argparse.googlecode.com/files/argparse-%s.tar.gz" % (argparse.__version__, ),
    url="http://code.google.com/p/argparse/",
    license="Python Software Foundation License",
    keywords="argparse command line parser parsing",
    platforms="any",
    classifiers="""\
Development Status :: 5 - Production/Stable
Environment :: Console
Intended Audience :: Developers
License :: OSI Approved :: Python Software Foundation License
Operating System :: OS Independent
Programming Language :: Python
Programming Language :: Python :: 2
Programming Language :: Python :: 3
Programming Language :: Python :: 2.3
Programming Language :: Python :: 2.4
Programming Language :: Python :: 2.5
Programming Language :: Python :: 2.6
Programming Language :: Python :: 2.7
Programming Language :: Python :: 3.0
Programming Language :: Python :: 3.1
Programming Language :: Python :: 3.2
Topic :: Software Development""".splitlines(),
    py_modules=['argparse'],
)

if __name__ == '__main__':
    setup(**setup_args)

