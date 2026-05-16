"""SNS notifier."""

from __future__ import annotations

import os

from jqanywhere.notifications.base import Notifier


class SnsNotifier(Notifier):
    def __init__(self, topic_arn: str | None = None, endpoint_url: str | None = None):
        import boto3

        self.topic_arn = topic_arn or os.environ["SNS_TOPIC_ARN"]
        self.client = boto3.client("sns", endpoint_url=endpoint_url or None)

    def send(self, subject: str, message: str) -> None:
        self.client.publish(TopicArn=self.topic_arn, Subject=subject[:100], Message=message or "completed")
