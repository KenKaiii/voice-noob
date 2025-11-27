"""Base telephony provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CallDirection(str, Enum):
    """Call direction."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, Enum):
    """Call status."""

    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no_answer"
    CANCELED = "canceled"


@dataclass
class PhoneNumber:
    """Phone number information."""

    id: str
    phone_number: str
    friendly_name: str | None = None
    provider: str = ""
    capabilities: dict[str, Any] | None = None
    assigned_agent_id: str | None = None


@dataclass
class CallInfo:
    """Call information."""

    call_id: str
    call_control_id: str | None = None
    from_number: str = ""
    to_number: str = ""
    direction: CallDirection = CallDirection.INBOUND
    status: CallStatus = CallStatus.INITIATED
    agent_id: str | None = None
    duration_seconds: int = 0
    recording_url: str | None = None


class TelephonyProvider(ABC):
    """Abstract base class for telephony providers."""

    @abstractmethod
    async def initiate_call(
        self,
        to_number: str,
        from_number: str,
        webhook_url: str,
        agent_id: str | None = None,
    ) -> CallInfo:
        """Initiate an outbound call.

        Args:
            to_number: Destination phone number (E.164 format)
            from_number: Source phone number (E.164 format)
            webhook_url: URL for call status callbacks
            agent_id: Optional agent ID for context

        Returns:
            CallInfo with call details
        """
        ...

    @abstractmethod
    async def hangup_call(self, call_id: str) -> bool:
        """Hang up an active call.

        Args:
            call_id: Call identifier

        Returns:
            True if successful
        """
        ...

    @abstractmethod
    async def list_phone_numbers(self) -> list[PhoneNumber]:
        """List all phone numbers for this account.

        Returns:
            List of PhoneNumber objects
        """
        ...

    @abstractmethod
    async def search_phone_numbers(
        self,
        country: str = "US",
        area_code: str | None = None,
        contains: str | None = None,
        limit: int = 10,
    ) -> list[PhoneNumber]:
        """Search for available phone numbers to purchase.

        Args:
            country: Country code (e.g., "US")
            area_code: Area code filter
            contains: Pattern to match
            limit: Maximum results

        Returns:
            List of available PhoneNumber objects
        """
        ...

    @abstractmethod
    async def purchase_phone_number(self, phone_number: str) -> PhoneNumber:
        """Purchase a phone number.

        Args:
            phone_number: Phone number to purchase (E.164 format)

        Returns:
            Purchased PhoneNumber object
        """
        ...

    @abstractmethod
    async def release_phone_number(self, phone_number_id: str) -> bool:
        """Release a phone number.

        Args:
            phone_number_id: Phone number ID to release

        Returns:
            True if successful
        """
        ...

    @abstractmethod
    def generate_answer_response(self, websocket_url: str, agent_id: str | None = None) -> str:
        """Generate TwiML/TeXML response to answer a call and stream to WebSocket.

        Args:
            websocket_url: WebSocket URL for media streaming
            agent_id: Optional agent ID for context

        Returns:
            XML response string (TwiML for Twilio, TeXML for Telnyx)
        """
        ...
