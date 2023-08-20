"""
This is a setup.py script generated by py2applet

Usage:
    set filepath.txt to no
    python3 setup.py py2app
"""

from setuptools import setup

APP = ['main.py']
DATA_FILES = ['filepath.txt']
OPTIONS = {}

setup(
    name='Personal Finance Dashboard',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
