"""Telnyx telephony service implementation."""

import httpx
import structlog
import telnyx

from app.services.telephony.base import (
    CallDirection,
    CallInfo,
    CallStatus,
    PhoneNumber,
    TelephonyProvider,
)

logger = structlog.get_logger()


class TelnyxService(TelephonyProvider):
    """Telnyx telephony service for voice calls and phone number management."""

    def __init__(self, api_key: str, public_key: str | None = None):
        """Initialize Telnyx client.

        Args:
            api_key: Telnyx API Key
            public_key: Telnyx Public Key (for webhook verification)
        """
        self.api_key = api_key
        self.public_key = public_key
        telnyx.api_key = api_key  # type: ignore[attr-defined]
        self.logger = logger.bind(provider="telnyx")
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for TeXML API calls."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url="https://api.telnyx.com/v2",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._http_client

    async def initiate_call(
        self,
        to_number: str,
        from_number: str,
        webhook_url: str,
        agent_id: str | None = None,
    ) -> CallInfo:
        """Initiate an outbound call via Telnyx TeXML.

        Args:
            to_number: Destination phone number (E.164 format)
            from_number: Source phone number (E.164 format)
            webhook_url: URL for TeXML instructions when call connects
            agent_id: Optional agent ID for context

        Returns:
            CallInfo with call details
        """
        self.logger.info(
            "initiating_call",
            to=to_number,
            from_=from_number,
            webhook_url=webhook_url,
            agent_id=agent_id,
        )

        client = await self._get_http_client()

        # Use Telnyx TeXML API for call initiation
        payload = {
            "to": to_number,
            "from": from_number,
            "connection_id": await self._get_connection_id(),
            "texml_url": webhook_url,
        }

        response = await client.post("/texml/calls", json=payload)
        response.raise_for_status()
        data = response.json()

        call_data = data.get("data", {})
        call_control_id = call_data.get("call_control_id", "")
        call_sid = call_data.get("sid", call_control_id)

        self.logger.info("call_initiated", call_control_id=call_control_id)

        return CallInfo(
            call_id=call_sid,
            call_control_id=call_control_id,
            from_number=from_number,
            to_number=to_number,
            direction=CallDirection.OUTBOUND,
            status=CallStatus.INITIATED,
            agent_id=agent_id,
        )

    async def initiate_call_via_call_control(
        self,
        to_number: str,
        from_number: str,
        connection_id: str,
        webhook_url: str,
        agent_id: str | None = None,
    ) -> CallInfo:
        """Initiate an outbound call via Telnyx Call Control API.

        Args:
            to_number: Destination phone number (E.164 format)
            from_number: Source phone number (E.164 format)
            connection_id: Telnyx connection ID
            webhook_url: URL for call event webhooks
            agent_id: Optional agent ID for context

        Returns:
            CallInfo with call details
        """
        self.logger.info(
            "initiating_call_via_call_control",
            to=to_number,
            from_=from_number,
            connection_id=connection_id,
        )

        call = telnyx.Call.create(  # type: ignore[attr-defined]
            connection_id=connection_id,
            to=to_number,
            from_=from_number,
            webhook_url=webhook_url,
        )

        self.logger.info("call_initiated", call_control_id=call.call_control_id)

        return CallInfo(
            call_id=call.call_control_id,
            call_control_id=call.call_control_id,
            from_number=from_number,
            to_number=to_number,
            direction=CallDirection.OUTBOUND,
            status=CallStatus.INITIATED,
            agent_id=agent_id,
        )

    async def hangup_call(self, call_id: str) -> bool:
        """Hang up an active Telnyx call.

        Args:
            call_id: Telnyx Call Control ID

        Returns:
            True if successful
        """
        self.logger.info("hanging_up_call", call_control_id=call_id)

        try:
            client = await self._get_http_client()
            response = await client.post(f"/calls/{call_id}/actions/hangup", json={})
            response.raise_for_status()
            return True
        except Exception:
            self.logger.exception("hangup_failed", call_control_id=call_id)
            return False

    async def answer_call(self, call_control_id: str, webhook_url: str | None = None) -> bool:
        """Answer an incoming call.

        Args:
            call_control_id: Telnyx Call Control ID
            webhook_url: Optional webhook URL for call events

        Returns:
            True if successful
        """
        self.logger.info("answering_call", call_control_id=call_control_id)

        try:
            client = await self._get_http_client()
            payload: dict[str, str] = {}
            if webhook_url:
                payload["webhook_url"] = webhook_url

            response = await client.post(
                f"/calls/{call_control_id}/actions/answer",
                json=payload,
            )
            response.raise_for_status()
            return True
        except Exception:
            self.logger.exception("answer_failed", call_control_id=call_control_id)
            return False

    async def stream_audio(
        self,
        call_control_id: str,
        stream_url: str,
        stream_track: str = "both_tracks",
    ) -> bool:
        """Start streaming audio to/from a WebSocket.

        Args:
            call_control_id: Telnyx Call Control ID
            stream_url: WebSocket URL for audio streaming
            stream_track: Which tracks to stream (inbound_track, outbound_track, both_tracks)

        Returns:
            True if successful
        """
        self.logger.info(
            "starting_stream",
            call_control_id=call_control_id,
            stream_url=stream_url,
        )

        try:
            client = await self._get_http_client()
            response = await client.post(
                f"/calls/{call_control_id}/actions/streaming_start",
                json={
                    "stream_url": stream_url,
                    "stream_track": stream_track,
                },
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.exception(
                "stream_start_failed", call_control_id=call_control_id, error=str(e)
            )
            return False

    async def list_phone_numbers(self) -> list[PhoneNumber]:
        """List all Telnyx phone numbers.

        Returns:
            List of PhoneNumber objects
        """
        self.logger.info("listing_phone_numbers")

        numbers = []
        client = await self._get_http_client()

        response = await client.get("/phone_numbers")
        response.raise_for_status()
        data = response.json()

        for number in data.get("data", []):
            numbers.append(
                PhoneNumber(
                    id=number.get("id", ""),
                    phone_number=number.get("phone_number", ""),
                    friendly_name=number.get("connection_name"),
                    provider="telnyx",
                    capabilities={
                        "voice": True,
                        "sms": number.get("messaging_profile_id") is not None,
                    },
                )
            )

        self.logger.info("phone_numbers_listed", count=len(numbers))
        return numbers

    async def search_phone_numbers(
        self,
        country: str = "US",
        area_code: str | None = None,
        contains: str | None = None,
        limit: int = 10,
    ) -> list[PhoneNumber]:
        """Search for available Telnyx phone numbers.

        Args:
            country: Country code (e.g., "US")
            area_code: Area code filter (NPA)
            contains: Pattern to match
            limit: Maximum results

        Returns:
            List of available PhoneNumber objects
        """
        self.logger.info(
            "searching_phone_numbers",
            country=country,
            area_code=area_code,
            contains=contains,
        )

        client = await self._get_http_client()

        params: dict[str, str | int | bool] = {
            "filter[country_code]": country,
            "filter[features]": "voice",
            "filter[limit]": limit,
        }
        if area_code:
            params["filter[national_destination_code]"] = area_code
        if contains:
            params["filter[phone_number][contains]"] = contains

        response = await client.get("/available_phone_numbers", params=params)
        response.raise_for_status()
        data = response.json()

        numbers = []
        for number in data.get("data", []):
            numbers.append(
                PhoneNumber(
                    id="",  # Not purchased yet
                    phone_number=number.get("phone_number", ""),
                    friendly_name=number.get("region_information", [{}])[0].get("region_name"),
                    provider="telnyx",
                    capabilities={
                        "voice": "voice" in number.get("features", []),
                        "sms": "sms" in number.get("features", []),
                    },
                )
            )

        self.logger.info("phone_numbers_found", count=len(numbers))
        return numbers

    async def purchase_phone_number(self, phone_number: str) -> PhoneNumber:
        """Purchase a Telnyx phone number.

        Args:
            phone_number: Phone number to purchase (E.164 format)

        Returns:
            Purchased PhoneNumber object
        """
        self.logger.info("purchasing_phone_number", phone_number=phone_number)

        client = await self._get_http_client()

        # First, create a number order
        response = await client.post(
            "/number_orders",
            json={
                "phone_numbers": [{"phone_number": phone_number}],
            },
        )
        response.raise_for_status()
        order_data = response.json()

        # Get the phone number ID from the order
        phone_numbers = order_data.get("data", {}).get("phone_numbers", [])
        if not phone_numbers:
            raise ValueError("No phone number returned from order")

        number_data = phone_numbers[0]

        self.logger.info("phone_number_purchased", id=number_data.get("id"))

        return PhoneNumber(
            id=number_data.get("id", ""),
            phone_number=number_data.get("phone_number", phone_number),
            friendly_name=None,
            provider="telnyx",
            capabilities={"voice": True, "sms": True},
        )

    async def release_phone_number(self, phone_number_id: str) -> bool:
        """Release a Telnyx phone number.

        Args:
            phone_number_id: Phone number ID to release

        Returns:
            True if successful
        """
        self.logger.info("releasing_phone_number", id=phone_number_id)

        try:
            client = await self._get_http_client()
            response = await client.delete(f"/phone_numbers/{phone_number_id}")
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.exception("release_failed", id=phone_number_id, error=str(e))
            return False

    async def configure_phone_number(
        self,
        phone_number_id: str,
        connection_id: str | None = None,
        texml_application_id: str | None = None,
    ) -> bool:
        """Configure a phone number with connection or TeXML application.

        Args:
            phone_number_id: Phone number ID
            connection_id: Telnyx connection ID for Call Control
            texml_application_id: Telnyx TeXML Application ID

        Returns:
            True if successful
        """
        self.logger.info(
            "configuring_phone_number",
            id=phone_number_id,
            connection_id=connection_id,
            texml_application_id=texml_application_id,
        )

        try:
            client = await self._get_http_client()
            payload: dict[str, str] = {}

            if connection_id:
                payload["connection_id"] = connection_id
            if texml_application_id:
                payload["texml_application_id"] = texml_application_id

            response = await client.patch(
                f"/phone_numbers/{phone_number_id}",
                json=payload,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.exception("configure_failed", id=phone_number_id, error=str(e))
            return False

    async def _get_connection_id(self) -> str:
        """Get or create a Telnyx connection for outbound calls.

        Returns:
            Connection ID string
        """
        # List existing connections
        client = await self._get_http_client()
        response = await client.get("/credential_connections")
        response.raise_for_status()
        data = response.json()

        connections = data.get("data", [])
        if connections:
            return str(connections[0].get("id", ""))

        # Create a new connection if none exists
        response = await client.post(
            "/credential_connections",
            json={
                "connection_name": "voice-agent-connection",
                "active": True,
            },
        )
        response.raise_for_status()
        new_data = response.json()
        return str(new_data.get("data", {}).get("id", ""))

    def generate_answer_response(self, websocket_url: str, agent_id: str | None = None) -> str:  # noqa: ARG002
        """Generate TeXML response to answer a call and stream to WebSocket.

        Args:
            websocket_url: WebSocket URL for media streaming
            agent_id: Optional agent ID for context

        Returns:
            TeXML response string
        """
        # Build TeXML with proper XML escaping for & in URLs
        escaped_ws_url = websocket_url.replace("&", "&amp;")

        texml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{escaped_ws_url}" />
    </Connect>
</Response>"""

        return texml

    def generate_gather_response(
        self,
        message: str,
        action_url: str,
        num_digits: int = 1,
        timeout: int = 5,
    ) -> str:
        """Generate TeXML response to gather DTMF input.

        Args:
            message: Message to speak before gathering
            action_url: URL to send gathered digits to
            num_digits: Number of digits to gather
            timeout: Timeout in seconds

        Returns:
            TeXML response string
        """
        escaped_action_url = action_url.replace("&", "&amp;")

        texml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather numDigits="{num_digits}" action="{escaped_action_url}" method="POST" timeout="{timeout}">
        <Say>{message}</Say>
    </Gather>
</Response>"""

        return texml

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
