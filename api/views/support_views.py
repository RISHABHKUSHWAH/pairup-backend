import json
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework import status
from ..models import PlatformSetting
from ..helpers import success_response, error_response

DEFAULT_TICKETS = [
    {
        "id": "SUP-2088",
        "user_id": 3,
        "user_name": "Sarah Connor",
        "user_email": "sarah@example.com",
        "user_role": "learner",
        "subject": "Dispute on unfulfilled React Native code review contract",
        "category": "Billing & Escrow",
        "priority": "Urgent",
        "status": "Open",
        "date": "2026-09-13",
        "created_at": "2026-09-13T14:30:00Z",
        "description": "I booked a 90-minute session for React Native navigation debugging. The mentor disconnected after 15 minutes due to power outage and has not rescheduled. I would like an escrow refund or slot reschedule.",
        "response": "Hi Sarah, we are checking the session disconnect logs with our WebRTC monitor. We will freeze escrow release until resolved.",
        "admin_notes": "WebRTC logs confirm session ended abruptly at 14m22s. Waiting for mentor response before releasing escrow.",
        "history": [
            {"by": "Sarah Connor (Learner)", "text": "Submitted support inquiry regarding disconnected session.", "time": "2026-09-13 14:30"},
            {"by": "Admin Team", "text": "Status changed to Open. Escrow flagged for temporary hold.", "time": "2026-09-13 14:45"}
        ]
    },
    {
        "id": "SUP-2041",
        "user_id": 2,
        "user_name": "Alex Rivera",
        "user_email": "alex@example.com",
        "user_role": "mentor",
        "subject": "Inquiry regarding Escrow payment clearance timeline",
        "category": "Billing & Escrow",
        "priority": "Normal",
        "status": "In Review",
        "date": "2026-09-11",
        "created_at": "2026-09-11T09:15:00Z",
        "description": "Completed my pair programming session and learner marked it done. When will payout reflect in wallet?",
        "response": "Our automated payout engine processes completed escrow releases within 24 hours. Your payout is currently queued for disbursement.",
        "admin_notes": "Booking #24 approved. Payout scheduled for batch clearance today at 18:00 IST.",
        "history": [
            {"by": "Alex Rivera (Mentor)", "text": "Asked about payout reflection timeframe.", "time": "2026-09-11 09:15"},
            {"by": "Admin Team", "text": "Replied with clearance policy details. Marked In Review.", "time": "2026-09-11 11:20"}
        ]
    },
    {
        "id": "SUP-2105",
        "user_id": 5,
        "user_name": "Priya Patel",
        "user_email": "priya@example.com",
        "user_role": "mentor",
        "subject": "Bank account IFSC verification pending for over 48 hours",
        "category": "Account & Verification",
        "priority": "High",
        "status": "In Review",
        "date": "2026-09-12",
        "created_at": "2026-09-12T16:40:00Z",
        "description": "I submitted my HDFC bank account passbook for payout verification two days ago, but status still says Pending Verification.",
        "response": "Our compliance team is verifying the IFSC code and account holder name match. Review should complete today.",
        "admin_notes": "Passbook name matches profile name. Sent to banking partner API for penny drop validation.",
        "history": [
            {"by": "Priya Patel (Mentor)", "text": "Requested status update on bank verification.", "time": "2026-09-12 16:40"}
        ]
    },
    {
        "id": "SUP-2112",
        "user_id": 6,
        "user_name": "Michael Zhang",
        "user_email": "michael@example.com",
        "user_role": "learner",
        "subject": "Monaco editor syntax highlighting for Rust/Wasm files",
        "category": "Technical Issue",
        "priority": "Normal",
        "status": "Open",
        "date": "2026-09-14",
        "created_at": "2026-09-14T01:10:00Z",
        "description": "When pairing on Rust code (.rs files), the editor defaults to plain text mode without rust-analyzer hints.",
        "response": "",
        "admin_notes": "",
        "history": [
            {"by": "Michael Zhang (Learner)", "text": "Reported editor syntax mode bug for Rust files.", "time": "2026-09-14 01:10"}
        ]
    },
    {
        "id": "SUP-1980",
        "user_id": 4,
        "user_name": "David Chen",
        "user_email": "david@example.com",
        "user_role": "mentor",
        "subject": "Microphone permission issue on Safari macOS",
        "category": "Live Sessions",
        "priority": "Low",
        "status": "Resolved",
        "date": "2026-09-06",
        "created_at": "2026-09-06T11:00:00Z",
        "description": "Safari prompted for permission but WebRTC audio stayed muted during pairing.",
        "response": "Resolved in platform update v2.4 with fallback audio constraints and WebRTC automatic reconnect handlers.",
        "admin_notes": "Tested on Safari 17.5. Audio track binds properly now.",
        "history": [
            {"by": "David Chen (Mentor)", "text": "Ticket submitted.", "time": "2026-09-06 11:00"},
            {"by": "Admin Team", "text": "Resolved and deployed patch.", "time": "2026-09-07 14:00"}
        ]
    },
    {
        "id": "SUP-1950",
        "user_id": 8,
        "user_name": "Anita Desai",
        "user_email": "anita@example.com",
        "user_role": "mentor",
        "subject": "How to request 1099/TDS tax invoice for platform fees",
        "category": "Billing & Escrow",
        "priority": "Low",
        "status": "Resolved",
        "date": "2026-08-28",
        "created_at": "2026-08-28T10:20:00Z",
        "description": "Need tax deduction certificate for earnings in Q3.",
        "response": "Tax summary reports can now be generated directly from Admin/Earnings -> Download Tax Invoices.",
        "admin_notes": "Sent PDF receipt copy to user email as well.",
        "history": [
            {"by": "Anita Desai (Mentor)", "text": "Ticket opened.", "time": "2026-08-28 10:20"},
            {"by": "Admin Team", "text": "Provided PDF download link and marked resolved.", "time": "2026-08-28 15:30"}
        ]
    }
]

def _get_stored_tickets():
    try:
        setting, _ = PlatformSetting.objects.get_or_create(
            setting_key="support_tickets",
            defaults={"setting_value": json.dumps(DEFAULT_TICKETS)}
        )
        val = (setting.setting_value or "").strip()
        if not val or val == "[]":
            setting.setting_value = json.dumps(DEFAULT_TICKETS)
            setting.save()
            return list(DEFAULT_TICKETS)
        parsed = json.loads(val)
        if isinstance(parsed, list):
            return parsed
        return list(DEFAULT_TICKETS)
    except Exception:
        return list(DEFAULT_TICKETS)

def _save_stored_tickets(tickets_list):
    try:
        PlatformSetting.objects.update_or_create(
            setting_key="support_tickets",
            defaults={"setting_value": json.dumps(tickets_list)}
        )
    except Exception:
        pass

@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def list_or_create_tickets(request):
    if request.method == "GET":
        tickets = _get_stored_tickets()
        return success_response(tickets)

    data = request.data or {}
    tickets = _get_stored_tickets()

    now_iso = timezone.now().isoformat()
    today_str = now_iso.split("T")[0]

    new_id = data.get("id") or f"SUP-{1000 + (len(tickets) * 17 + 3) % 9000}"
    new_ticket = {
        "id": new_id,
        "user_id": data.get("user_id") or "guest",
        "user_name": data.get("user_name") or "Anonymous User",
        "user_email": data.get("user_email") or "user@example.com",
        "user_role": data.get("user_role") or "learner",
        "subject": data.get("subject") or "Support Inquiry",
        "category": data.get("category") or "General Inquiry",
        "priority": data.get("priority") or "Normal",
        "status": data.get("status") or "Open",
        "date": data.get("date") or today_str,
        "created_at": data.get("created_at") or now_iso,
        "description": data.get("description") or "",
        "response": data.get("response") or "",
        "admin_notes": data.get("admin_notes") or "",
        "history": data.get("history") or [
            {
                "by": f"{data.get('user_name') or 'User'} ({data.get('user_role') or 'user'})",
                "text": "Ticket opened.",
                "time": now_iso.replace("T", " ")[:16]
            }
        ],
    }
    # Preserve any additional fields (resolved_at, updated_at, etc.)
    for k, v in data.items():
        if k not in new_ticket and v is not None:
            new_ticket[k] = v

    idx = next((i for i, t in enumerate(tickets) if t.get("id") == new_id), -1)
    if idx != -1:
        tickets[idx] = {**tickets[idx], **new_ticket}
    else:
        tickets.insert(0, new_ticket)

    _save_stored_tickets(tickets)
    return success_response(new_ticket, status_code=status.HTTP_201_CREATED)

@api_view(["PUT", "DELETE"])
@permission_classes([AllowAny])
def ticket_detail(request, ticket_id):
    tickets = _get_stored_tickets()
    idx = next((i for i, t in enumerate(tickets) if t.get("id") == ticket_id), -1)

    if request.method == "DELETE":
        if idx != -1:
            tickets.pop(idx)
            _save_stored_tickets(tickets)
        return success_response({"message": f"Ticket {ticket_id} deleted"})

    data = request.data or {}
    if idx == -1:
        target = {"id": ticket_id, **data}
        tickets.insert(0, target)
    else:
        target = {**tickets[idx], **data}
        tickets[idx] = target

    _save_stored_tickets(tickets)
    return success_response(target)
