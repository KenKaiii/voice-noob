"""Twilio telephony service implementation."""

import structlog
from twilio.rest import Client
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.services.telephony.base import (
    CallDirection,
    CallInfo,
    CallStatus,
    PhoneNumber,
    TelephonyProvider,
)

logger = structlog.get_logger()


class TwilioService(TelephonyProvider):
    """Twilio telephony service for voice calls and phone number management."""

    def __init__(self, account_sid: str, auth_token: str):
        """Initialize Twilio client.

        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
        """
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.client = Client(account_sid, auth_token)
        self.logger = logger.bind(provider="twilio")

    async def initiate_call(
        self,
        to_number: str,
        from_number: str,
        webhook_url: str,
        agent_id: str | None = None,
    ) -> CallInfo:
        """Initiate an outbound call via Twilio.

        Args:
            to_number: Destination phone number (E.164 format)
            from_number: Source phone number (E.164 format)
            webhook_url: URL for TwiML instructions when call connects
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

        # Build callback URLs
        status_callback = webhook_url.replace("/answer", "/status")

        call = self.client.calls.create(
            to=to_number,
            from_=from_number,
            url=webhook_url,
            status_callback=status_callback,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
        )

        self.logger.info("call_initiated", call_sid=call.sid)

        return CallInfo(
            call_id=call.sid,
            call_control_id=call.sid,
            from_number=from_number,
            to_number=to_number,
            direction=CallDirection.OUTBOUND,
            status=CallStatus.INITIATED,
            agent_id=agent_id,
        )

    async def hangup_call(self, call_id: str) -> bool:
        """Hang up an active Twilio call.

        Args:
            call_id: Twilio Call SID

        Returns:
            True if successful
        """
        self.logger.info("hanging_up_call", call_sid=call_id)

        try:
            self.client.calls(call_id).update(status="completed")
            return True
        except Exception as e:
            self.logger.exception("hangup_failed", call_sid=call_id, error=str(e))
            return False

    async def list_phone_numbers(self) -> list[PhoneNumber]:
        """List all Twilio phone numbers.

        Returns:
            List of PhoneNumber objects
        """
        self.logger.info("listing_phone_numbers")

        numbers = []
        for number in self.client.incoming_phone_numbers.list():
            numbers.append(
                PhoneNumber(
                    id=number.sid,
                    phone_number=number.phone_number,
                    friendly_name=number.friendly_name,
                    provider="twilio",
                    capabilities={
                        "voice": number.capabilities.get("voice", False),
                        "sms": number.capabilities.get("sms", False),
                        "mms": number.capabilities.get("mms", False),
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
        """Search for available Twilio phone numbers.

        Args:
            country: Country code (e.g., "US")
            area_code: Area code filter
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

        # Build search parameters
        params: dict[str, str | int | bool] = {
            "voice_enabled": True,
            "limit": limit,
        }
        if area_code:
            params["area_code"] = area_code
        if contains:
            params["contains"] = contains

        numbers = []
        available = self.client.available_phone_numbers(country).local.list(**params)

        for number in available:
            numbers.append(
                PhoneNumber(
                    id="",  # Not purchased yet
                    phone_number=number.phone_number,
                    friendly_name=number.friendly_name,
                    provider="twilio",
                    capabilities={
                        "voice": number.capabilities.get("voice", False),
                        "sms": number.capabilities.get("sms", False),
                        "mms": number.capabilities.get("mms", False),
                    },
                )
            )

        self.logger.info("phone_numbers_found", count=len(numbers))
        return numbers

    async def purchase_phone_number(self, phone_number: str) -> PhoneNumber:
        """Purchase a Twilio phone number.

        Args:
            phone_number: Phone number to purchase (E.164 format)

        Returns:
            Purchased PhoneNumber object
        """
        self.logger.info("purchasing_phone_number", phone_number=phone_number)

        number = self.client.incoming_phone_numbers.create(phone_number=phone_number)

        self.logger.info("phone_number_purchased", sid=number.sid)

        return PhoneNumber(
            id=number.sid,
            phone_number=number.phone_number,
            friendly_name=number.friendly_name,
            provider="twilio",
            capabilities={
                "voice": number.capabilities.get("voice", False),
                "sms": number.capabilities.get("sms", False),
                "mms": number.capabilities.get("mms", False),
            },
        )

    async def release_phone_number(self, phone_number_id: str) -> bool:
        """Release a Twilio phone number.

        Args:
            phone_number_id: Phone number SID to release

        Returns:
            True if successful
        """
        self.logger.info("releasing_phone_number", sid=phone_number_id)

        try:
            self.client.incoming_phone_numbers(phone_number_id).delete()
            return True
        except Exception as e:
            self.logger.exception("release_failed", sid=phone_number_id, error=str(e))
            return False

    async def configure_phone_number_webhook(
        self,
        phone_number_id: str,
        voice_url: str,
        status_callback_url: str | None = None,
    ) -> bool:
        """Configure webhook URLs for a phone number.

        Args:
            phone_number_id: Phone number SID
            voice_url: URL for incoming call webhooks
            status_callback_url: URL for status callbacks

        Returns:
            True if successful
        """
        self.logger.info(
            "configuring_webhook",
            sid=phone_number_id,
            voice_url=voice_url,
        )

        try:
            update_params: dict[str, str] = {
                "voice_url": voice_url,
                "voice_method": "POST",
            }
            if status_callback_url:
                update_params["status_callback"] = status_callback_url
                update_params["status_callback_method"] = "POST"

            self.client.incoming_phone_numbers(phone_number_id).update(**update_params)
            return True
        except Exception as e:
            self.logger.exception("webhook_config_failed", sid=phone_number_id, error=str(e))
            return False

    def generate_answer_response(self, websocket_url: str, agent_id: str | None = None) -> str:
        """Generate TwiML response to answer a call and stream to WebSocket.

        Args:
            websocket_url: WebSocket URL for media streaming
            agent_id: Optional agent ID for context

        Returns:
            TwiML response string
        """
        response = VoiceResponse()

        # Connect to WebSocket for media streaming
        connect = Connect()
        stream = connect.stream(url=websocket_url)

        # Add custom parameters to the stream
        if agent_id:
            stream.parameter(name="agent_id", value=agent_id)

        response.append(connect)

        return str(response)

    def generate_gather_response(
        self,
        message: str,
        action_url: str,
        num_digits: int = 1,
        timeout: int = 5,
    ) -> str:
        """Generate TwiML response to gather DTMF input.

        Args:
            message: Message to speak before gathering
            action_url: URL to send gathered digits to
            num_digits: Number of digits to gather
            timeout: Timeout in seconds

        Returns:
            TwiML response string
        """
        response = VoiceResponse()
        gather = response.gather(
            num_digits=num_digits,
            action=action_url,
            method="POST",
            timeout=timeout,
        )
        gather.say(message)
        return str(response)

    async def get_call_info(self, call_sid: str) -> CallInfo | None:
        """Get information about a call.

        Args:
            call_sid: Twilio Call SID

        Returns:
            CallInfo or None if not found
        """
        try:
            call = self.client.calls(call_sid).fetch()

            # Map Twilio status to our CallStatus
            status_map = {
                "queued": CallStatus.INITIATED,
                "ringing": CallStatus.RINGING,
                "in-progress": CallStatus.IN_PROGRESS,
                "completed": CallStatus.COMPLETED,
                "busy": CallStatus.BUSY,
                "failed": CallStatus.FAILED,
                "no-answer": CallStatus.NO_ANSWER,
                "canceled": CallStatus.CANCELED,
            }

            return CallInfo(
                call_id=call.sid,
                call_control_id=call.sid,
                from_number=call.from_formatted or call.from_,
                to_number=call.to_formatted or call.to,
                direction=CallDirection.INBOUND
                if call.direction == "inbound"
                else CallDirection.OUTBOUND,
                status=status_map.get(call.status, CallStatus.INITIATED),
                duration_seconds=int(call.duration) if call.duration else 0,
            )
        except Exception as e:
            self.logger.exception("get_call_info_failed", call_sid=call_sid, error=str(e))
            return None
