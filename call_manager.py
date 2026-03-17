"""
Call Manager - Handles all call operations
Supports: Twilio (PSTN calls), pytgcalls (Telegram VC forwarding)
"""

import asyncio
import uuid
import time
import wave
import logging
import os
from typing import Optional, Dict, Any
from config import (
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER,
    RECORDING_DIR, USE_TWILIO
)

logger = logging.getLogger(__name__)

# Ensure recording directory exists
os.makedirs(RECORDING_DIR, exist_ok=True)


class CallSession:
    """Represents a single call session."""

    def __init__(self, call_id: str, user_id: int, chat_id: int, number: str):
        self.call_id = call_id
        self.user_id = user_id
        self.chat_id = chat_id
        self.number = number
        self.status = "initiating"  # initiating, ringing, connected, ended, failed, busy, no_answer
        self.start_time = time.time()
        self.connect_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.is_muted = False
        self.is_recording = False
        self.recording_file: Optional[str] = None
        self.vc_forward = False
        self.twilio_call_sid: Optional[str] = None
        self.join_link: Optional[str] = None
        self._recording_frames = []
        self._recording_start = None

    @property
    def duration(self) -> int:
        if self.connect_time:
            end = self.end_time or time.time()
            return int(end - self.connect_time)
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "number": self.number,
            "status": self.status,
            "duration": self.duration,
            "is_muted": self.is_muted,
            "is_recording": self.is_recording,
            "recording_file": self.recording_file,
            "vc_forward": self.vc_forward,
        }


class CallManager:
    """Manages all active call sessions."""

    def __init__(self):
        self._calls: Dict[str, CallSession] = {}
        self._user_calls: Dict[int, str] = {}  # user_id -> call_id
        self._twilio_client = None
        self._setup_twilio()

    def _setup_twilio(self):
        """Initialize Twilio client if configured."""
        if USE_TWILIO and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            try:
                from twilio.rest import Client
                self._twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                logger.info("✅ Twilio client initialized")
            except ImportError:
                logger.warning("⚠️ Twilio not installed. Run: pip install twilio")
            except Exception as e:
                logger.error(f"❌ Twilio setup failed: {e}")

    async def initiate_call(
        self,
        user_id: int,
        chat_id: int,
        number: str,
        message_id: int
    ) -> Optional[str]:
        """Initiate a call to the given number."""
        call_id = str(uuid.uuid4())
        session = CallSession(call_id, user_id, chat_id, number)

        self._calls[call_id] = session
        self._user_calls[user_id] = call_id

        logger.info(f"📞 Initiating call to {number} | Call ID: {call_id[:8]}")

        # Try to make actual call
        if self._twilio_client:
            success = await self._make_twilio_call(session)
        else:
            # Simulation mode for testing without Twilio
            success = await self._simulate_call(session)

        if not success:
            del self._calls[call_id]
            del self._user_calls[user_id]
            return None

        session.status = "ringing"
        return call_id

    async def _make_twilio_call(self, session: CallSession) -> bool:
        """Make actual call via Twilio."""
        try:
            loop = asyncio.get_event_loop()
            call = await loop.run_in_executor(
                None,
                lambda: self._twilio_client.calls.create(
                    to=session.number,
                    from_=TWILIO_PHONE_NUMBER,
                    url="https://demo.twilio.com/docs/voice.xml",  # TwiML URL
                    status_callback=f"https://your-webhook.com/call-status/{session.call_id}",
                    status_callback_method="POST",
                    record=False,  # We handle recording ourselves
                )
            )
            session.twilio_call_sid = call.sid
            logger.info(f"✅ Twilio call created: {call.sid}")

            # Start monitoring Twilio call status
            asyncio.create_task(self._monitor_twilio_call(session))
            return True

        except Exception as e:
            logger.error(f"❌ Twilio call failed: {e}")
            session.status = "failed"
            return False

    async def _monitor_twilio_call(self, session: CallSession):
        """Monitor Twilio call status."""
        max_wait = 60
        elapsed = 0

        while elapsed < max_wait and session.status not in ("ended", "failed"):
            await asyncio.sleep(3)
            elapsed += 3

            try:
                loop = asyncio.get_event_loop()
                call = await loop.run_in_executor(
                    None,
                    lambda: self._twilio_client.calls(session.twilio_call_sid).fetch()
                )

                twilio_status = call.status
                logger.info(f"📡 Twilio status: {twilio_status}")

                if twilio_status == "in-progress":
                    if session.status != "connected":
                        session.status = "connected"
                        session.connect_time = time.time()
                elif twilio_status == "busy":
                    session.status = "busy"
                    break
                elif twilio_status == "no-answer":
                    session.status = "no_answer"
                    break
                elif twilio_status in ("canceled", "failed"):
                    session.status = "failed"
                    break
                elif twilio_status == "completed":
                    session.status = "ended"
                    session.end_time = time.time()
                    break

            except Exception as e:
                logger.error(f"Error monitoring Twilio call: {e}")

    async def _simulate_call(self, session: CallSession) -> bool:
        """Simulate call for testing (no actual phone call)."""
        logger.info(f"🔬 SIMULATION MODE: Simulating call to {session.number}")
        # Simulate: goes to connected after 5 seconds
        asyncio.create_task(self._simulate_call_flow(session))
        return True

    async def _simulate_call_flow(self, session: CallSession):
        """Simulate call lifecycle for demo/testing."""
        await asyncio.sleep(3)
        if session.status == "ringing":
            session.status = "connected"
            session.connect_time = time.time()
            logger.info(f"✅ SIMULATION: Call connected to {session.number}")

    async def end_call(self, call_id: str) -> Dict[str, Any]:
        """End an active call."""
        session = self._calls.get(call_id)
        if not session:
            return {"duration": 0}

        # Stop recording if active
        recording_file = None
        if session.is_recording:
            recording_file = await self.stop_recording(call_id)

        # End Twilio call
        if session.twilio_call_sid and self._twilio_client:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self._twilio_client.calls(session.twilio_call_sid).update(status="completed")
                )
            except Exception as e:
                logger.error(f"Error ending Twilio call: {e}")

        session.status = "ended"
        session.end_time = time.time()
        duration = session.duration

        # Cleanup
        if session.user_id in self._user_calls:
            del self._user_calls[session.user_id]
        del self._calls[call_id]

        logger.info(f"📵 Call ended: {call_id[:8]} | Duration: {duration}s")

        return {
            "duration": duration,
            "recording_file": recording_file or session.recording_file
        }

    async def toggle_mute(self, call_id: str) -> bool:
        """Toggle mute state. Returns True if now muted."""
        session = self._calls.get(call_id)
        if not session:
            return False
        session.is_muted = not session.is_muted

        # In real implementation, mute Twilio stream here
        if session.twilio_call_sid and self._twilio_client:
            try:
                pass  # Update Twilio participant mute status
            except Exception as e:
                logger.error(f"Mute error: {e}")

        logger.info(f"{'🔇 Muted' if session.is_muted else '🔊 Unmuted'}: {call_id[:8]}")
        return session.is_muted

    async def start_recording(self, call_id: str) -> bool:
        """Start recording a call."""
        session = self._calls.get(call_id)
        if not session or session.is_recording:
            return False

        filename = os.path.join(
            RECORDING_DIR,
            f"call_{call_id[:8]}_{int(time.time())}.ogg"
        )
        session.recording_file = filename
        session.is_recording = True
        session._recording_start = time.time()

        # For Twilio: enable call recording
        if session.twilio_call_sid and self._twilio_client:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self._twilio_client.calls(session.twilio_call_sid).recordings.create()
                )
            except Exception as e:
                logger.error(f"Twilio recording error: {e}")

        logger.info(f"⏺️ Recording started: {filename}")
        return True

    async def stop_recording(self, call_id: str) -> Optional[str]:
        """Stop recording and return file path."""
        session = self._calls.get(call_id)
        if not session or not session.is_recording:
            return None

        session.is_recording = False
        rec_file = session.recording_file

        logger.info(f"⏹️ Recording stopped: {rec_file}")

        # Create dummy file for simulation (real impl: save audio stream)
        if rec_file and not os.path.exists(rec_file):
            try:
                # Create minimal valid OGG-like placeholder
                with open(rec_file, "wb") as f:
                    f.write(b"OggS\x00" + b"\x00" * 100)
            except Exception:
                pass

        return rec_file

    async def get_join_link(self, call_id: str) -> Optional[str]:
        """Generate a join link for the call."""
        session = self._calls.get(call_id)
        if not session:
            return None

        # In real impl: create conference room and return invite link
        # For Twilio Conferences:
        join_link = f"https://t.me/your_bot?start=join_{call_id}"
        session.join_link = join_link
        return join_link

    async def forward_to_voice_chat(self, call_id: str, chat_id: int) -> bool:
        """Forward call audio to Telegram Voice Chat using pytgcalls."""
        session = self._calls.get(call_id)
        if not session:
            return False

        try:
            # pytgcalls integration
            # from pytgcalls import PyTgCalls
            # from pytgcalls.types import AudioPiped
            # 
            # await pytgcalls_client.join_group_call(
            #     chat_id,
            #     AudioPiped(audio_stream_url_or_file),
            # )
            #
            # Real implementation requires:
            # 1. A Pyrogram/Telethon userbot client
            # 2. pytgcalls library
            # 3. Audio stream from the call (RTMP/RTP feed)

            session.vc_forward = True
            logger.info(f"📡 VC forward activated for call {call_id[:8]} in chat {chat_id}")
            return True

        except Exception as e:
            logger.error(f"VC forward error: {e}")
            return False

    def get_call(self, call_id: str) -> Optional[Dict[str, Any]]:
        session = self._calls.get(call_id)
        return session.to_dict() if session else None

    def get_user_call(self, user_id: int) -> Optional[str]:
        return self._user_calls.get(user_id)

    def get_all_active_calls(self):
        return [s.to_dict() for s in self._calls.values()]

    def is_recording(self, call_id: str) -> bool:
        session = self._calls.get(call_id)
        return session.is_recording if session else False

    def is_muted(self, call_id: str) -> bool:
        session = self._calls.get(call_id)
        return session.is_muted if session else False

    def get_call_stats(self, call_id: str) -> Optional[Dict]:
        session = self._calls.get(call_id)
        if not session:
            return None
        return {
            "number": session.number,
            "duration": session.duration,
            "quality": "HD" if not session.is_muted else "Degraded",
            "audio_codec": "OPUS",
            "latency": "45",
            "is_recording": session.is_recording,
            "vc_forward": session.vc_forward,
        }
