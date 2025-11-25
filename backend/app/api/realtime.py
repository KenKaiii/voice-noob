"""WebSocket API for GPT Realtime voice calls."""

import asyncio
import json
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.agent import Agent
from app.services.gpt_realtime import GPTRealtimeSession

router = APIRouter(prefix="/ws", tags=["realtime"])
logger = structlog.get_logger()


@router.websocket("/realtime/{agent_id}")
async def realtime_websocket(
    websocket: WebSocket,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """WebSocket endpoint for GPT Realtime voice calls.

    This endpoint:
    1. Accepts WebSocket connection from client (phone/browser)
    2. Loads agent configuration and enabled integrations
    3. Initializes GPT Realtime session with internal tools
    4. Bridges audio between client and GPT Realtime
    5. Routes tool calls to internal tool handlers

    Args:
        websocket: WebSocket connection
        agent_id: Agent UUID
        db: Database session
    """
    session_id = str(uuid.uuid4())
    client_logger = logger.bind(
        endpoint="realtime_websocket",
        agent_id=agent_id,
        session_id=session_id,
    )

    await websocket.accept()
    client_logger.info("websocket_connected")

    try:
        # Load agent configuration
        result = await db.execute(
            select(Agent).where(Agent.id == uuid.UUID(agent_id))
        )
        agent = result.scalar_one_or_none()

        if not agent:
            await websocket.send_json({
                "type": "error",
                "error": f"Agent {agent_id} not found",
            })
            await websocket.close()
            return

        if not agent.is_active:
            await websocket.send_json({
                "type": "error",
                "error": "Agent is not active",
            })
            await websocket.close()
            return

        # Check if Premium tier (GPT Realtime only for Premium)
        if agent.pricing_tier != "premium":
            await websocket.send_json({
                "type": "error",
                "error": "GPT Realtime only available for Premium tier agents",
            })
            await websocket.close()
            return

        client_logger.info(
            "agent_loaded",
            agent_name=agent.name,
            tier=agent.pricing_tier,
            tools_count=len(agent.enabled_tools),
        )

        # Build agent config for GPT Realtime
        agent_config = {
            "system_prompt": agent.system_prompt,
            "enabled_tools": agent.enabled_tools,
            "language": agent.language,
        }

        # Initialize GPT Realtime session with internal tools
        async with GPTRealtimeSession(
            db=db,
            user_id=agent.user_id,
            agent_config=agent_config,
            session_id=session_id,
        ) as realtime_session:

            # Send ready signal to client
            await websocket.send_json({
                "type": "session.ready",
                "session_id": session_id,
                "agent": {
                    "id": str(agent.id),
                    "name": agent.name,
                    "tier": agent.pricing_tier,
                },
            })

            # Start bidirectional streaming
            await _bridge_audio_streams(
                client_ws=websocket,
                realtime_session=realtime_session,
                logger=client_logger,
            )

    except WebSocketDisconnect:
        client_logger.info("websocket_disconnected")
    except Exception as e:
        client_logger.exception("websocket_error", error=str(e))
        try:
            await websocket.send_json({
                "type": "error",
                "error": str(e),
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        client_logger.info("websocket_closed")


async def _bridge_audio_streams(
    client_ws: WebSocket,
    realtime_session: GPTRealtimeSession,
    logger: Any,
) -> None:
    """Bridge audio streams between client and GPT Realtime.

    Args:
        client_ws: Client WebSocket connection
        realtime_session: GPT Realtime session
        logger: Structured logger
    """

    async def client_to_realtime() -> None:
        """Forward messages from client to GPT Realtime."""
        try:
            while True:
                # Receive from client
                logger.debug("waiting_for_client_message")
                message = await client_ws.receive()
                logger.debug("client_message_received", message_type=message.get("type"))

                if message["type"] == "websocket.disconnect":
                    logger.info("client_initiated_disconnect")
                    break

                # Forward to Realtime API
                if message["type"] == "websocket.receive":
                    if "bytes" in message:
                        # Audio data
                        audio_size = len(message["bytes"])
                        logger.debug("client_audio_received", size_bytes=audio_size)
                        await realtime_session.send_audio(message["bytes"])
                    elif "text" in message:
                        # JSON event
                        data = json.loads(message["text"])
                        logger.info("client_event", event_type=data.get("type"), data=data)

        except WebSocketDisconnect:
            logger.info("client_disconnected_exception")
        except Exception as e:
            logger.exception("client_to_realtime_error", error=str(e), error_type=type(e).__name__)

    async def realtime_to_client() -> None:
        """Forward messages from GPT Realtime to client."""
        try:
            if not realtime_session.connection:
                logger.error("no_realtime_connection")
                return

            logger.info("starting_realtime_to_client_loop")
            async for event in realtime_session.connection:
                try:
                    event_type = event.type

                    logger.info("realtime_event", event_type=event_type)

                    # Handle tool calls internally
                    if event_type == "response.function_call_arguments.done":
                        logger.info("handling_function_call", call_id=event.call_id, name=event.name)
                        await realtime_session._handle_function_call(event)

                    # Forward events to client as JSON
                    await client_ws.send_json({
                        "type": event_type,
                        "event": event.model_dump() if hasattr(event, "model_dump") else {},
                    })
                    logger.debug("event_forwarded_to_client", event_type=event_type)

                except Exception as e:
                    logger.exception("event_forward_error", error=str(e), error_type=type(e).__name__)

        except Exception as e:
            logger.exception("realtime_to_client_error", error=str(e), error_type=type(e).__name__)

    # Run both directions concurrently
    await asyncio.gather(
        client_to_realtime(),
        realtime_to_client(),
        return_exceptions=True,
    )
