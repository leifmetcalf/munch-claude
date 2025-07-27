"""
Development settings for local development.

Use this settings module for local development:
DJANGO_SETTINGS_MODULE=munch.dev_settings python manage.py runserver
"""

import os

# Set development secret key before importing production settings
os.environ['SECRET_KEY'] = 'django-insecure-!72+)yngvc_4@u7+yq14zy4)+z#(r44ljvb#-a(ajx*3l_ux_8'

from .settings import *

# Override production settings for development
DEBUG = True

# Clear ALLOWED_HOSTS for development (allows all hosts when DEBUG=True)
ALLOWED_HOSTS = []
