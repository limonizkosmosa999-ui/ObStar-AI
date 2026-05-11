from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Project, Meeting


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'your@email.com',
            'id': 'register-email-input',
            'class': 'form-control',
        }),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={
                'placeholder': 'Username',
                'id': 'register-username-input',
                'class': 'form-control',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'placeholder': 'Password',
            'id': 'register-password1-input',
            'class': 'form-control',
        })
        self.fields['password2'].widget.attrs.update({
            'placeholder': 'Confirm password',
            'id': 'register-password2-input',
            'class': 'form-control',
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Project name',
                'id': 'project-name-input',
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Brief description (optional)',
                'rows': 3,
                'id': 'project-description-input',
            }),
        }


class MeetingUploadForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ['project', 'title', 'audio_file']
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'Meeting title',
                'id': 'meeting-title-input',
            }),
            'project': forms.Select(attrs={
                'id': 'meeting-project-select',
            }),
            'audio_file': forms.ClearableFileInput(attrs={
                'id': 'meeting-file-input',
                'accept': 'audio/*,video/*,.mp3,.mp4,.wav,.m4a,.webm,.ogg,.flac',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['audio_file'].required = True
        self.fields['audio_file'].label = 'Audio / Video File'
        self.fields['project'].empty_label = 'Select a project...'
        if self.user:
            self.fields['project'].queryset = Project.objects.filter(user=self.user)
