from django.db import models
from projects.models import Project
from teams.models import Team

from .service_backends.slack import SlackBackend
from .service_backends.mattermost import MattermostBackend
from .service_backends.discord import DiscordBackend
from .service_backends.msteams import MsTeamsBackend
from .service_backends.telegram import TelegramBackend
from .service_backends.google_chat import GoogleChatBackend
from .service_backends.custom import CustomBackend


def get_alert_service_kind_choices():
    # As a callable to avoid non-DB-affecting migrations for adding new kinds.
    # Messaging backends don't need translations since they are brand names.
    return [
        ("discord", "Discord"),
        ("google_chat", "Google Chat"),
        ("mattermost", "Mattermost"),
        ("msteams", "Microsoft Teams"),
        ("slack", "Slack"),
        ("telegram", "Telegram"),
        ("custom", "Custom"),
    ]


def get_service_config_model(config_kind="project"):
    # Lets async backend tasks (which only get a bare service_config_id, not a model instance) resolve the right
    # table: MessagingServiceConfig and TeamMessagingServiceConfig have independent id sequences, so guessing wrong
    # would silently drop failure-tracking info, or worse, overwrite an unrelated config's.
    if config_kind == "team":
        return TeamMessagingServiceConfig
    return MessagingServiceConfig


def get_alert_service_backend_class(kind):
    if kind == "discord":
        return DiscordBackend
    if kind == "google_chat":
        return GoogleChatBackend
    if kind == "mattermost":
        return MattermostBackend
    if kind == "msteams":
        return MsTeamsBackend
    if kind == "slack":
        return SlackBackend
    if kind == "telegram":
        return TelegramBackend
    if kind == "custom":
        return CustomBackend
    raise ValueError(f"Unknown backend kind: {kind}")


class MessagingServiceConfig(models.Model):
    CONFIG_KIND = "project"  # disambiguates which table a bare service_config_id (e.g. in an async task) refers to

    project = models.ForeignKey(Project, on_delete=models.DO_NOTHING, related_name="service_configs")
    display_name = models.CharField(max_length=100, blank=False,
                                    help_text='For display in the UI, e.g. "#general on company Slack"')

    kind = models.CharField(choices=get_alert_service_kind_choices, max_length=20, default="slack")

    config = models.TextField(blank=False)

    # Alert backend failure tracking
    last_failure_timestamp = models.DateTimeField(null=True, blank=True,
                                                  help_text="When the last failure occurred")
    last_failure_status_code = models.IntegerField(null=True, blank=True,
                                                   help_text="HTTP status code of the failed request")
    last_failure_response_text = models.TextField(null=True, blank=True,
                                                  help_text="Response text from the failed request")
    last_failure_is_json = models.BooleanField(null=True, blank=True,
                                               help_text="Whether the response was valid JSON")
    last_failure_error_type = models.CharField(max_length=100, null=True, blank=True,
                                               help_text="Type of error that occurred (e.g., 'requests.HTTPError')")
    last_failure_error_message = models.TextField(null=True, blank=True,
                                                  help_text="Error message from the exception")

    def get_backend(self):
        return get_alert_service_backend_class(self.kind)(self)

    def clear_failure_status(self):
        """Clear all failure tracking fields on successful operation"""
        self.last_failure_timestamp = None
        self.last_failure_status_code = None
        self.last_failure_response_text = None
        self.last_failure_is_json = None
        self.last_failure_error_type = None
        self.last_failure_error_message = None

    def has_recent_failure(self):
        """Check if this config has a recent failure"""
        return self.last_failure_timestamp is not None

    def display_scope_name(self):
        return self.project.name


class TeamMessagingServiceConfig(models.Model):
    CONFIG_KIND = "team"  # disambiguates which table a bare service_config_id (e.g. in an async task) refers to

    # Team-level messaging services are a separate, additive concept alongside per-project MessagingServiceConfig
    # (both fire independently for a given project's alerts): a single config here can fan out to any subset of the
    # team's projects, so admins have one place to manage a service that multiple projects should alert into.
    team = models.ForeignKey(Team, on_delete=models.DO_NOTHING, related_name="service_configs")
    projects = models.ManyToManyField(Project, blank=True, related_name="team_service_configs",
                                      help_text="Which projects in this team this service sends alerts for")
    auto_add_new_projects = models.BooleanField(
        "Automatically add new projects", default=False,
        help_text="New projects created in this team will be added to this service automatically")

    display_name = models.CharField(max_length=100, blank=False,
                                    help_text='For display in the UI, e.g. "#general on company Slack"')

    kind = models.CharField(choices=get_alert_service_kind_choices, max_length=20, default="slack")

    config = models.TextField(blank=False)

    # Alert backend failure tracking
    last_failure_timestamp = models.DateTimeField(null=True, blank=True,
                                                  help_text="When the last failure occurred")
    last_failure_status_code = models.IntegerField(null=True, blank=True,
                                                   help_text="HTTP status code of the failed request")
    last_failure_response_text = models.TextField(null=True, blank=True,
                                                  help_text="Response text from the failed request")
    last_failure_is_json = models.BooleanField(null=True, blank=True,
                                               help_text="Whether the response was valid JSON")
    last_failure_error_type = models.CharField(max_length=100, null=True, blank=True,
                                               help_text="Type of error that occurred (e.g., 'requests.HTTPError')")
    last_failure_error_message = models.TextField(null=True, blank=True,
                                                  help_text="Error message from the exception")

    def get_backend(self):
        return get_alert_service_backend_class(self.kind)(self)

    def clear_failure_status(self):
        """Clear all failure tracking fields on successful operation"""
        self.last_failure_timestamp = None
        self.last_failure_status_code = None
        self.last_failure_response_text = None
        self.last_failure_is_json = None
        self.last_failure_error_type = None
        self.last_failure_error_message = None

    def has_recent_failure(self):
        """Check if this config has a recent failure"""
        return self.last_failure_timestamp is not None

    def display_scope_name(self):
        return self.team.name
