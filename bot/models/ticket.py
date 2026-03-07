# bot/models/ticket.py
from datetime import datetime, timezone
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from bot.models.database import SupportTicket, SupportMessage, TicketStatus


class TicketRepo:
    @staticmethod
    async def get_or_create_open(session: AsyncSession, user_id: int, user_telegram_id: int) -> SupportTicket:
        result = await session.execute(
            select(SupportTicket)
            .where(
                SupportTicket.user_id == user_id,
                SupportTicket.status != TicketStatus.CLOSED,
            )
            .order_by(SupportTicket.updated_at.desc())
            .limit(1)
        )
        ticket = result.scalar_one_or_none()
        if ticket:
            return ticket
        ticket = SupportTicket(
            user_id=user_id,
            user_telegram_id=user_telegram_id,
            status=TicketStatus.OPEN,
        )
        session.add(ticket)
        await session.flush()
        return ticket

    @staticmethod
    async def get_by_id(session: AsyncSession, ticket_id: int) -> SupportTicket | None:
        result = await session.execute(
            select(SupportTicket)
            .options(selectinload(SupportTicket.messages))
            .where(SupportTicket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_user_telegram_id(session: AsyncSession, telegram_id: int) -> SupportTicket | None:
        result = await session.execute(
            select(SupportTicket)
            .options(selectinload(SupportTicket.messages))
            .where(
                SupportTicket.user_telegram_id == telegram_id,
                SupportTicket.status != TicketStatus.CLOSED,
            )
            .order_by(SupportTicket.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def add_message(
        session: AsyncSession, ticket_id: int,
        sender_telegram_id: int, text: str, is_admin: bool = False,
    ) -> SupportMessage:
        msg = SupportMessage(
            ticket_id=ticket_id,
            sender_telegram_id=sender_telegram_id,
            is_admin=is_admin,
            message_text=text,
        )
        session.add(msg)
        new_status = TicketStatus.REPLIED if is_admin else TicketStatus.OPEN
        await session.execute(
            update(SupportTicket)
            .where(SupportTicket.id == ticket_id)
            .values(status=new_status, updated_at=datetime.now(timezone.utc))
        )
        await session.flush()
        return msg

    @staticmethod
    async def close_ticket(session: AsyncSession, ticket_id: int) -> SupportTicket | None:
        result = await session.execute(
            select(SupportTicket).where(SupportTicket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        if ticket:
            ticket.status = TicketStatus.CLOSED
            ticket.closed_at = datetime.now(timezone.utc)
            await session.flush()
        return ticket

    @staticmethod
    async def reopen_ticket(session: AsyncSession, ticket_id: int) -> SupportTicket | None:
        result = await session.execute(
            select(SupportTicket).where(SupportTicket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        if ticket:
            ticket.status = TicketStatus.OPEN
            ticket.closed_at = None
            await session.flush()
        return ticket

    @staticmethod
    async def get_all_tickets(
        session: AsyncSession,
        status: TicketStatus | None = None,
        page: int = 1, per_page: int = 10,
    ) -> tuple[list[SupportTicket], int]:
        stmt = select(SupportTicket).options(selectinload(SupportTicket.user))
        count_stmt = select(func.count(SupportTicket.id))
        if status:
            stmt = stmt.where(SupportTicket.status == status)
            count_stmt = count_stmt.where(SupportTicket.status == status)
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(
            SupportTicket.status.asc(),
            SupportTicket.updated_at.desc(),
        ).offset((page - 1) * per_page).limit(per_page)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def get_ticket_history(session: AsyncSession, ticket_id: int, limit: int = 50) -> list[SupportMessage]:
        result = await session.execute(
            select(SupportMessage)
            .where(SupportMessage.ticket_id == ticket_id)
            .order_by(SupportMessage.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_open_count(session: AsyncSession) -> int:
        return (await session.execute(
            select(func.count(SupportTicket.id))
            .where(SupportTicket.status == TicketStatus.OPEN)
        )).scalar_one()

    @staticmethod
    async def get_user_ticket_count(session: AsyncSession, user_id: int) -> int:
        return (await session.execute(
            select(func.count(SupportTicket.id))
            .where(SupportTicket.user_id == user_id)
        )).scalar_one()