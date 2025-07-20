"""
Development settings for local development.

Use this settings module for local development:
DJANGO_SETTINGS_MODULE=munch.dev_settings python manage.py runserver
"""

from .settings import *

# Override production settings for development
DEBUG = True

# Development secret key (insecure but fine for local development)
SECRET_KEY = 'django-insecure-!72+)yngvc_4@u7+yq14zy4)+z#(r44ljvb#-a(ajx*3l_ux_8'