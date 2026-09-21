from django.core.management.base import BaseCommand, CommandError

from projects.models import Project
from issues.tasks import cleanup_stale_unresolved_issues_sync, get_stale_unresolved_issues


class Command(BaseCommand):
    help = (
        "Delete unresolved issues that have not been seen for longer than each project's configured "
        "'stale_issue_max_age_days'. Projects with this set to 0 (the default) are skipped."
    )

    def add_arguments(self, parser):
        parser.add_argument("--project-id", type=int, help="Only process a single project.")
        parser.add_argument("--dry-run", action="store_true", help="Show how many issues would be deleted.")

    def handle(self, *args, **options):
        project_id = options["project_id"]

        if project_id is not None:
            if not Project.objects.filter(pk=project_id).exists():
                raise CommandError(f"Project {project_id} does not exist.")

        if options["dry_run"]:
            from datetime import timedelta

            from django.utils import timezone

            from projects.models import StaleIssueDeletionScope

            queryset = Project.objects.filter(stale_issue_max_age_days__gt=0)
            if project_id is not None:
                queryset = queryset.filter(id=project_id)

            total = 0
            for project in queryset:
                cutoff = timezone.now() - timedelta(days=project.stale_issue_max_age_days)
                include_muted = project.stale_issue_deletion_scope == StaleIssueDeletionScope.UNRESOLVED_AND_MUTED
                count = get_stale_unresolved_issues(project, cutoff, include_muted).count()
                if count:
                    self.stdout.write(f"Project {project.id} ({project.name}): would delete {count} issue(s).")
                total += count

            issue_label = "issue" if total == 1 else "issues"
            self.stdout.write(f"Would delete {total} stale unresolved {issue_label} in total.")
            return

        cleanup_stale_unresolved_issues_sync(project_id)
        self.stdout.write(self.style.SUCCESS("Stale unresolved issue cleanup complete."))
