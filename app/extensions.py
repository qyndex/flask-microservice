"""Shared extension instances for the Flask microservice."""
from celery import Celery
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
ma = Marshmallow()
migrate = Migrate()
redis_client = FlaskRedis()
celery_app = Celery()
