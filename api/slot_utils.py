from datetime import datetime, date, time, timedelta
from .models import MentorAvailability, Booking, User


def parse_iso_datetime(dt_str):
    if not dt_str:
        return None
    s = str(dt_str).strip()
    if s.endswith('Z'):
        s = s[:-1]
    if '+' in s:
        s = s.split('+')[0]
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def get_mentor_availability_windows(mentor_id, js_day_of_week):
    """
    Returns list of (start_time_str, end_time_str) tuples for this mentor on the given day.
    js_day_of_week: 0=Sunday, 1=Monday ... 6=Saturday.
    If mentor has configured availability: returns matching rules for that day.
    If mentor has no availability configured at all: returns default [("09:00", "21:00")].
    """
    has_any = MentorAvailability.objects.filter(user_id=mentor_id).exists()
    if not has_any:
        return [("09:00", "21:00")]

    rules = MentorAvailability.objects.filter(user_id=mentor_id, day_of_week=js_day_of_week)
    if not rules.exists():
        return []

    windows = []
    for r in rules:
        windows.append((r.start_time[:5], r.end_time[:5]))
    return windows


def get_mentor_active_booked_windows(mentor_id, date_obj=None, exclude_booking_id=None):
    """
    Returns list of (start_dt, end_dt) for all active bookings of this mentor.
    """
    qs = Booking.objects.filter(
        mentor_id=mentor_id,
        status__in=['pending', 'accepted', 'paid']
    ).exclude(scheduled_at__isnull=True).exclude(scheduled_at='')

    if exclude_booking_id:
        qs = qs.exclude(id=exclude_booking_id)

    windows = []
    for b in qs:
        b_start = parse_iso_datetime(b.scheduled_at)
        if b_start:
            b_end = b_start + timedelta(minutes=b.duration_minutes or 30)
            if date_obj is not None:
                day_start = datetime.combine(date_obj, time(0, 0))
                day_end = datetime.combine(date_obj + timedelta(days=1), time(0, 0))
                if b_start < day_end and b_end > day_start:
                    windows.append((b_start, b_end))
            else:
                windows.append((b_start, b_end))
    return windows


def check_slot_conflict(mentor_id, start_dt, duration_minutes, exclude_booking_id=None):
    """
    Checks if [start_dt, start_dt + duration_minutes) overlaps with any active booking for this mentor.
    Returns (True, conflict_booking) if there is an overlap, or (False, None) if free.
    """
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    qs = Booking.objects.filter(
        mentor_id=mentor_id,
        status__in=['pending', 'accepted', 'paid']
    ).exclude(scheduled_at__isnull=True).exclude(scheduled_at='')

    if exclude_booking_id:
        qs = qs.exclude(id=exclude_booking_id)

    for b in qs:
        b_start = parse_iso_datetime(b.scheduled_at)
        if b_start:
            b_end = b_start + timedelta(minutes=b.duration_minutes or 30)
            if start_dt < b_end and end_dt > b_start:
                return True, b
    return False, None


def generate_available_slots_for_date(mentor_id, target_date, duration_minutes=60, step_minutes=30):
    """
    Generates all available slots for this mentor on target_date, hiding slots already booked by others.
    """
    now = datetime.now()
    if target_date < now.date():
        return {
            'slots': [],
            'day_available': False,
            'message': 'Cannot view slots for a past date'
        }

    js_day = (target_date.weekday() + 1) % 7
    windows = get_mentor_availability_windows(mentor_id, js_day)

    if not windows:
        return {
            'slots': [],
            'day_available': False,
            'message': 'Mentor has no availability scheduled on this day.'
        }

    booked_windows = get_mentor_active_booked_windows(mentor_id, date_obj=target_date)

    available_slots = []
    buffer_now = now + timedelta(minutes=15)

    for w_start_str, w_end_str in windows:
        try:
            w_start_time = datetime.strptime(w_start_str[:5], '%H:%M').time()
            w_end_time = datetime.strptime(w_end_str[:5], '%H:%M').time()
        except ValueError:
            continue

        current_dt = datetime.combine(target_date, w_start_time)
        window_end_dt = datetime.combine(target_date, w_end_time)

        while current_dt + timedelta(minutes=duration_minutes) <= window_end_dt:
            slot_start = current_dt
            slot_end = current_dt + timedelta(minutes=duration_minutes)

            # Advance for next iteration
            current_dt += timedelta(minutes=step_minutes)

            # Exclude past times if today
            if target_date == now.date() and slot_start < buffer_now:
                continue

            # Check overlap with any active booked window
            overlap = any(slot_start < b_end and slot_end > b_start for b_start, b_end in booked_windows)
            if overlap:
                # DO NOT SHOW: already booked by another learner!
                continue

            available_slots.append({
                'time': slot_start.strftime('%H:%M'),
                'label': f"{slot_start.strftime('%I:%M %p')} - {slot_end.strftime('%I:%M %p')}",
                'start_time': slot_start.strftime('%H:%M'),
                'end_time': slot_end.strftime('%H:%M'),
                'start_formatted': slot_start.strftime('%I:%M %p'),
                'end_formatted': slot_end.strftime('%I:%M %p'),
                'iso': slot_start.isoformat(),
                'date': target_date.strftime('%Y-%m-%d'),
            })

    return {
        'slots': available_slots,
        'day_available': True,
        'total_available': len(available_slots),
        'booked_count': len(booked_windows),
    }


def get_mentor_available_dates(mentor_id, days_ahead=14, duration_minutes=60, step_minutes=30):
    """
    Scans upcoming days starting from today and returns a list of date descriptors
    on which the mentor has at least ONE available, unbooked slot.
    Days where the mentor has no scheduled hours or where all slots are booked/past
    are strictly excluded (never returned).
    """
    now = datetime.now()
    start_date = now.date()

    has_any = MentorAvailability.objects.filter(user_id=mentor_id).exists()
    avail_by_day = {}
    if has_any:
        for r in MentorAvailability.objects.filter(user_id=mentor_id):
            avail_by_day.setdefault(r.day_of_week, []).append((r.start_time[:5], r.end_time[:5]))

    booked_windows = get_mentor_active_booked_windows(mentor_id)
    buffer_now = now + timedelta(minutes=15)

    available_dates = []
    # Scan up to 45 calendar days to find at least days_ahead available dates
    max_scan_days = 45

    for offset in range(max_scan_days):
        target_date = start_date + timedelta(days=offset)
        js_day = (target_date.weekday() + 1) % 7

        if not has_any:
            windows = [("09:00", "21:00")]
        else:
            windows = avail_by_day.get(js_day, [])

        if not windows:
            # Mentor is not available on this day of the week -> DO NOT SHOW
            continue

        # Check if there is at least one open slot on this day
        free_slots_count = 0
        for w_start_str, w_end_str in windows:
            try:
                w_start_time = datetime.strptime(w_start_str[:5], '%H:%M').time()
                w_end_time = datetime.strptime(w_end_str[:5], '%H:%M').time()
            except ValueError:
                continue

            current_dt = datetime.combine(target_date, w_start_time)
            window_end_dt = datetime.combine(target_date, w_end_time)

            while current_dt + timedelta(minutes=duration_minutes) <= window_end_dt:
                slot_start = current_dt
                slot_end = current_dt + timedelta(minutes=duration_minutes)
                current_dt += timedelta(minutes=step_minutes)

                if target_date == now.date() and slot_start < buffer_now:
                    continue

                overlap = any(slot_start < b_end and slot_end > b_start for b_start, b_end in booked_windows)
                if overlap:
                    continue

                free_slots_count += 1

        if free_slots_count > 0:
            is_today = (target_date == now.date())
            is_tomorrow = (target_date == now.date() + timedelta(days=1))
            day_name = 'Today' if is_today else ('Tomorrow' if is_tomorrow else target_date.strftime('%a'))

            available_dates.append({
                'date': target_date.strftime('%Y-%m-%d'),
                'day_name': day_name,
                'day_num': target_date.day,
                'month_name': target_date.strftime('%b'),
                'weekday': target_date.strftime('%A'),
                'is_today': is_today,
                'is_tomorrow': is_tomorrow,
                'slots_count': free_slots_count,
            })

            if len(available_dates) >= days_ahead:
                break

    return available_dates
