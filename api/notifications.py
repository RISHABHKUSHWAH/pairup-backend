import logging
from .models import Notification, User, MentorProfile

logger = logging.getLogger(__name__)


def create_notification(user, title, message, notification_type='system', link=''):
    """
    Safely creates a Notification record for a user.
    Silently logs any exceptions so notification errors do not abort core operations.
    """
    if not user:
        return None
    try:
        return Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link or '',
            is_read=False,
        )
    except Exception as e:
        logger.warning(f"Could not create notification for user {getattr(user, 'id', None)}: {e}")
        return None


def notify_matching_mentors(problem):
    """
    Alerts active approved mentors when a new problem request is posted.
    Prioritizes mentors whose listed skills match the problem skills.
    """
    try:
        problem_skills = [s.strip().lower() for s in (problem.skills or '').split(',') if s.strip()]
        
        # Notify the learner who posted it as confirmation
        create_notification(
            user=problem.learner,
            title='Problem Request Published 🚀',
            message=f"Your problem '{problem.title}' is now live. Mentors can submit proposals.",
            notification_type='problem',
            link='/learner/my-problems',
        )

        # Find approved mentors
        mentors = MentorProfile.objects.select_related('user').filter(
            approval_status='approved',
            user__is_active=True
        ).exclude(user=problem.learner)

        budget_str = f" (Budget: ₹{problem.budget:,.0f})" if problem.budget else ""
        notified_count = 0
        learner_name = problem.learner.name or (problem.learner.email.split('@')[0] if problem.learner.email else 'A learner')

        for profile in mentors:
            mentor_skills = [s.strip().lower() for s in (profile.skills or '').split(',') if s.strip()]
            
            # Check overlap if skills are provided
            matches = False
            if problem_skills:
                matches = any(ps in mentor_skills or any(ps in ms for ms in mentor_skills) for ps in problem_skills)
            else:
                matches = True

            if matches and notified_count < 15:
                create_notification(
                    user=profile.user,
                    title='New Problem Matching Your Skills 💡',
                    message=f"{learner_name} posted: '{problem.title}'{budget_str}.",
                    notification_type='problem',
                    link='/mentor/explore-problems',
                )
                notified_count += 1
    except Exception as e:
        logger.warning(f"Error in notify_matching_mentors: {e}")


def notify_proposal_submitted(proposal):
    """
    Alerts the learner that a mentor has submitted a proposal on their problem.
    """
    try:
        problem = proposal.problem
        mentor = proposal.mentor
        create_notification(
            user=problem.learner,
            title='New Proposal Received 📩',
            message=f"{mentor.name} submitted a ₹{proposal.proposed_price:,.0f} proposal on '{problem.title}'.",
            notification_type='proposal',
            link='/learner/my-problems',
        )
        create_notification(
            user=mentor,
            title='Proposal Submitted ✅',
            message=f"Your ₹{proposal.proposed_price:,.0f} proposal for '{problem.title}' was sent to {problem.learner.name}.",
            notification_type='proposal',
            link='/mentor/my-proposals',
        )
    except Exception as e:
        logger.warning(f"Error in notify_proposal_submitted: {e}")


def notify_proposal_accepted(proposal, booking):
    """
    Alerts the chosen mentor that their proposal was accepted and booking was created.
    Also alerts other mentors whose proposals were declined.
    """
    try:
        problem = proposal.problem
        learner = booking.learner
        mentor = proposal.mentor

        # Notify winning mentor
        create_notification(
            user=mentor,
            title='Proposal Accepted! 🎉',
            message=f"Great news! {learner.name} accepted your proposal for '{problem.title}'. Session #{booking.id} created.",
            notification_type='proposal',
            link='/mentor/sessions',
        )

        # Notify learner
        create_notification(
            user=learner,
            title='Session Confirmed 🤝',
            message=f"You accepted {mentor.name}'s proposal for '{problem.title}'. Proceed to payment to fund escrow.",
            notification_type='session',
            link='/learner/sessions',
        )

        # Notify other applicants
        declined_proposals = problem.proposals.exclude(id=proposal.id).select_related('mentor')
        for dec in declined_proposals:
            create_notification(
                user=dec.mentor,
                title='Proposal Status Update',
                message=f"Another proposal was selected for '{problem.title}'. Thank you for submitting!",
                notification_type='proposal',
                link='/mentor/my-proposals',
            )
    except Exception as e:
        logger.warning(f"Error in notify_proposal_accepted: {e}")


def notify_booking_created(booking):
    """
    Alerts mentor when learner directly requests a 1-on-1 session.
    """
    try:
        create_notification(
            user=booking.mentor,
            title='New Session Request 📅',
            message=f"{booking.learner.name} requested a {booking.duration_minutes}-min session on '{booking.topic}' (${booking.price:,.0f}).",
            notification_type='session',
            link='/mentor/sessions',
        )
        create_notification(
            user=booking.learner,
            title='Session Requested ⏳',
            message=f"Your request for '{booking.topic}' was sent to {booking.mentor.name}. Waiting for mentor approval.",
            notification_type='session',
            link='/learner/sessions',
        )
    except Exception as e:
        logger.warning(f"Error in notify_booking_created: {e}")


def notify_booking_accepted(booking):
    """
    Alerts learner when mentor accepts their requested session.
    """
    try:
        create_notification(
            user=booking.learner,
            title='Session Request Accepted! 🚀',
            message=f"{booking.mentor.name} accepted your session on '{booking.topic}'. Please confirm with payment.",
            notification_type='session',
            link='/learner/sessions',
        )
    except Exception as e:
        logger.warning(f"Error in notify_booking_accepted: {e}")


def notify_payment_held(booking, payment):
    """
    Alerts mentor and learner that escrow payment is funded and session is confirmed.
    """
    try:
        create_notification(
            user=booking.mentor,
            title='Payment Locked in Escrow 🔒',
            message=f"{booking.learner.name} paid ${payment.amount:,.0f} into escrow for '{booking.topic}'. Session is confirmed!",
            notification_type='payment',
            link='/mentor/sessions',
        )
        create_notification(
            user=booking.learner,
            title='Payment Secured in Escrow 🛡️',
            message=f"${payment.amount:,.0f} is held in escrow for '{booking.topic}'. Funds will only release after session completion.",
            notification_type='payment',
            link='/learner/sessions',
        )
    except Exception as e:
        logger.warning(f"Error in notify_payment_held: {e}")


def notify_session_completed(booking, payment=None):
    """
    Alerts mentor that escrow funds are released, and prompts learner to rate mentor.
    """
    try:
        amount = payment.amount - payment.platform_fee if payment else booking.price
        create_notification(
            user=booking.mentor,
            title='Escrow Funds Released! 💰',
            message=f"${amount:,.0f} has been released to your balance for completed session '{booking.topic}'.",
            notification_type='payment',
            link='/mentor/earnings',
        )
        create_notification(
            user=booking.learner,
            title='Session Complete — Leave a Review ⭐',
            message=f"Your session '{booking.topic}' with {booking.mentor.name} is complete. Share your feedback!",
            notification_type='session',
            link='/learner/reviews',
        )
    except Exception as e:
        logger.warning(f"Error in notify_session_completed: {e}")


def notify_review_created(review):
    """
    Alerts mentor that a learner submitted a rating and review.
    """
    try:
        snippet = f": \"{review.comment[:60]}...\"" if review.comment else ""
        create_notification(
            user=review.mentor,
            title=f"New {review.rating}★ Review Received! ⭐",
            message=f"{review.learner.name} rated you {review.rating} out of 5 stars{snippet}",
            notification_type='review',
            link='/mentor/reviews',
        )
    except Exception as e:
        logger.warning(f"Error in notify_review_created: {e}")


def notify_chat_message(message):
    """
    Alerts recipient of a new direct chat message.
    """
    try:
        sender_name = message.sender.name
        body_snippet = message.body[:70] + ('...' if len(message.body) > 70 else '')
        create_notification(
            user=message.receiver,
            title=f"New message from {sender_name} 💬",
            message=body_snippet,
            notification_type='message',
            link=f"/messages?with={message.sender_id}",
        )
    except Exception as e:
        logger.warning(f"Error in notify_chat_message: {e}")


def notify_dispute_raised(booking, reason, disputed_by):
    """
    Alerts the counterparty when a dispute is opened on a session.
    """
    try:
        other_user = booking.mentor if disputed_by == booking.learner else booking.learner
        create_notification(
            user=other_user,
            title='Session Dispute Opened ⚠️',
            message=f"A dispute was raised for '{booking.topic}'. Reason: {reason}. Our support team will review it.",
            notification_type='session',
            link='/sessions',
        )
    except Exception as e:
        logger.warning(f"Error in notify_dispute_raised: {e}")


def notify_dispute_resolved(booking, resolution):
    """
    Alerts both parties when admin resolves a dispute.
    """
    try:
        if resolution == 'release':
            create_notification(
                user=booking.mentor,
                title='Dispute Resolved — Funds Released 💰',
                message=f"The dispute for session '{booking.topic}' was resolved. Funds were released to your balance.",
                notification_type='payment',
                link='/mentor/earnings',
            )
            create_notification(
                user=booking.learner,
                title='Dispute Resolved',
                message=f"The dispute for session '{booking.topic}' has been closed.",
                notification_type='session',
                link='/learner/sessions',
            )
        else:
            create_notification(
                user=booking.learner,
                title='Dispute Resolved — Refund Approved 💳',
                message=f"The dispute for session '{booking.topic}' was resolved in your favor. Your payment was refunded.",
                notification_type='payment',
                link='/learner/payments',
            )
            create_notification(
                user=booking.mentor,
                title='Dispute Resolved — Session Refunded',
                message=f"The dispute for session '{booking.topic}' was closed and refunded to the learner.",
                notification_type='session',
                link='/mentor/sessions',
            )
    except Exception as e:
        logger.warning(f"Error in notify_dispute_resolved: {e}")


def notify_mentor_approval(mentor_profile, approved):
    """
    Alerts mentor when their application is approved or rejected by an admin.
    """
    try:
        if approved:
            create_notification(
                user=mentor_profile.user,
                title='Mentor Profile Approved! 🎉',
                message='Congratulations! Your mentor profile has been verified and approved. You are now discoverable in search.',
                notification_type='system',
                link='/mentor/profile',
            )
        else:
            create_notification(
                user=mentor_profile.user,
                title='Mentor Application Update',
                message='Your mentor application was reviewed. Please update your profile details and reapply.',
                notification_type='system',
                link='/mentor/profile',
            )
    except Exception as e:
        logger.warning(f"Error in notify_mentor_approval: {e}")


def notify_contract_proposed(contract):
    """
    Alerts user when a multi-session contract is proposed.
    """
    try:
        recipient = contract.learner if contract.created_by_id == contract.mentor_id else contract.mentor
        sender_name = contract.created_by.name
        create_notification(
            user=recipient,
            title='New Mentorship Contract Proposed 📄',
            message=f"{sender_name} proposed a {contract.total_sessions}-session contract '{contract.title}' for ₹{contract.total_price:,.0f}.",
            notification_type='proposal',
            link=f"/contracts/{contract.id}",
        )
    except Exception as e:
        logger.warning(f"Error in notify_contract_proposed: {e}")


def notify_contract_paid(contract):
    """
    Alerts mentor when learner accepts & funds contract escrow.
    """
    try:
        create_notification(
            user=contract.mentor,
            title='Contract Funded & Active! 🚀',
            message=f"{contract.learner.name} paid ₹{contract.total_price:,.0f} into escrow for contract '{contract.title}'. All {contract.total_sessions} sessions are now ready.",
            notification_type='payment',
            link=f"/contracts/{contract.id}",
        )
        create_notification(
            user=contract.learner,
            title='Contract Activated (Escrow Protected) 🛡️',
            message=f"₹{contract.total_price:,.0f} is held in platform escrow for '{contract.title}'. Your {contract.total_sessions} milestone sessions are ready to conduct.",
            notification_type='payment',
            link=f"/contracts/{contract.id}",
        )
    except Exception as e:
        logger.warning(f"Error in notify_contract_paid: {e}")


def notify_contract_completed_by_mentor(contract):
    """
    Alerts learner when mentor completes all sessions and submits for review.
    """
    try:
        create_notification(
            user=contract.learner,
            title='Contract Ready for Review 🎓',
            message=f"{contract.mentor.name} has conducted all {contract.total_sessions} sessions for '{contract.title}'. Please review and approve to release payment.",
            notification_type='session',
            link=f"/contracts/{contract.id}",
        )
    except Exception as e:
        logger.warning(f"Error in notify_contract_completed_by_mentor: {e}")


def notify_contract_approved(contract):
    """
    Alerts mentor when learner approves contract and releases escrow payout.
    """
    try:
        create_notification(
            user=contract.mentor,
            title='Contract Approved — Payout Released 💰',
            message=f"{contract.learner.name} approved contract '{contract.title}'. Payment of ₹{contract.total_price:,.0f} has been released to your account!",
            notification_type='payment',
            link=f"/contracts/{contract.id}",
        )
    except Exception as e:
        logger.warning(f"Error in notify_contract_approved: {e}")


def notify_contract_disputed(contract, reason, raised_by):
    """
    Alerts participants and admin when contract is disputed.
    """
    try:
        other_party = contract.learner if raised_by.id == contract.mentor_id else contract.mentor
        create_notification(
            user=other_party,
            title='Contract Disputed ⚠️',
            message=f"{raised_by.name} raised a dispute on contract '{contract.title}': \"{reason}\". Platform administrators are reviewing.",
            notification_type='session',
            link=f"/contracts/{contract.id}",
        )
        # Notify admins
        admins = User.objects.filter(role__in=['admin', 'superadmin'], is_active=True)
        for adm in admins[:10]:
            create_notification(
                user=adm,
                title='[Admin] Contract Dispute Raised ⚠️',
                message=f"Dispute raised on Contract #{contract.id} ({contract.title}) by {raised_by.name}: \"{reason}\"",
                notification_type='system',
                link=f"/admin/disputes",
            )
    except Exception as e:
        logger.warning(f"Error in notify_contract_disputed: {e}")

