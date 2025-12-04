"""Repository for Expense model operations."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.expense import Expense


class ExpenseRepository:
    """Repository for managing expenses."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        master_id: int,
        category: str,
        amount: int,
        expense_date: datetime,
        description: Optional[str] = None
    ) -> Expense:
        """Create a new expense."""
        expense = Expense(
            master_id=master_id,
            category=category,
            amount=amount,
            expense_date=expense_date,
            description=description
        )
        self.session.add(expense)
        await self.session.flush()
        return expense
    
    async def get_by_id(self, expense_id: int) -> Optional[Expense]:
        """Get expense by ID."""
        stmt = select(Expense).where(Expense.id == expense_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_master(
        self,
        master_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category: Optional[str] = None
    ) -> List[Expense]:
        """
        Get expenses for a master with optional filters.
        
        Args:
            master_id: Master ID
            start_date: Filter expenses from this date (inclusive)
            end_date: Filter expenses until this date (inclusive)
            category: Filter by category
        
        Returns:
            List of expenses
        """
        conditions = [Expense.master_id == master_id]
        
        if start_date:
            conditions.append(Expense.expense_date >= start_date)
        if end_date:
            conditions.append(Expense.expense_date <= end_date)
        if category:
            conditions.append(Expense.category == category)
        
        stmt = select(Expense).where(and_(*conditions)).order_by(Expense.expense_date.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def update(self, expense: Expense) -> Expense:
        """Update an existing expense."""
        self.session.add(expense)
        await self.session.flush()
        return expense
    
    async def delete(self, expense_id: int) -> bool:
        """Delete an expense."""
        expense = await self.get_by_id(expense_id)
        if not expense:
            return False
        await self.session.delete(expense)
        await self.session.flush()
        return True
    
    async def get_total_by_period(
        self,
        master_id: int,
        start_date: datetime,
        end_date: datetime,
        category: Optional[str] = None
    ) -> int:
        """
        Calculate total expenses for a period.
        
        Args:
            master_id: Master ID
            start_date: Start of period
            end_date: End of period
            category: Optional category filter
        
        Returns:
            Total amount of expenses
        """
        conditions = [
            Expense.master_id == master_id,
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date
        ]
        
        if category:
            conditions.append(Expense.category == category)
        
        stmt = select(func.sum(Expense.amount)).where(and_(*conditions))
        result = await self.session.execute(stmt)
        total = result.scalar()
        return total if total else 0
    
    async def get_expenses_by_category(
        self,
        master_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[dict]:
        """
        Get expenses grouped by category for a period.
        
        Returns:
            List of dicts with category and total amount
        """
        stmt = (
            select(
                Expense.category,
                func.sum(Expense.amount).label('total')
            )
            .where(
                and_(
                    Expense.master_id == master_id,
                    Expense.expense_date >= start_date,
                    Expense.expense_date <= end_date
                )
            )
            .group_by(Expense.category)
            .order_by(func.sum(Expense.amount).desc())
        )
        
        result = await self.session.execute(stmt)
        return [
            {"category": row.category, "total": row.total}
            for row in result.all()
        ]
