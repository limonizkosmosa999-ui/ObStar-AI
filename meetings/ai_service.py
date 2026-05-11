"""
AI Service — integrates with Deepgram APIs for transcription and text analysis.
Uses Deepgram's:
  - Listen API (nova-3 model) for speech-to-text transcription
  - Read API for text summarization, topic detection, and intent detection
Falls back to mock responses when DEEPGRAM_API_KEY is not set.
"""
import os
import logging
import time
import re

logger = logging.getLogger(__name__)

def get_deepgram_client():
    """Get Deepgram client if API key is available."""
    api_key = os.getenv('DEEPGRAM_API_KEY', '')
    if not api_key:
        return None
    try:
        from deepgram import DeepgramClient
        return DeepgramClient(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to create Deepgram client: {e}")
        return None


def transcribe_audio(file_path):
    """
    Transcribe audio/video file using Deepgram Listen API (nova-3).
    Returns dict with 'text' and 'timestamps'.
    """
    client = get_deepgram_client()

    if client:
        try:
            logger.info(f"Transcribing file with Deepgram: {file_path}")

            with open(file_path, 'rb') as audio_file:
                audio_data = audio_file.read()

            response = client.listen.v1.media.transcribe_file(
                request=audio_data,
                model="nova-3",
                smart_format=True,
                punctuate=True,
                paragraphs=True,
                utterances=True,
                language="en",
            )

            # Extract full transcript text
            transcript_text = ''
            timestamps = []

            if hasattr(response, 'results') and response.results:
                channels = response.results.channels
                if channels:
                    alternatives = channels[0].alternatives
                    if alternatives:
                        transcript_text = alternatives[0].transcript or ''

                # Extract word/utterance timestamps
                if hasattr(response.results, 'utterances') and response.results.utterances:
                    for utterance in response.results.utterances:
                        timestamps.append({
                            'start': round(utterance.start, 1),
                            'end': round(utterance.end, 1),
                            'text': utterance.transcript.strip(),
                        })
                elif channels and alternatives:
                    # Fallback: create segments from paragraphs in transcript
                    words = alternatives[0].words if hasattr(alternatives[0], 'words') and alternatives[0].words else []
                    if words:
                        # Group words into ~10-word segments
                        segment_words = []
                        segment_start = 0
                        for i, word in enumerate(words):
                            if not segment_words:
                                segment_start = word.start
                            segment_words.append(word.punctuated_word if hasattr(word, 'punctuated_word') else word.word)

                            if len(segment_words) >= 10 or i == len(words) - 1:
                                timestamps.append({
                                    'start': round(segment_start, 1),
                                    'end': round(word.end, 1),
                                    'text': ' '.join(segment_words),
                                })
                                segment_words = []

            if not transcript_text:
                raise Exception("Deepgram returned empty transcript. Check audio file format.")

            return {
                'text': transcript_text,
                'timestamps': timestamps,
            }

        except Exception as e:
            logger.error(f"Deepgram transcription error: {e}")
            raise Exception(f"Transcription failed: {str(e)}")
    else:
        # Mock response for development
        logger.info("No Deepgram API key — using mock transcription")
        time.sleep(3)
        return _mock_transcription()


def generate_summary(transcript_text):
    """
    Generate structured summary from transcript.
    Uses Deepgram Read API for summarization and topic detection,
    then structures the result into topics, decisions, and action items.
    """
    client = get_deepgram_client()

    if client:
        try:
            logger.info("Analyzing transcript with Deepgram Read API")

            # Use Deepgram's text analysis for summarization and topics
            response = client.read.v1.text.analyze(
                request={"text": transcript_text},
                language="en",
                summarize=True,
                topics=True,
                intents=True,
            )

            # Extract results from Deepgram response
            summary_text = ''
            topics_list = []
            intents_list = []

            if hasattr(response, 'results'):
                results = response.results

                # Get summary
                if hasattr(results, 'summary') and results.summary:
                    summary_text = results.summary.text if hasattr(results.summary, 'text') else str(results.summary)

                # Get topics
                if hasattr(results, 'topics') and results.topics:
                    if hasattr(results.topics, 'segments'):
                        for segment in results.topics.segments:
                            if hasattr(segment, 'topics'):
                                for topic in segment.topics:
                                    topic_text = topic.topic if hasattr(topic, 'topic') else str(topic)
                                    if topic_text and topic_text not in topics_list:
                                        topics_list.append(topic_text)

                # Get intents (can serve as action indicators)
                if hasattr(results, 'intents') and results.intents:
                    if hasattr(results.intents, 'segments'):
                        for segment in results.intents.segments:
                            if hasattr(segment, 'intents'):
                                for intent in segment.intents:
                                    intent_text = intent.intent if hasattr(intent, 'intent') else str(intent)
                                    if intent_text and intent_text not in intents_list:
                                        intents_list.append(intent_text)

            # Structure the output
            # Topics from Deepgram topic detection
            topics_formatted = '\n'.join([f'- {t}' for t in topics_list]) if topics_list else ''

            # For decisions and action items, extract from the transcript using heuristics
            decisions, action_items = extract_decisions_and_actions(transcript_text)

            # If Deepgram didn't return topics, extract from summary
            if not topics_formatted and summary_text:
                # Deepgram summary is a paragraph; convert it to multiple bullets
                # to make the "конспект" (topics) more informative.
                candidates = [s.strip() for s in re.split(r'\n+|(?<=[.!?])\s+', summary_text) if s.strip()]
                if not candidates:
                    candidates = [summary_text.strip()]
                topics_formatted = "\n".join([f"- {c[:220]}" for c in candidates[:12] if c]) or ''

            # If no topics at all, generate from transcript
            if not topics_formatted:
                topics_formatted = extract_topics_from_text(transcript_text)

            return {
                'topics': topics_formatted,
                'decisions': decisions,
                'action_items': action_items,
            }

        except Exception as e:
            logger.error(f"Deepgram analysis error: {e}")
            # Fallback to heuristic extraction if API fails
            logger.info("Falling back to heuristic text analysis")
            return _heuristic_summary(transcript_text)
    else:
        # Mock response for development
        logger.info("No Deepgram API key — using mock summary")
        time.sleep(2)
        return _mock_summary()


def extract_decisions_and_actions(text):
    """
    Extract decisions and action items from transcript text using keyword heuristics.
    This supplements Deepgram's topic/intent detection.
    """
    sentences = re.split(r'[.!?]+', text)
    decisions = []
    action_items = []

    decision_keywords = [
        'decided', 'agreed', 'approved', 'confirmed', 'settled',
        'concluded', 'determined', 'resolved', 'chose', 'selected',
        'will use', 'will adopt', 'going with', 'let\'s go with',
    ]

    action_keywords = [
        'will', 'should', 'need to', 'needs to', 'must',
        'assigned to', 'responsible for', 'take care of',
        'follow up', 'deadline', 'by friday', 'by monday',
        'next week', 'next step', 'action item', 'to do',
        'please', 'make sure', 'don\'t forget',
    ]

    for sentence in sentences:
        s = sentence.strip()
        if not s or len(s) < 10:
            continue

        s_lower = s.lower()

        if any(kw in s_lower for kw in decision_keywords):
            decisions.append(f'- {s.strip()}')

        if any(kw in s_lower for kw in action_keywords):
            action_items.append(f'- {s.strip()}')

    decisions_text = '\n'.join(decisions[:10]) if decisions else '- No explicit decisions detected in transcript'
    actions_text = '\n'.join(action_items[:10]) if action_items else '- No explicit action items detected in transcript'

    return decisions_text, actions_text


def extract_topics_from_text(text):
    """Extract main topics from text by analyzing sentence beginnings and key phrases."""
    sentences = re.split(r'[.!?]+', text)
    topics = set()

    topic_indicators = [
        'discuss', 'talk about', 'regarding', 'about',
        'update on', 'status of', 'progress on', 'report on',
        'moving to', 'next topic', 'let\'s talk', 'agenda',
    ]

    for sentence in sentences:
        s = sentence.strip()
        s_lower = s.lower()
        if any(kw in s_lower for kw in topic_indicators):
            # Clean and add
            topic = s[:180].strip()
            if len(topic) > 10:
                topics.add(topic)

    if topics:
        return '\n'.join([f'- {t}' for t in list(topics)[:12]])

    # Fallback: use first few sentences as topic indicators
    first_sentences = [s.strip() for s in sentences[:7] if len(s.strip()) > 15]
    return '\n'.join([f'- {s[:180]}' for s in first_sentences]) if first_sentences else '- General meeting discussion'


def _heuristic_summary(text):
    """Fallback: generate summary purely from text heuristics when API fails."""
    decisions, action_items = extract_decisions_and_actions(text)
    topics = extract_topics_from_text(text)
    return {
        'topics': topics,
        'decisions': decisions,
        'action_items': action_items,
    }


def _mock_transcription():
    """Mock transcription for development without API key."""
    return {
        'text': (
            "Welcome everyone to today's meeting. Let's start with the project update. "
            "The development team has completed the backend API integration. We're now "
            "moving to the frontend implementation phase. Sarah mentioned that the design "
            "mockups are ready for review. We need to finalize the color scheme by Friday. "
            "John will handle the database migration next week. The client demo is scheduled "
            "for March 15th. We agreed to use the new testing framework for all future sprints. "
            "Budget allocation for Q2 needs to be submitted by end of month. "
            "Let's also discuss the hiring plan — we need two more developers. "
            "The team velocity has improved by 20% this sprint. Good work everyone."
        ),
        'timestamps': [
            {'start': 0.0, 'end': 5.2, 'text': "Welcome everyone to today's meeting."},
            {'start': 5.2, 'end': 10.1, 'text': "Let's start with the project update."},
            {'start': 10.1, 'end': 18.5, 'text': "The development team has completed the backend API integration."},
            {'start': 18.5, 'end': 25.0, 'text': "We're now moving to the frontend implementation phase."},
            {'start': 25.0, 'end': 32.8, 'text': "Sarah mentioned that the design mockups are ready for review."},
            {'start': 32.8, 'end': 38.4, 'text': "We need to finalize the color scheme by Friday."},
            {'start': 38.4, 'end': 45.0, 'text': "John will handle the database migration next week."},
            {'start': 45.0, 'end': 51.2, 'text': "The client demo is scheduled for March 15th."},
            {'start': 51.2, 'end': 60.0, 'text': "We agreed to use the new testing framework for all future sprints."},
            {'start': 60.0, 'end': 68.5, 'text': "Budget allocation for Q2 needs to be submitted by end of month."},
            {'start': 68.5, 'end': 76.0, 'text': "Let's also discuss the hiring plan — we need two more developers."},
            {'start': 76.0, 'end': 82.0, 'text': "The team velocity has improved by 20% this sprint. Good work everyone."},
        ]
    }


def _mock_summary():
    """Mock summary for development without API key."""
    return {
        'topics': (
            "- Project development progress and backend API completion\n"
            "- Frontend implementation phase kickoff\n"
            "- Design mockup review and color scheme finalization\n"
            "- Database migration planning\n"
            "- Client demo preparation\n"
            "- Testing framework adoption\n"
            "- Q2 budget allocation\n"
            "- Hiring plan for development team"
        ),
        'decisions': (
            "- Adopt the new testing framework for all future sprints\n"
            "- Move to frontend implementation phase immediately\n"
            "- Schedule client demo for March 15th\n"
            "- Hire two additional developers"
        ),
        'action_items': (
            "- Sarah — Prepare design mockups for team review — ASAP\n"
            "- Team — Finalize color scheme — by Friday\n"
            "- John — Handle database migration — next week\n"
            "- Team — Prepare for client demo — by March 15th\n"
            "- Management — Submit Q2 budget allocation — end of month\n"
            "- HR/Management — Begin hiring process for 2 developers — ongoing"
        ),
    }
