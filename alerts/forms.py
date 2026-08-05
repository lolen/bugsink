from django import forms
from django.forms import ModelForm

from .models import MessagingServiceConfig, TeamMessagingServiceConfig

# Matches the checkbox styling used elsewhere in the redesigned UI (e.g. issue_list.html's row checkboxes).
_CHECKBOX_CLASS = ("rounded-sm bg-surface border-edge checked:bg-accent checked:border-accent "
                   "text-accent focus:ring-accent-wash cursor-pointer")


class MessagingServiceConfigNewForm(ModelForm):

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project

    class Meta:
        model = MessagingServiceConfig
        fields = ["display_name", "kind"]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.project = self.project
        if commit:
            instance.save()
        return instance


class MessagingServiceConfigEditForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        model = MessagingServiceConfig
        fields = ["display_name"]


class TeamMessagingServiceConfigNewForm(ModelForm):

    def __init__(self, team, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        # widget must be swapped in *before* queryset is assigned: setting .queryset syncs .widget.choices, and a
        # widget swapped in afterward would keep its default (empty) choices, rendering no checkboxes at all.
        self.fields["projects"].widget = forms.CheckboxSelectMultiple(attrs={"class": _CHECKBOX_CLASS})
        self.fields["projects"].queryset = team.project_set.filter(is_deleted=False)
        self.fields["auto_add_new_projects"].widget.attrs["class"] = _CHECKBOX_CLASS

    class Meta:
        model = TeamMessagingServiceConfig
        fields = ["display_name", "kind", "projects", "auto_add_new_projects"]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.team = self.team
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class TeamMessagingServiceConfigEditForm(ModelForm):

    def __init__(self, team, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # widget must be swapped in *before* queryset is assigned: setting .queryset syncs .widget.choices, and a
        # widget swapped in afterward would keep its default (empty) choices, rendering no checkboxes at all.
        self.fields["projects"].widget = forms.CheckboxSelectMultiple(attrs={"class": _CHECKBOX_CLASS})
        self.fields["projects"].queryset = team.project_set.filter(is_deleted=False)
        self.fields["auto_add_new_projects"].widget.attrs["class"] = _CHECKBOX_CLASS

    class Meta:
        model = TeamMessagingServiceConfig
        fields = ["display_name", "projects", "auto_add_new_projects"]
