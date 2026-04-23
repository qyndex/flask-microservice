#!/usr/bin/env python3
"""Seed the database with sample data for development.

Usage:
    python seed.py                  # Uses DevelopmentConfig
    FLASK_CONFIG=config.TestingConfig python seed.py
"""
from __future__ import annotations

import json
import os
import sys

from app import create_app
from app.extensions import db
from app.models import Event, Job


SAMPLE_JOBS = [
    {
        "task_name": "myapp.tasks.process_payment",
        "status": "completed",
        "payload": json.dumps({"amount": 99.99, "currency": "USD", "customer_id": "cust-001"}),
        "result": json.dumps({"transaction_id": "txn-abc123", "status": "settled"}),
        "duration_seconds": 2.34,
    },
    {
        "task_name": "myapp.tasks.send_email",
        "status": "completed",
        "payload": json.dumps({"to": "user@example.com", "template": "welcome"}),
        "result": json.dumps({"message_id": "msg-xyz"}),
        "duration_seconds": 0.87,
    },
    {
        "task_name": "myapp.tasks.generate_report",
        "status": "running",
        "payload": json.dumps({"report_type": "monthly", "month": "2025-01"}),
    },
    {
        "task_name": "myapp.tasks.sync_inventory",
        "status": "pending",
        "payload": json.dumps({"warehouse": "us-east-1", "full_sync": True}),
    },
    {
        "task_name": "myapp.tasks.resize_images",
        "status": "failed",
        "payload": json.dumps({"batch_id": "batch-42", "sizes": [128, 256, 512]}),
        "error": "OSError: disk quota exceeded",
    },
]

SAMPLE_EVENTS = [
    {
        "event_type": "user.signup",
        "source": "auth-service",
        "severity": "info",
        "payload": json.dumps({"user_id": "u-001", "email": "alice@example.com"}),
        "metadata_json": json.dumps({"ip": "192.168.1.10", "user_agent": "Mozilla/5.0"}),
    },
    {
        "event_type": "order.created",
        "source": "order-service",
        "severity": "info",
        "payload": json.dumps({"order_id": "ord-100", "total": 149.99}),
        "metadata_json": json.dumps({"region": "us-east-1"}),
    },
    {
        "event_type": "payment.failed",
        "source": "billing-service",
        "severity": "error",
        "payload": json.dumps({"order_id": "ord-101", "reason": "insufficient_funds"}),
        "metadata_json": json.dumps({"retry_count": 2}),
    },
    {
        "event_type": "deploy.completed",
        "source": "ci-pipeline",
        "severity": "info",
        "payload": json.dumps({"version": "1.4.2", "commit": "a1b2c3d"}),
        "is_processed": True,
    },
    {
        "event_type": "rate_limit.exceeded",
        "source": "api-gateway",
        "severity": "warning",
        "payload": json.dumps({"client_ip": "10.0.0.5", "endpoint": "/api/v1/jobs"}),
        "metadata_json": json.dumps({"window": "60s", "limit": 100}),
    },
    {
        "event_type": "db.connection_pool_exhausted",
        "source": "monitoring",
        "severity": "critical",
        "payload": json.dumps({"pool_size": 20, "active": 20, "waiting": 5}),
        "metadata_json": json.dumps({"host": "db-primary.internal"}),
    },
]


def seed() -> None:
    """Insert sample jobs and events into the database."""
    config = os.environ.get("FLASK_CONFIG", "config.DevelopmentConfig")
    app = create_app(config)

    with app.app_context():
        db.create_all()

        # Check if data already exists
        existing_jobs = db.session.execute(db.select(db.func.count(Job.id))).scalar_one()
        existing_events = db.session.execute(db.select(db.func.count(Event.id))).scalar_one()

        if existing_jobs > 0 or existing_events > 0:
            print(f"Database already has data ({existing_jobs} jobs, {existing_events} events).")
            print("Drop tables first or use a fresh database. Skipping seed.")
            sys.exit(0)

        # Insert jobs
        for job_data in SAMPLE_JOBS:
            job = Job(**job_data)
            db.session.add(job)

        # Insert events
        for event_data in SAMPLE_EVENTS:
            event = Event(**event_data)
            db.session.add(event)

        db.session.commit()
        print(f"Seeded {len(SAMPLE_JOBS)} jobs and {len(SAMPLE_EVENTS)} events.")


if __name__ == "__main__":
    seed()
