import os


# Minimal config for the MVP.
# We keep everything driven by environment variables to avoid hardcoding secrets
# in the image or in git.
SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

# Superset metadata database.
SQLALCHEMY_DATABASE_URI = os.environ["SQLALCHEMY_DATABASE_URI"]

SQLALCHEMY_TRACK_MODIFICATIONS = False
