import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from pytz import timezone as pytz_timezone

# Ensure project root is on sys.path when running as a script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import async_session_maker
from database.models.appointment import Appointment, AppointmentStatus
from database.models.master import Master
from sqlalchemy import select, and_, or_

"""
One-off migration tool to correct appointments created before the timezone fix.

Usage examples (PowerShell):
  # Dry run: show how many rows would be updated for all masters between dates, +3h shift
    python scripts/fix_timezone.py --from 2025-12-01 --to 2025-12-31 --offset 4

  # Apply for a specific master by Telegram ID
    python scripts/fix_timezone.py --from 2025-12-01 --to 2025-12-31 --offset 4 --master 123456789 --apply

Notes:
- The script shifts both start_time and end_time by a fixed number of hours.
- It targets only appointments in the provided date window. If not specified, uses [today-30d, today+30d].
- Use --dry-run (default) to preview changes safely.
"""


def parse_args():
    p = argparse.ArgumentParser(description="Fix timezone offset for old appointments")
    p.add_argument("--from", dest="date_from", help="Date from (YYYY-MM-DD)")
    p.add_argument("--to", dest="date_to", help="Date to (YYYY-MM-DD)")
    p.add_argument("--offset", type=int, required=True, help="Hour offset to add (e.g., 3 or -3)")
    p.add_argument("--master", type=int, help="Filter by master's Telegram ID")
    p.add_argument("--apply", action="store_true", help="Apply changes (omit for dry run)")
    return p.parse_args()


async def main():
    args = parse_args()
    today = datetime.now(timezone.utc).date()
    date_from = datetime.strptime(args.date_from, "%Y-%m-%d").date() if args.date_from else (today - timedelta(days=30))
    date_to = datetime.strptime(args.date_to, "%Y-%m-%d").date() if args.date_to else (today + timedelta(days=30))
    offset = timedelta(hours=args.offset)

    async with async_session_maker() as session:
        # Load masters filter map by telegram id if provided
        masters_q = select(Master)
        if args.master:
            masters_q = masters_q.where(Master.telegram_id == args.master)
        masters = (await session.execute(masters_q)).scalars().all()
        if not masters:
            print("No masters found for filter")
            return
        total_updates = 0
        for m in masters:
            tz = pytz_timezone(m.timezone or "Europe/Moscow")
            # Select appointments in date window for this master
            start_dt = datetime(date_from.year, date_from.month, date_from.day)
            end_dt = datetime(date_to.year, date_to.month, date_to.day) + timedelta(days=1)
            apps_q = select(Appointment).where(
                and_(
                    Appointment.master_id == m.id,
                    Appointment.start_time >= start_dt,
                    Appointment.start_time < end_dt,
                    Appointment.status.in_([
                        AppointmentStatus.SCHEDULED.value,
                        AppointmentStatus.CONFIRMED.value,
                        AppointmentStatus.RESCHEDULED.value,
                        AppointmentStatus.COMPLETED.value,
                    ])
                )
            )
            apps = (await session.execute(apps_q)).scalars().all()
            if not apps:
                continue
            print(f"Master {m.id} (tz={m.timezone}) appointments: {len(apps)}")
            for a in apps:
                old_start, old_end = a.start_time, a.end_time
                new_start = old_start + offset
                new_end = old_end + offset
                print(f"  #{a.id}: {old_start} -> {new_start}")
                if args.apply:
                    a.start_time = new_start
                    a.end_time = new_end
                    session.add(a)
                    total_updates += 1
        if args.apply:
            await session.commit()
            print(f"Done. Updated {total_updates} appointments.")
        else:
            print("Dry run. No changes written. Use --apply to commit.")


if __name__ == "__main__":
    asyncio.run(main())
