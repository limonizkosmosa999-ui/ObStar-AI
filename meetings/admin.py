from django.contrib import admin
from .models import Project, Meeting, Transcript, Summary


class MeetingInline(admin.TabularInline):
    model = Meeting
    extra = 0
    fields = ['title', 'status', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'meeting_count', 'created_at']
    search_fields = ['name']
    inlines = [MeetingInline]


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ['title', 'project', 'status', 'created_at']
    list_filter = ['status', 'project']
    search_fields = ['title']


@admin.register(Transcript)
class TranscriptAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'created_at']


@admin.register(Summary)
class SummaryAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'created_at']
