"""Form helpers for the users app."""

from __future__ import annotations

from typing import Iterable, Sequence

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group

from apps.users.constants import ADMINS_GROUP_NAME, UserRole, groups_for_roles
from apps.users.models import BoardMemberProfile


class BoardSignatureForm(forms.ModelForm):
    """Allow board members to upload their signature image."""

    class Meta:
        model = BoardMemberProfile
        fields = ["signature_image"]
        labels = {"signature_image": "Digital signature"}
        help_texts = {
            "signature_image": "Upload an image of your signature (PNG or JPG).",
        }
        widgets = {
            "signature_image": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class AdminUserCreationForm(UserCreationForm):
    """Create new platform users with role assignments."""

    roles = forms.MultipleChoiceField(
        choices=[(role.value, role.value.title()) for role in UserRole],
        widget=forms.CheckboxSelectMultiple,
        label="Roles",
        help_text="Assign one or more roles to control the user's access.",
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roles"].required = True
        self._selected_roles: Sequence[UserRole] = []

    def clean_roles(self) -> Sequence[UserRole]:
        raw_roles: Iterable[str] = self.cleaned_data.get("roles") or []
        if not raw_roles:
            raise forms.ValidationError("Select at least one role for the user.")

        normalised_roles = []
        for raw_role in raw_roles:
            try:
                normalised_roles.append(UserRole(raw_role))
            except ValueError as exc:
                raise forms.ValidationError("Unknown role selected.") from exc

        self._selected_roles = tuple(normalised_roles)
        return self._selected_roles

    def save(self, commit: bool = True):  # type: ignore[override]
        user = super().save(commit=False)

        roles: Sequence[UserRole] = self.cleaned_data.get("roles", ())
        self._selected_roles = tuple(roles)
        is_staff = any(role in {UserRole.ADMIN, UserRole.STAFF} for role in roles)
        is_superuser = UserRole.ADMIN in roles

        user.is_staff = is_staff
        user.is_superuser = is_superuser

        if commit:
            user.save()
            self._assign_groups(user, roles)

        return user

    def _assign_groups(self, user, roles: Sequence[UserRole]) -> None:
        group_names = groups_for_roles(roles)
        if UserRole.ADMIN not in roles:
            group_names.discard(ADMINS_GROUP_NAME)

        groups = []
        for group_name in sorted(group_names):
            group, _ = Group.objects.get_or_create(name=group_name)
            groups.append(group)

        user.groups.set(groups)

    @property
    def selected_roles(self) -> Sequence[UserRole]:
        return self._selected_roles


__all__ = ["AdminUserCreationForm", "BoardSignatureForm"]
