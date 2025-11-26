"""CRM tools for voice agents - bookings, contacts, appointments."""

import uuid
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cache import cache_invalidate
from app.models.appointment import Appointment
from app.models.contact import Contact

logger = structlog.get_logger()


class CRMTools:
    """Internal CRM tools for voice agents.

    Provides tools for:
    - Looking up customers by phone/email/name
    - Creating new contacts
    - Checking appointment availability
    - Booking appointments
    - Viewing upcoming appointments
    - Canceling appointments
    """

    def __init__(self, db: AsyncSession, user_id: uuid.UUID) -> None:
        """Initialize CRM tools.

        Args:
            db: Database session
            user_id: User ID (agent owner)
        """
        self.db = db
        self.user_id = user_id
        self.logger = logger.bind(component="crm_tools", user_id=str(user_id))

    @staticmethod
    def get_tool_definitions() -> list[dict[str, Any]]:
        """Get OpenAI function calling tool definitions.

        Returns:
            List of tool definitions for GPT Realtime API (uses nested function format)
        """
        return [
            {
                "type": "function",
                "name": "search_customer",
                "description": "Search for a customer by phone number, email, or name",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Phone number, email, or name to search for",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "type": "function",
                "name": "create_contact",
                "description": "Create a new contact/customer in the CRM",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "first_name": {"type": "string", "description": "Customer's first name"},
                        "last_name": {"type": "string", "description": "Customer's last name"},
                        "phone_number": {
                            "type": "string",
                            "description": "Customer's phone number",
                        },
                        "email": {"type": "string", "description": "Customer's email address"},
                        "company_name": {"type": "string", "description": "Company name"},
                    },
                    "required": ["first_name", "phone_number"],
                },
            },
            {
                "type": "function",
                "name": "check_availability",
                "description": "Check available appointment time slots for a specific date",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Date to check in YYYY-MM-DD format",
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Desired appointment duration in minutes (default 30)",
                        },
                    },
                    "required": ["date"],
                },
            },
            {
                "type": "function",
                "name": "book_appointment",
                "description": "Book an appointment for a customer",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "contact_phone": {
                            "type": "string",
                            "description": "Customer's phone number",
                        },
                        "scheduled_at": {
                            "type": "string",
                            "description": "Appointment date and time in ISO 8601 format (YYYY-MM-DDTHH:MM:SS)",
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration in minutes (default 30)",
                        },
                        "service_type": {
                            "type": "string",
                            "description": "Type of service/appointment",
                        },
                        "notes": {"type": "string", "description": "Additional notes"},
                    },
                    "required": ["contact_phone", "scheduled_at"],
                },
            },
            {
                "type": "function",
                "name": "list_appointments",
                "description": "List upcoming appointments, optionally filtered by date or contact",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "contact_phone": {
                            "type": "string",
                            "description": "Filter by customer phone number",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start date in YYYY-MM-DD format",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date in YYYY-MM-DD format",
                        },
                        "status": {
                            "type": "string",
                            "description": "Filter by status (scheduled, completed, cancelled, no_show)",
                        },
                    },
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "cancel_appointment",
                "description": "Cancel an existing appointment",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "appointment_id": {
                            "type": "integer",
                            "description": "Appointment ID to cancel",
                        },
                        "reason": {"type": "string", "description": "Cancellation reason"},
                    },
                    "required": ["appointment_id"],
                },
            },
            {
                "type": "function",
                "name": "reschedule_appointment",
                "description": "Reschedule an existing appointment to a new time",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "appointment_id": {
                            "type": "integer",
                            "description": "Appointment ID to reschedule",
                        },
                        "new_scheduled_at": {
                            "type": "string",
                            "description": "New appointment time in ISO 8601 format",
                        },
                    },
                    "required": ["appointment_id", "new_scheduled_at"],
                },
            },
        ]

    def _get_user_id_int(self) -> int:
        """Get user_id as integer for Contact model queries.

        The Contact model uses integer user_id, but the tools API passes UUID.
        For now, hardcode to 1 since we don't have proper user mapping.
        TODO: Implement proper user ID mapping when auth is added.
        """
        # Suppress unused variable warning - user_id will be used when auth is implemented
        _ = self.user_id
        return 1

    async def search_customer(self, query: str) -> dict[str, Any]:
        """Search for a customer by phone, email, or name.

        Args:
            query: Search query

        Returns:
            Customer information or error
        """
        try:
            user_id_int = self._get_user_id_int()

            # Search by phone, email, or name - filtered by user_id for security
            # Also search full name (first + last) for queries like "John Smith"
            full_name = func.concat(Contact.first_name, " ", func.coalesce(Contact.last_name, ""))
            stmt = select(Contact).where(
                Contact.user_id == user_id_int,
                (
                    (Contact.phone_number.ilike(f"%{query}%"))
                    | (Contact.email.ilike(f"%{query}%"))
                    | (Contact.first_name.ilike(f"%{query}%"))
                    | (Contact.last_name.ilike(f"%{query}%"))
                    | (full_name.ilike(f"%{query}%"))
                ),
            )

            result = await self.db.execute(stmt)
            contacts = list(result.scalars().all())

            if not contacts:
                return {
                    "success": True,
                    "found": False,
                    "message": f"No customer found matching '{query}'",
                }

            # Return first match (or all if multiple)
            customer_data = [
                {
                    "id": c.id,
                    "name": f"{c.first_name} {c.last_name or ''}".strip(),
                    "phone": c.phone_number,
                    "email": c.email,
                    "company": c.company_name,
                    "status": c.status,
                }
                for c in contacts[:3]  # Limit to 3 results
            ]

            return {
                "success": True,
                "found": True,
                "count": len(customer_data),
                "customers": customer_data,
            }

        except Exception as e:
            self.logger.exception("search_customer_failed", query=query, error=str(e))
            return {"success": False, "error": str(e)}

    async def create_contact(
        self,
        first_name: str,
        phone_number: str,
        last_name: str | None = None,
        email: str | None = None,
        company_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new contact.

        Args:
            first_name: First name
            phone_number: Phone number
            last_name: Last name
            email: Email
            company_name: Company

        Returns:
            Created contact info
        """
        try:
            user_id_int = self._get_user_id_int()
            contact = Contact(
                user_id=user_id_int,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                email=email,
                company_name=company_name,
                status="new",
            )

            self.db.add(contact)
            await self.db.commit()
            await self.db.refresh(contact)

            # Invalidate CRM caches so new contacts appear immediately in the UI
            try:
                await cache_invalidate(f"crm:contacts:list:{user_id_int}:*")
                await cache_invalidate("crm:stats:*")
                self.logger.debug("invalidated_crm_cache_after_create_contact")
            except Exception:
                self.logger.exception("failed_to_invalidate_cache_after_create_contact")

            return {
                "success": True,
                "contact_id": contact.id,
                "message": f"Created contact for {first_name} {last_name or ''}",
            }

        except Exception as e:
            self.logger.exception("create_contact_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def check_availability(
        self, date: str, duration_minutes: int = 30  # noqa: ARG002
    ) -> dict[str, Any]:
        """Check available time slots for a date.

        Args:
            date: Date in YYYY-MM-DD format
            duration_minutes: Desired duration (reserved for future use)

        Returns:
            Available time slots
        """
        try:
            user_id_int = self._get_user_id_int()

            # Parse date
            target_date = datetime.strptime(date, "%Y-%m-%d").date()

            # Get existing appointments for that day - filtered by user's contacts
            stmt = (
                select(Appointment)
                .join(Contact)
                .where(
                    Contact.user_id == user_id_int,
                    Appointment.scheduled_at >= datetime.combine(
                        target_date, datetime.min.time()
                    ),
                    Appointment.scheduled_at < datetime.combine(
                        target_date, datetime.max.time()
                    ),
                    Appointment.status == "scheduled",
                )
            )

            result = await self.db.execute(stmt)
            booked_appointments = list(result.scalars().all())

            # Simple availability: 9 AM to 5 PM, hourly slots
            available_slots = []
            for hour in range(9, 17):  # 9 AM to 5 PM
                slot_time = datetime.combine(target_date, datetime.min.time()).replace(
                    hour=hour
                )

                # Check if slot conflicts with existing appointments
                is_available = True
                for apt in booked_appointments:
                    if apt.scheduled_at.hour == hour:
                        is_available = False
                        break

                if is_available:
                    available_slots.append(slot_time.isoformat())

            return {
                "success": True,
                "date": date,
                "available_slots": available_slots,
                "total_available": len(available_slots),
            }

        except Exception as e:
            self.logger.exception("check_availability_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def book_appointment(
        self,
        contact_phone: str,
        scheduled_at: str,
        duration_minutes: int = 30,
        service_type: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Book an appointment.

        Args:
            contact_phone: Customer phone number
            scheduled_at: ISO 8601 datetime
            duration_minutes: Duration
            service_type: Service type
            notes: Notes

        Returns:
            Booking confirmation
        """
        try:
            user_id_int = self._get_user_id_int()

            # Find contact - filtered by user_id for security
            stmt = select(Contact).where(
                Contact.user_id == user_id_int,
                Contact.phone_number == contact_phone,
            )
            result = await self.db.execute(stmt)
            contact = result.scalar_one_or_none()

            if not contact:
                return {
                    "success": False,
                    "error": f"No contact found with phone {contact_phone}. Please create contact first.",
                }

            # Parse datetime
            appointment_time = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))

            # Create appointment
            appointment = Appointment(
                contact_id=contact.id,
                scheduled_at=appointment_time,
                duration_minutes=duration_minutes,
                service_type=service_type,
                notes=notes,
                status="scheduled",
            )

            self.db.add(appointment)
            await self.db.commit()
            await self.db.refresh(appointment)

            # Invalidate CRM stats cache after booking
            try:
                await cache_invalidate("crm:stats:*")
                self.logger.debug("invalidated_crm_cache_after_book_appointment")
            except Exception:
                self.logger.exception("failed_to_invalidate_cache_after_book_appointment")

            return {
                "success": True,
                "appointment_id": appointment.id,
                "customer_name": f"{contact.first_name} {contact.last_name or ''}",
                "scheduled_at": appointment.scheduled_at.isoformat(),
                "duration_minutes": appointment.duration_minutes,
                "message": f"Appointment booked for {contact.first_name} on {appointment.scheduled_at.strftime('%B %d at %I:%M %p')}",
            }

        except Exception as e:
            self.logger.exception("book_appointment_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def list_appointments(
        self,
        contact_phone: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """List appointments with optional filters.

        Args:
            contact_phone: Filter by phone
            start_date: Start date filter
            end_date: End date filter
            status: Status filter

        Returns:
            List of appointments
        """
        try:
            user_id_int = self._get_user_id_int()

            # Use selectinload to eagerly load contacts in a single query (fixes N+1)
            # Filter by user_id for security
            stmt = (
                select(Appointment)
                .join(Contact)
                .options(selectinload(Appointment.contact))
                .where(Contact.user_id == user_id_int)
            )

            # Apply filters
            if contact_phone:
                stmt = stmt.where(Contact.phone_number == contact_phone)

            if start_date:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                stmt = stmt.where(Appointment.scheduled_at >= start_dt)

            if end_date:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                stmt = stmt.where(Appointment.scheduled_at <= end_dt)

            if status:
                stmt = stmt.where(Appointment.status == status)
            else:
                stmt = stmt.where(Appointment.status == "scheduled")

            stmt = stmt.order_by(Appointment.scheduled_at)

            result = await self.db.execute(stmt)
            appointments = list(result.scalars().all())

            # Contact is already loaded via selectinload - no additional queries needed
            appointment_list = [
                {
                    "id": apt.id,
                    "customer_name": f"{apt.contact.first_name} {apt.contact.last_name or ''}",
                    "phone": apt.contact.phone_number,
                    "scheduled_at": apt.scheduled_at.isoformat(),
                    "duration_minutes": apt.duration_minutes,
                    "service_type": apt.service_type,
                    "status": apt.status,
                }
                for apt in appointments
            ]

            return {
                "success": True,
                "total": len(appointment_list),
                "appointments": appointment_list,
            }

        except Exception as e:
            self.logger.exception("list_appointments_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def cancel_appointment(
        self, appointment_id: int, reason: str | None = None
    ) -> dict[str, Any]:
        """Cancel an appointment.

        Args:
            appointment_id: Appointment ID
            reason: Cancellation reason

        Returns:
            Cancellation confirmation
        """
        try:
            user_id_int = self._get_user_id_int()

            # Verify appointment belongs to user's contact
            stmt = (
                select(Appointment)
                .join(Contact)
                .where(
                    Appointment.id == appointment_id,
                    Contact.user_id == user_id_int,
                )
            )
            result = await self.db.execute(stmt)
            appointment = result.scalar_one_or_none()

            if not appointment:
                return {
                    "success": False,
                    "error": f"Appointment {appointment_id} not found",
                }

            # Update status
            appointment.status = "cancelled"
            if reason:
                appointment.notes = (
                    f"{appointment.notes}\n\nCancellation reason: {reason}"
                    if appointment.notes
                    else f"Cancellation reason: {reason}"
                )

            await self.db.commit()

            return {
                "success": True,
                "appointment_id": appointment_id,
                "message": f"Appointment on {appointment.scheduled_at.strftime('%B %d at %I:%M %p')} has been cancelled",
            }

        except Exception as e:
            self.logger.exception("cancel_appointment_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def reschedule_appointment(
        self, appointment_id: int, new_scheduled_at: str
    ) -> dict[str, Any]:
        """Reschedule an appointment.

        Args:
            appointment_id: Appointment ID
            new_scheduled_at: New datetime in ISO 8601 format

        Returns:
            Reschedule confirmation
        """
        try:
            user_id_int = self._get_user_id_int()

            # Verify appointment belongs to user's contact
            stmt = (
                select(Appointment)
                .join(Contact)
                .where(
                    Appointment.id == appointment_id,
                    Contact.user_id == user_id_int,
                )
            )
            result = await self.db.execute(stmt)
            appointment = result.scalar_one_or_none()

            if not appointment:
                return {
                    "success": False,
                    "error": f"Appointment {appointment_id} not found",
                }

            # Parse new datetime
            new_time = datetime.fromisoformat(new_scheduled_at.replace("Z", "+00:00"))

            old_time = appointment.scheduled_at
            appointment.scheduled_at = new_time

            await self.db.commit()

            return {
                "success": True,
                "appointment_id": appointment_id,
                "old_time": old_time.strftime("%B %d at %I:%M %p"),
                "new_time": new_time.strftime("%B %d at %I:%M %p"),
                "message": f"Appointment rescheduled from {old_time.strftime('%B %d at %I:%M %p')} to {new_time.strftime('%B %d at %I:%M %p')}",
            }

        except Exception as e:
            self.logger.exception("reschedule_appointment_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def execute_tool(  # noqa: PLR0911
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a CRM tool by name.

        Args:
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if tool_name == "search_customer":
            return await self.search_customer(**arguments)
        if tool_name == "create_contact":
            return await self.create_contact(**arguments)
        if tool_name == "check_availability":
            return await self.check_availability(**arguments)
        if tool_name == "book_appointment":
            return await self.book_appointment(**arguments)
        if tool_name == "list_appointments":
            return await self.list_appointments(**arguments)
        if tool_name == "cancel_appointment":
            return await self.cancel_appointment(**arguments)
        if tool_name == "reschedule_appointment":
            return await self.reschedule_appointment(**arguments)
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
