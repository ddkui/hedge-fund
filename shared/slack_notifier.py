"""
Slack notification utility for research alerts.
Sends formatted messages to configured Slack channels.
"""
import logging
import os
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Send formatted messages to Slack."""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Slack notifier.

        Args:
            webhook_url: Slack webhook URL. Defaults to SLACK_WEBHOOK_URL env var.
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")

    def send_message(
        self,
        text: str,
        channel: Optional[str] = None,
        username: str = "Research Bot"
    ) -> bool:
        """
        Send a simple text message to Slack.

        Args:
            text: Message text
            channel: Slack channel name (e.g., "#research")
            username: Bot username

        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            logger.warning("SLACK_WEBHOOK_URL not configured, skipping notification")
            return False

        payload = {
            "text": text,
            "username": username
        }

        if channel:
            payload["channel"] = channel

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5
            )
            response.raise_for_status()
            logger.info(f"Slack message sent to {channel or 'default channel'}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False

    def send_research_alert(
        self,
        paper_title: str,
        paper_authors: str,
        overall_score: float,
        paper_url: str,
        channel: str = "#research",
        suggested_tags: Optional[str] = None
    ) -> bool:
        """
        Send formatted research paper alert to Slack.

        Args:
            paper_title: Title of the paper
            paper_authors: Authors of the paper
            overall_score: Overall relevance score (0-100)
            paper_url: Link to the paper
            channel: Slack channel name
            suggested_tags: Comma-separated suggested tags

        Returns:
            True if successful, False otherwise
        """
        text = f"""
:memo: *New Research Paper Alert*

*Title:* {paper_title}

*Authors:* {paper_authors}

*Score:* {overall_score:.1f}/100

*Paper:* <{paper_url}|View on arXiv>

{f"*Suggested Tags:* {suggested_tags}" if suggested_tags else ""}
"""
        return self.send_message(
            text=text.strip(),
            channel=channel,
            username="Research Bot"
        )

    def send_github_issue_notification(
        self,
        issue_title: str,
        issue_body_preview: str,
        paper_url: str,
        channel: str = "#issues",
        implementability_score: float = 0.0,
        strategic_score: float = 0.0
    ) -> bool:
        """
        Send formatted GitHub issue creation notification.

        Args:
            issue_title: Title of the generated issue
            issue_body_preview: First 200 chars of issue body
            paper_url: Link to source paper
            channel: Slack channel name
            implementability_score: Implementability score (0-100)
            strategic_score: Strategic value score (0-100)

        Returns:
            True if successful, False otherwise
        """
        preview = issue_body_preview[:200] + "..." if len(issue_body_preview) > 200 else issue_body_preview

        text = f"""
:github: *New GitHub Issue Draft*

*Issue:* {issue_title}

*Preview:* {preview}

*Scores:*
  • Implementability: {implementability_score:.1f}/100
  • Strategic Value: {strategic_score:.1f}/100

*Paper:* <{paper_url}|View Source>
"""
        return self.send_message(
            text=text.strip(),
            channel=channel,
            username="Issue Bot"
        )

    def send_error_notification(
        self,
        error_message: str,
        context: str = "Research Agent",
        channel: str = "#alerts"
    ) -> bool:
        """
        Send error notification to Slack.

        Args:
            error_message: Error message to send
            context: Context/source of the error
            channel: Slack channel name

        Returns:
            True if successful, False otherwise
        """
        text = f"""
:warning: *Error Alert*

*Context:* {context}

*Error:* {error_message}
"""
        return self.send_message(
            text=text.strip(),
            channel=channel,
            username="Alert Bot"
        )

    def send_summary_notification(
        self,
        papers_fetched: int,
        papers_scored: int,
        issues_created: int,
        top_paper_title: Optional[str] = None,
        top_paper_score: float = 0.0,
        channel: str = "#research"
    ) -> bool:
        """
        Send job completion summary to Slack.

        Args:
            papers_fetched: Total papers fetched
            papers_scored: Total papers scored
            issues_created: Total issues created
            top_paper_title: Title of highest-scoring paper
            top_paper_score: Score of highest-scoring paper
            channel: Slack channel name

        Returns:
            True if successful, False otherwise
        """
        text = f"""
:bar_chart: *Research Job Summary*

*Metrics:*
  • Papers Fetched: {papers_fetched}
  • Papers Scored: {papers_scored}
  • Issues Created: {issues_created}

{f"*Top Paper:* {top_paper_title} ({top_paper_score:.1f}/100)" if top_paper_title else ""}
"""
        return self.send_message(
            text=text.strip(),
            channel=channel,
            username="Research Bot"
        )
