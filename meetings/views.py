
import os
import json
import logging
import requests

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q, Count
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.csrf import csrf_exempt

from .models import Project, Meeting, Transcript, Summary
from .forms import ProjectForm, MeetingUploadForm, RegistrationForm
from .tasks import start_meeting_processing

logger = logging.getLogger(__name__)


# ==================== Auth Views ====================

def register_view(request):
    """User registration."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.username}! Your account is ready.')
            return redirect('dashboard')
    else:
        form = RegistrationForm()

    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    """User login."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Redirect to 'next' param or dashboard
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
    else:
        form = AuthenticationForm()

    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    """User logout."""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


# ==================== Dashboard & Projects ====================

@login_required
def dashboard(request):
    """Main dashboard — list all projects and recent meetings."""
    projects = Project.objects.filter(user=request.user).annotate(
        total_meetings=Count('meetings'),
    ).all()

    recent_meetings = Meeting.objects.filter(user=request.user).select_related('project', 'summary').all()[:10]

    total_projects = projects.count()
    total_meetings = Meeting.objects.filter(user=request.user).count()
    completed_meetings = Meeting.objects.filter(user=request.user, status='completed').count()

    context = {
        'projects': projects,
        'recent_meetings': recent_meetings,
        'total_projects': total_projects,
        'total_meetings': total_meetings,
        'completed_meetings': completed_meetings,
    }
    return render(request, 'meetings/dashboard.html', context)


@login_required
def create_project(request):
    """Create a new project."""
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.user = request.user
            project.save()
            messages.success(request, f'Project "{project.name}" created successfully!')
            return redirect('dashboard')
    else:
        form = ProjectForm()

    return render(request, 'meetings/create_project.html', {'form': form})


@login_required
def project_detail(request, project_id):
    """Show project details with its meetings."""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    meetings = project.meetings.select_related('summary').all()

    context = {
        'project': project,
        'meetings': meetings,
    }
    return render(request, 'meetings/project_detail.html', context)


@login_required
def upload_meeting(request):
    """Upload a new meeting recording."""
    if request.method == 'POST':
        form = MeetingUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.user = request.user
            meeting.status = 'pending'
            meeting.save()

            # Start background processing
            start_meeting_processing(meeting.id)

            messages.success(request, f'Meeting "{meeting.title}" uploaded! AI processing has started.')
            return redirect('meeting_detail', meeting_id=meeting.id)
    else:
        form = MeetingUploadForm(user=request.user)
        # Pre-select project if provided in query params
        project_id = request.GET.get('project')
        if project_id:
            form.fields['project'].initial = project_id

    return render(request, 'meetings/upload.html', {'form': form})


@login_required
def meeting_detail(request, meeting_id):
    """Show meeting details with transcript and summary."""
    meeting = get_object_or_404(
        Meeting.objects.select_related('project', 'transcript', 'summary'),
        id=meeting_id,
        user=request.user,
    )

    # Parse summary items into lists for template
    topics = []
    decisions = []
    action_items = []

    if meeting.has_summary:
        topics = [line.strip().lstrip('- ') for line in (meeting.summary.topics or '').split('\n') if line.strip()]
        decisions = [line.strip().lstrip('- ') for line in meeting.summary.decisions.split('\n') if line.strip()]
        action_items = [line.strip().lstrip('- ') for line in meeting.summary.action_items.split('\n') if line.strip()]

    # Parse timestamps for transcript
    timestamps = []
    if meeting.has_transcript and meeting.transcript.timestamps:
        timestamps = meeting.transcript.timestamps

    context = {
        'meeting': meeting,
        'topics': topics,
        'decisions': decisions,
        'action_items': action_items,
        'timestamps': timestamps,
    }
    return render(request, 'meetings/meeting_detail.html', context)


@login_required
def meeting_status_api(request, meeting_id):
    """JSON API endpoint for polling meeting processing status."""
    meeting = get_object_or_404(Meeting, id=meeting_id, user=request.user)
    data = {
        'id': meeting.id,
        'status': meeting.status,
        'error_message': meeting.error_message,
    }
    return JsonResponse(data)


@login_required
def search(request):
    """Search across transcripts and summaries."""
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        results = Meeting.objects.filter(user=request.user).select_related('project', 'summary', 'transcript').filter(
            Q(title__icontains=query) |
            Q(transcript__text__icontains=query) |
            Q(summary__topics__icontains=query) |
            Q(summary__decisions__icontains=query) |
            Q(summary__action_items__icontains=query)
        ).distinct()

    context = {
        'query': query,
        'results': results,
        'result_count': len(results) if results else 0,
    }
    return render(request, 'meetings/search.html', context)


@login_required
def delete_project(request, project_id):
    """Delete a project and its meetings."""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    if request.method == 'POST':
        name = project.name
        project.delete()
        messages.success(request, f'Project "{name}" deleted.')
        return redirect('dashboard')
    return redirect('project_detail', project_id=project_id)


@login_required
def delete_meeting(request, meeting_id):
    """Delete a meeting."""
    meeting = get_object_or_404(Meeting, id=meeting_id, user=request.user)
    if request.method == 'POST':
        project_id = meeting.project.id
        title = meeting.title
        meeting.delete()
        messages.success(request, f'Meeting "{title}" deleted.')
        return redirect('project_detail', project_id=project_id)
    return redirect('meeting_detail', meeting_id=meeting_id)


@login_required
def reprocess_meeting(request, meeting_id):
    """Re-process a failed or completed meeting."""
    meeting = get_object_or_404(Meeting, id=meeting_id, user=request.user)
    if request.method == 'POST':
        meeting.status = 'pending'
        meeting.error_message = ''
        meeting.save()
        # Delete old transcript and summary
        Transcript.objects.filter(meeting=meeting).delete()
        Summary.objects.filter(meeting=meeting).delete()
        # Restart processing
        start_meeting_processing(meeting.id)
        messages.success(request, f'Re-processing "{meeting.title}"...')
    return redirect('meeting_detail', meeting_id=meeting_id)


# ==================== Recall.ai Bot ====================

@login_required
def add_bot_to_meeting(request):
    """Send a Recall.ai bot to a Zoom/Google Meet call."""
    if request.method != 'POST':
        return redirect('dashboard')

    meeting_url = request.POST.get('meeting_url', '').strip()
    title = request.POST.get('title', '').strip() or 'Untitled Meeting'
    project_id = request.POST.get('project_id')

    if not meeting_url or not project_id:
        messages.error(request, 'Please provide a meeting link and select a project.')
        return redirect('project_detail', project_id=project_id) if project_id else redirect('dashboard')

    project = get_object_or_404(Project, id=project_id, user=request.user)

    # Send bot via Recall.ai API
    recall_api_key = os.environ.get('RECALL_API_KEY', '')
    recall_bot_id = ''

    if recall_api_key:
        try:
            resp = requests.post(
                'https://us-east-1.recall.ai/api/v1/bot/',
                headers={
                    'Authorization': f'Token {recall_api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'meeting_url': meeting_url,
                    'bot_name': 'ObStar AI',
                    'transcription_options': {'provider': 'assembly_ai'},
                },
                timeout=30,
            )
            resp.raise_for_status()
            recall_bot_id = resp.json().get('id', '')
            logger.info(f'Recall.ai bot created: {recall_bot_id}')
        except Exception as e:
            logger.error(f'Recall.ai API error: {e}')
            messages.error(request, f'Failed to send bot: {e}')
            return redirect('project_detail', project_id=project.id)
    else:
        logger.warning('RECALL_API_KEY not set — bot not sent')
        messages.warning(request, 'Recall.ai API key not configured. Bot was not sent.')

    # Save meeting record
    meeting = Meeting.objects.create(
        user=request.user,
        project=project,
        title=title,
        meeting_url=meeting_url,
        recall_bot_id=recall_bot_id,
        status='processing',
    )

    messages.success(request, f'Bot sent to meeting "{title}". Waiting for it to finish...')
    return redirect('project_detail', project_id=project.id)


@csrf_exempt
def recall_webhook(request):
    """Webhook endpoint for Recall.ai — called when bot finishes recording."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    event = payload.get('event', '')
    logger.info(f'Recall webhook received: event={event}')

    if event != 'bot.done':
        # Acknowledge non-done events
        return JsonResponse({'status': 'ignored'})

    data = payload.get('data', {})
    bot_id = data.get('bot_id', '') or data.get('id', '')

    if not bot_id:
        return JsonResponse({'error': 'No bot_id'}, status=400)

    try:
        meeting = Meeting.objects.get(recall_bot_id=bot_id)
    except Meeting.DoesNotExist:
        logger.error(f'Meeting not found for bot_id: {bot_id}')
        return JsonResponse({'error': 'Meeting not found'}, status=404)

    # Extract transcript from webhook data
    transcript_data = data.get('transcript', [])
    if isinstance(transcript_data, list):
        transcript_text = '\n'.join(
            item.get('text', '') if isinstance(item, dict) else str(item)
            for item in transcript_data
        )
    elif isinstance(transcript_data, str):
        transcript_text = transcript_data
    else:
        transcript_text = str(transcript_data)

    if not transcript_text.strip():
        meeting.status = 'failed'
        meeting.error_message = 'Empty transcript received from Recall.ai'
        meeting.save()
        return JsonResponse({'status': 'error', 'detail': 'empty transcript'})

    # Save transcript
    from .ai_service import generate_summary

    Transcript.objects.update_or_create(
        meeting=meeting,
        defaults={
            'text': transcript_text,
            'timestamps': [],
        }
    )

    # Generate summary
    try:
        summary_data = generate_summary(transcript_text)
        Summary.objects.update_or_create(
            meeting=meeting,
            defaults={
                'topics': summary_data.get('topics', ''),
                'decisions': summary_data.get('decisions', ''),
                'action_items': summary_data.get('action_items', ''),
            }
        )
        meeting.status = 'completed'
        meeting.error_message = ''
    except Exception as e:
        logger.error(f'Summary generation failed for meeting {meeting.id}: {e}')
        meeting.status = 'completed'  # Transcript saved, summary failed
        meeting.error_message = f'Summary generation failed: {e}'

    meeting.save()
    logger.info(f'Recall webhook processed successfully for meeting {meeting.id}')
    return JsonResponse({'status': 'ok'})


# ==================== Q&A Chat ====================

@login_required
def project_chat(request, project_id):
    """Q&A chat about all meetings in a project using OpenAI."""
    project = get_object_or_404(Project, id=project_id, user=request.user)

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        question = body.get('question', '').strip()
        if not question:
            return JsonResponse({'error': 'Empty question'}, status=400)

        # Build context from all completed meetings
        meetings = Meeting.objects.filter(
            project=project, status='completed', user=request.user
        ).select_related('transcript')

        context_parts = []
        for m in meetings:
            if m.has_transcript:
                context_parts.append(
                    f"Встреча '{m.title}' от {m.created_at.date()}:\n{m.transcript.text}"
                )

        if not context_parts:
            return JsonResponse({'answer': 'В этом проекте пока нет обработанных встреч для ответа на вопрос.'})

        context = '\n\n---\n\n'.join(context_parts)

        # Call Groq AI
        groq_api_key = os.environ.get('OPENAI_API_KEY', '')
        if not groq_api_key:
            return JsonResponse({'answer': 'Groq API key not configured. Set OPENAI_API_KEY environment variable.'})

        try:
            import openai
            client = openai.OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
            response = client.chat.completions.create(
                model='llama-3.1-8b-instant',
                messages=[
                    {
                        'role': 'system',
                        'content': f'Ты помощник. Отвечай только на основе этих встреч:\n\n{context}',
                    },
                    {
                        'role': 'user',
                        'content': question,
                    },
                ],
            )
            answer = response.choices[0].message.content
        except Exception as e:
            logger.error(f'Groq API error: {e}')
            answer = f'Ошибка при обращении к AI: {str(e)}'

        return JsonResponse({'answer': answer})

    # GET — render chat page
    return render(request, 'meetings/project_detail.html', {
        'project': project,
        'meetings': project.meetings.select_related('summary').all(),
        'show_chat': True,
    })

