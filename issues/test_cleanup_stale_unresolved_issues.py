import io
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from bugsink.test_utils import TransactionTestCase25251 as TransactionTestCase
from events.factories import create_event
from issues.factories import get_or_create_issue
from issues.models import Issue
from issues.tasks import mark_stale_unresolved_issues_sync
from projects.models import Project, StaleIssueDeletionScope


class CleanupStaleUnresolvedIssuesCommandTestCase(TransactionTestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Cleanup", stale_issue_max_age_days=10)
        self.stale_unresolved = self.create_issue("StaleUnresolved", 20)
        self.recent_unresolved = self.create_issue("RecentUnresolved", 5)
        self.stale_muted = self.create_issue("StaleMuted", 20, is_muted=True)
        self.stale_resolved = self.create_issue("StaleResolved", 20, is_resolved=True)

        self.project.issue_count = 4
        self.project.save(update_fields=["issue_count"])

    def create_issue(self, exception_type, age_days, is_muted=False, is_resolved=False):
        issue, _ = get_or_create_issue(
            self.project,
            {"exception": {"values": [{"type": exception_type}]}},
        )
        create_event(self.project, issue=issue)
        seen = timezone.now() - timedelta(days=age_days)
        Issue.objects.filter(id=issue.id).update(
            first_seen=seen, last_seen=seen, is_muted=is_muted, is_resolved=is_resolved, stored_event_count=1)
        issue.refresh_from_db()
        return issue

    def run_command(self, *args):
        stdout = io.StringIO()
        call_command("cleanup_stale_unresolved_issues", *args, stdout=stdout, no_color=True)
        return stdout.getvalue()

    def test_command_deletes_stale_unresolved_issues_only(self):
        output = self.run_command()

        self.assertEqual("Stale unresolved issue cleanup complete.\n", output)
        self.assertFalse(Issue.objects.filter(id=self.stale_unresolved.id).exists())
        self.assertTrue(Issue.objects.filter(id=self.recent_unresolved.id).exists())
        self.assertTrue(Issue.objects.filter(id=self.stale_muted.id).exists())
        self.assertTrue(Issue.objects.filter(id=self.stale_resolved.id).exists())
        self.project.refresh_from_db()
        self.assertEqual(3, self.project.issue_count)

    def test_scope_unresolved_and_muted_also_deletes_muted(self):
        self.project.stale_issue_deletion_scope = StaleIssueDeletionScope.UNRESOLVED_AND_MUTED
        self.project.save(update_fields=["stale_issue_deletion_scope"])

        self.run_command()

        self.assertFalse(Issue.objects.filter(id=self.stale_unresolved.id).exists())
        self.assertFalse(Issue.objects.filter(id=self.stale_muted.id).exists())
        self.assertTrue(Issue.objects.filter(id=self.stale_resolved.id).exists())

    def test_max_age_days_zero_disables_cleanup(self):
        self.project.stale_issue_max_age_days = 0
        self.project.save(update_fields=["stale_issue_max_age_days"])

        self.run_command()

        self.assertTrue(Issue.objects.filter(id=self.stale_unresolved.id).exists())

    def test_dry_run_does_not_delete(self):
        output = self.run_command("--dry-run")

        self.assertIn(f"Project {self.project.id} (Cleanup): would delete 1 issue(s).", output)
        self.assertIn("Would delete 1 stale unresolved issue in total.", output)
        self.assertTrue(Issue.objects.filter(id=self.stale_unresolved.id).exists())

    def test_project_id_filters_to_a_single_project(self):
        other_project = Project.objects.create(name="Other", stale_issue_max_age_days=10)
        seen = timezone.now() - timedelta(days=20)
        other_issue, _ = get_or_create_issue(other_project, {"exception": {"values": [{"type": "Other"}]}})
        create_event(other_project, issue=other_issue)
        Issue.objects.filter(id=other_issue.id).update(first_seen=seen, last_seen=seen, stored_event_count=1)

        self.run_command("--project-id", str(self.project.id))

        self.assertFalse(Issue.objects.filter(id=self.stale_unresolved.id).exists())
        self.assertTrue(Issue.objects.filter(id=other_issue.id).exists())

    def test_rejects_unknown_project_id(self):
        with self.assertRaisesMessage(CommandError, "Project 999999 does not exist."):
            self.run_command("--project-id", "999999")


class MarkStaleUnresolvedIssuesTestCase(TransactionTestCase):
    def test_updates_project_counts(self):
        project = Project.objects.create(name="A", issue_count=1, stale_issue_max_age_days=10)
        issue, _ = get_or_create_issue(project, {"exception": {"values": [{"type": "Stale"}]}})
        create_event(project, issue=issue)
        seen = timezone.now() - timedelta(days=20)
        Issue.objects.filter(id=issue.id).update(first_seen=seen, last_seen=seen, stored_event_count=1)

        mark_stale_unresolved_issues_sync()

        self.assertTrue(Issue.objects.get(id=issue.id).is_deleted)
        project.refresh_from_db()
        self.assertEqual(0, project.issue_count)
