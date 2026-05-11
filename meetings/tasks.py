"""
Background task runner using Python threading.
Processes meetings asynchronously without blocking the request.
"""
import logging
import threading
import traceback

from .models import Meeting, Transcript, Summary
from .ai_service import transcribe_audio, generate_summary

logger = logging.getLogger(__name__)


def process_meeting_task(meeting_id):
    """
    Process a meeting: transcribe audio and generate summary.
    Runs in a background thread.
    """
    try:
        meeting = Meeting.objects.get(id=meeting_id)
        meeting.status = 'processing'
        meeting.save()

        logger.info(f"Processing meeting: {meeting.title} (ID: {meeting_id})")

        # Step 1: Transcribe audio
        if meeting.audio_file:
            transcript_data = transcribe_audio(meeting.audio_file.path)
        else:
            raise Exception("No audio file attached to this meeting.")

        # Save transcript
        Transcript.objects.update_or_create(
            meeting=meeting,
            defaults={
                'text': transcript_data['text'],
                'timestamps': transcript_data.get('timestamps', []),
            }
        )
        logger.info(f"Transcript saved for meeting {meeting_id}")

        # Step 2: Generate summary
        summary_data = generate_summary(transcript_data['text'])

        # Save summary
        Summary.objects.update_or_create(
            meeting=meeting,
            defaults={
                'topics': summary_data.get('topics', ''),
                'decisions': summary_data.get('decisions', ''),
                'action_items': summary_data.get('action_items', ''),
            }
        )
        logger.info(f"Summary saved for meeting {meeting_id}")

        # Mark as completed
        meeting.status = 'completed'
        meeting.error_message = ''
        meeting.save()
        logger.info(f"Meeting {meeting_id} processing completed successfully")

    except Meeting.DoesNotExist:
        logger.error(f"Meeting {meeting_id} not found")
    except Exception as e:
        logger.error(f"Error processing meeting {meeting_id}: {traceback.format_exc()}")
        try:
            meeting = Meeting.objects.get(id=meeting_id)
            meeting.status = 'failed'
            meeting.error_message = str(e)
            meeting.save()
        except Meeting.DoesNotExist:
            pass


def start_meeting_processing(meeting_id):
    """Start processing a meeting in a background thread."""
    thread = threading.Thread(
        target=process_meeting_task,
        args=(meeting_id,),
        daemon=True,
    )
    thread.start()
    logger.info(f"Started background processing for meeting {meeting_id}")
    return thread
