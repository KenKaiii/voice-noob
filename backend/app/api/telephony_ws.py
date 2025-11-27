"""Telephony WebSocket endpoints for Twilio and Telnyx media streaming.

These WebSocket endpoints handle the audio streams from Twilio and Telnyx,
connecting them to our AI voice agent pipeline.
"""

import asyncio
import base64
import json
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_user_id_from_uuid
from app.db.session import get_db
from app.models.agent import Agent
from app.services.gpt_realtime import GPTRealtimeSession

router = APIRouter(prefix="/ws/telephony", tags=["telephony-ws"])
logger = structlog.get_logger()


@router.websocket("/twilio/{agent_id}")
async def twilio_media_stream(
    websocket: WebSocket,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """WebSocket endpoint for Twilio Media Streams.

    Twilio sends audio via Media Streams in mulaw format at 8kHz.
    This endpoint bridges that audio to our GPT Realtime session.

    Message format from Twilio:
    - {"event": "connected", "protocol": "Call", "version": "1.0.0"}
    - {"event": "start", "start": {"streamSid": "...", "callSid": "..."}}
    - {"event": "media", "media": {"payload": "base64_audio"}}
    - {"event": "stop"}
    """
    session_id = str(uuid.uuid4())
    log = logger.bind(
        endpoint="twilio_media_stream",
        agent_id=agent_id,
        session_id=session_id,
    )

    await websocket.accept()
    log.info("twilio_websocket_connected")

    stream_sid: str = ""
    call_sid: str = ""

    try:
        # Load agent configuration
        result = await db.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id)))
        agent = result.scalar_one_or_none()

        if not agent:
            log.error("agent_not_found")
            await websocket.close(code=4004, reason="Agent not found")
            return

        if not agent.is_active:
            log.error("agent_not_active")
            await websocket.close(code=4003, reason="Agent is not active")
            return

        log.info("agent_loaded", agent_name=agent.name)

        # Look up user ID
        user_id_int = await get_user_id_from_uuid(agent.user_id, db)
        if user_id_int is None:
            log.error("agent_owner_not_found")
            await websocket.close(code=4004, reason="Agent owner not found")
            return

        # Build agent config
        agent_config = {
            "system_prompt": agent.system_prompt,
            "enabled_tools": agent.enabled_tools,
            "language": agent.language,
            "voice": agent.voice or "shimmer",
        }

        # Initialize GPT Realtime session
        async with GPTRealtimeSession(
            db=db,
            user_id=user_id_int,
            agent_config=agent_config,
            session_id=session_id,
        ) as realtime_session:
            # Handle Twilio media stream
            await _handle_twilio_stream(
                websocket=websocket,
                realtime_session=realtime_session,
                log=log,
            )

    except WebSocketDisconnect:
        log.info("twilio_websocket_disconnected")
    except Exception as e:
        log.exception("twilio_websocket_error", error=str(e))
    finally:
        log.info("twilio_websocket_closed", stream_sid=stream_sid, call_sid=call_sid)


async def _handle_twilio_stream(  # noqa: PLR0915
    websocket: WebSocket,
    realtime_session: GPTRealtimeSession,
    log: Any,
) -> None:
    """Handle Twilio Media Stream messages.

    Args:
        websocket: WebSocket connection from Twilio
        realtime_session: GPT Realtime session
        log: Logger instance
    """
    stream_sid = ""
    call_sid = ""

    async def twilio_to_realtime() -> None:
        """Forward audio from Twilio to GPT Realtime."""
        nonlocal stream_sid, call_sid

        try:
            while True:
                message = await websocket.receive_text()
                data = json.loads(message)
                event = data.get("event", "")

                if event == "connected":
                    log.info("twilio_stream_connected")

                elif event == "start":
                    start_data = data.get("start", {})
                    stream_sid = start_data.get("streamSid", "")
                    call_sid = start_data.get("callSid", "")
                    log.info(
                        "twilio_stream_started",
                        stream_sid=stream_sid,
                        call_sid=call_sid,
                    )

                elif event == "media":
                    # Decode base64 mulaw audio and forward to Realtime
                    media = data.get("media", {})
                    payload = media.get("payload", "")
                    if payload:
                        audio_bytes = base64.b64decode(payload)
                        await realtime_session.send_audio(audio_bytes)

                elif event == "stop":
                    log.info("twilio_stream_stopped")
                    break

                elif event == "mark":
                    # Mark events indicate playback position
                    log.debug("twilio_mark_event", name=data.get("mark", {}).get("name"))

        except WebSocketDisconnect:
            log.info("twilio_to_realtime_disconnected")
        except Exception as e:
            log.exception("twilio_to_realtime_error", error=str(e))

    async def realtime_to_twilio() -> None:
        """Forward audio from GPT Realtime to Twilio."""
        try:
            if not realtime_session.connection:
                log.error("no_realtime_connection")
                return

            async for event in realtime_session.connection:
                event_type = event.type

                # Handle audio output
                if event_type == "response.audio.delta":
                    # Get audio delta and send to Twilio
                    if hasattr(event, "delta") and event.delta:
                        audio_bytes = base64.b64decode(event.delta)
                        # Encode for Twilio
                        payload = base64.b64encode(audio_bytes).decode("utf-8")
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": payload},
                                }
                            )
                        )

                # Handle tool calls
                elif event_type == "response.function_call_arguments.done":
                    log.info(
                        "handling_function_call",
                        call_id=event.call_id,
                        name=event.name,
                    )
                    await realtime_session.handle_function_call_event(event)

                # Log other events
                elif event_type in [
                    "response.audio.done",
                    "response.done",
                    "input_audio_buffer.speech_started",
                    "input_audio_buffer.speech_stopped",
                ]:
                    log.debug("realtime_event", event_type=event_type)

        except Exception as e:
            log.exception("realtime_to_twilio_error", error=str(e))

    # Run both directions concurrently
    await asyncio.gather(
        twilio_to_realtime(),
        realtime_to_twilio(),
        return_exceptions=True,
    )


@router.websocket("/telnyx/{agent_id}")
async def telnyx_media_stream(
    websocket: WebSocket,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """WebSocket endpoint for Telnyx Media Streams.

    Telnyx sends audio via Media Streams in PCMU format at 8kHz.
    This endpoint bridges that audio to our GPT Realtime session.

    Message format from Telnyx:
    - {"event": "start", "stream_id": "...", "call_control_id": "..."}
    - {"event": "media", "media": {"payload": "base64_audio"}}
    - {"event": "stop"}
    """
    session_id = str(uuid.uuid4())
    log = logger.bind(
        endpoint="telnyx_media_stream",
        agent_id=agent_id,
        session_id=session_id,
    )

    await websocket.accept()
    log.info("telnyx_websocket_connected")

    stream_id: str = ""
    call_control_id: str = ""

    try:
        # Load agent configuration
        result = await db.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id)))
        agent = result.scalar_one_or_none()

        if not agent:
            log.error("agent_not_found")
            await websocket.close(code=4004, reason="Agent not found")
            return

        if not agent.is_active:
            log.error("agent_not_active")
            await websocket.close(code=4003, reason="Agent is not active")
            return

        log.info("agent_loaded", agent_name=agent.name)

        # Look up user ID
        user_id_int = await get_user_id_from_uuid(agent.user_id, db)
        if user_id_int is None:
            log.error("agent_owner_not_found")
            await websocket.close(code=4004, reason="Agent owner not found")
            return

        # Build agent config
        agent_config = {
            "system_prompt": agent.system_prompt,
            "enabled_tools": agent.enabled_tools,
            "language": agent.language,
            "voice": agent.voice or "shimmer",
        }

        # Initialize GPT Realtime session
        async with GPTRealtimeSession(
            db=db,
            user_id=user_id_int,
            agent_config=agent_config,
            session_id=session_id,
        ) as realtime_session:
            # Handle Telnyx media stream
            await _handle_telnyx_stream(
                websocket=websocket,
                realtime_session=realtime_session,
                log=log,
            )

    except WebSocketDisconnect:
        log.info("telnyx_websocket_disconnected")
    except Exception as e:
        log.exception("telnyx_websocket_error", error=str(e))
    finally:
        log.info("telnyx_websocket_closed", stream_id=stream_id, call_control_id=call_control_id)


async def _handle_telnyx_stream(
    websocket: WebSocket,
    realtime_session: GPTRealtimeSession,
    log: Any,
) -> None:
    """Handle Telnyx Media Stream messages.

    Args:
        websocket: WebSocket connection from Telnyx
        realtime_session: GPT Realtime session
        log: Logger instance
    """
    stream_id = ""
    call_control_id = ""

    async def telnyx_to_realtime() -> None:
        """Forward audio from Telnyx to GPT Realtime."""
        nonlocal stream_id, call_control_id

        try:
            while True:
                message = await websocket.receive_text()
                data = json.loads(message)
                event = data.get("event", "")

                if event == "start":
                    stream_id = data.get("stream_id", "")
                    start_data = data.get("start", {})
                    call_control_id = start_data.get("call_control_id", "")
                    log.info(
                        "telnyx_stream_started",
                        stream_id=stream_id,
                        call_control_id=call_control_id,
                    )

                elif event == "media":
                    # Decode base64 PCMU audio and forward to Realtime
                    media = data.get("media", {})
                    payload = media.get("payload", "")
                    if payload:
                        audio_bytes = base64.b64decode(payload)
                        await realtime_session.send_audio(audio_bytes)

                elif event == "stop":
                    log.info("telnyx_stream_stopped")
                    break

        except WebSocketDisconnect:
            log.info("telnyx_to_realtime_disconnected")
        except Exception as e:
            log.exception("telnyx_to_realtime_error", error=str(e))

    async def realtime_to_telnyx() -> None:
        """Forward audio from GPT Realtime to Telnyx."""
        try:
            if not realtime_session.connection:
                log.error("no_realtime_connection")
                return

            async for event in realtime_session.connection:
                event_type = event.type

                # Handle audio output
                if event_type == "response.audio.delta":
                    if hasattr(event, "delta") and event.delta:
                        audio_bytes = base64.b64decode(event.delta)
                        payload = base64.b64encode(audio_bytes).decode("utf-8")
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "event": "media",
                                    "stream_id": stream_id,
                                    "media": {"payload": payload},
                                }
                            )
                        )

                # Handle tool calls
                elif event_type == "response.function_call_arguments.done":
                    log.info(
                        "handling_function_call",
                        call_id=event.call_id,
                        name=event.name,
                    )
                    await realtime_session.handle_function_call_event(event)

                elif event_type in [
                    "response.audio.done",
                    "response.done",
                    "input_audio_buffer.speech_started",
                    "input_audio_buffer.speech_stopped",
                ]:
                    log.debug("realtime_event", event_type=event_type)

        except Exception as e:
            log.exception("realtime_to_telnyx_error", error=str(e))

    # Run both directions concurrently
    await asyncio.gather(
        telnyx_to_realtime(),
        realtime_to_telnyx(),
        return_exceptions=True,
    )
