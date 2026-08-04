from django.db.models.signals import post_save
from django.dispatch import receiver

from projects.models import Project


@receiver(post_save, sender=Project)
def auto_add_new_project_to_team_messaging_services(sender, instance, created, **kwargs):
    if not created or not instance.team_id:
        return

    from .models import TeamMessagingServiceConfig

    for config in TeamMessagingServiceConfig.objects.filter(team_id=instance.team_id, auto_add_new_projects=True):
        config.projects.add(instance)
