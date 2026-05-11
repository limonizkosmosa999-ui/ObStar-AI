from django.conf import settings
from django.db import models


class Project(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='projects', null=True, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def meeting_count(self):
        return self.meetings.count()

    @property
    def completed_count(self):
        return self.meetings.filter(status='completed').count()


class Meeting(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meetings', null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='meetings')
    title = models.CharField(max_length=255)
    audio_file = models.FileField(upload_to='meetings/%Y/%m/%d/', blank=True, null=True)
    meeting_url = models.URLField(blank=True, default='')
    recall_bot_id = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def has_summary(self):
        return hasattr(self, 'summary') and self.summary is not None

    @property
    def has_transcript(self):
        return hasattr(self, 'transcript') and self.transcript is not None

    @property
    def short_summary(self):
        """Return first topic as a short summary preview."""
        if self.has_summary and self.summary.topics:
            lines = self.summary.topics.strip().split('\n')
            if lines:
                return lines[0][:120]
        return 'No summary yet'


class Transcript(models.Model):
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name='transcript')
    text = models.TextField()
    timestamps = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Transcript for {self.meeting.title}'


class Summary(models.Model):
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name='summary')
    topics = models.TextField(blank=True, default='')
    decisions = models.TextField(blank=True, default='')
    action_items = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Summaries'

    def __str__(self):
        return f'Summary for {self.meeting.title}'
