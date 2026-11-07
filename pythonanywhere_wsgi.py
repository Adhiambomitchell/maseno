# Paste ALL of this into your PythonAnywhere WSGI file (Web tab > WSGI configuration file).
# Only change YOURUSERNAME. No secrets go here: they live in the .env file in the project folder.
import os
import sys

PROJECT = "/home/YOURUSERNAME/maseno-guide"

if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

from app import app as application  # noqa: E402
