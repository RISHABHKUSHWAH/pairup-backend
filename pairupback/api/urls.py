from django.urls import path
from .views import (
    auth_views,
    mentor_views,
    section_views,
    booking_views,
    chat_views,
    review_views,
    problem_views,
    admin_views,
    superadmin_views,
    page_views,
    contact_views,
    notification_views,
    livekit_views,
    contract_views,
    support_views,
)

urlpatterns = [
    # Auth
    path('auth/register', auth_views.register, name='auth-register'),
    path('auth/login', auth_views.login, name='auth-login'),
    path('auth/me', auth_views.me, name='auth-me'),
    path('auth/switch-role', auth_views.switch_role, name='auth-switch-role'),
    path('platform/config', auth_views.platform_config, name='platform-config'),

    # Mentors
    path('mentors', mentor_views.list_mentors, name='mentors-list'),
    path('mentors/<int:mentor_id>', mentor_views.mentor_detail, name='mentor-detail'),
    path('mentors/<int:mentor_id>/available-dates', mentor_views.get_available_dates, name='mentor-available-dates'),
    path('mentors/<int:mentor_id>/available-slots', mentor_views.get_available_slots, name='mentor-available-slots'),
    path('mentors/<int:mentor_id>/booked-slots', mentor_views.get_booked_slots, name='mentor-booked-slots'),
    path('mentors/me', mentor_views.update_own_profile, name='mentor-me-update'),
    path('mentors/me/online-status', mentor_views.set_online_status, name='mentor-me-online-status'),
    path('mentors/me/photo', mentor_views.upload_photo, name='mentor-me-photo'),
    path('mentors/apply', mentor_views.apply_as_mentor, name='mentor-apply'),

    # Mentor Sections
    path('mentors/me/experience', section_views.add_experience, name='mentor-add-experience'),
    path('mentors/me/experience/<int:item_id>', section_views.delete_experience, name='mentor-delete-experience'),
    path('mentors/me/projects', section_views.add_project, name='mentor-add-project'),
    path('mentors/me/projects/<int:item_id>', section_views.delete_project, name='mentor-delete-project'),
    path('mentors/me/education', section_views.add_education, name='mentor-add-education'),
    path('mentors/me/education/<int:item_id>', section_views.delete_education, name='mentor-delete-education'),
    path('mentors/me/certifications', section_views.add_certification, name='mentor-add-certification'),
    path('mentors/me/certifications/<int:item_id>', section_views.delete_certification, name='mentor-delete-certification'),
    path('mentors/me/awards', section_views.add_award, name='mentor-add-award'),
    path('mentors/me/awards/<int:item_id>', section_views.delete_award, name='mentor-delete-award'),
    path('mentors/me/availability', section_views.set_availability, name='mentor-set-availability'),

    # Bookings
    path('bookings', booking_views.bookings_endpoint, name='bookings'),
    path('bookings/<int:booking_id>/accept', booking_views.accept_booking, name='booking-accept'),
    path('bookings/<int:booking_id>/pay', booking_views.pay_booking, name='booking-pay'),
    path('bookings/<int:booking_id>/complete', booking_views.complete_booking, name='booking-complete'),
    path('bookings/<int:booking_id>/dispute', booking_views.dispute_booking, name='booking-dispute'),
    path('bookings/<int:booking_id>/cancel', booking_views.cancel_booking, name='booking-cancel'),
    path('bookings/<int:booking_id>', booking_views.session_detail, name='booking-detail'),
    path('bookings/<int:booking_id>/notes', booking_views.session_notes, name='booking-notes'),
    path('bookings/<int:booking_id>/livekit-token', livekit_views.generate_livekit_token, name='booking-livekit-token'),
    path('bookings/<int:booking_id>/files', livekit_views.session_files, name='booking-session-files'),
    path('bookings/<int:booking_id>/summary', livekit_views.session_summary, name='booking-session-summary'),
    path('bookings/<int:booking_id>/signal', livekit_views.session_signal, name='booking-session-signal'),

    # Contracts & Multi-Session Mentorship
    path('contracts', contract_views.list_or_create_contracts, name='contracts-list-create'),
    path('contracts/<int:contract_id>', contract_views.contract_detail, name='contract-detail'),
    path('contracts/<int:contract_id>/pay', contract_views.pay_contract, name='contract-pay'),
    path('contracts/<int:contract_id>/complete-by-mentor', contract_views.complete_contract_by_mentor, name='contract-complete-by-mentor'),
    path('contracts/<int:contract_id>/approve', contract_views.approve_contract, name='contract-approve'),
    path('contracts/<int:contract_id>/dispute', contract_views.dispute_contract, name='contract-dispute'),
    path('contracts/<int:contract_id>/decline', contract_views.decline_contract, name='contract-decline'),
    path('contracts/<int:contract_id>/sessions/<int:session_id>/schedule', contract_views.schedule_contract_session, name='contract-session-schedule'),
    path('contracts/<int:contract_id>/admin-resolve', contract_views.admin_resolve_contract, name='contract-admin-resolve'),


    # Payments personal
    path('payments/mine', booking_views.payments_mine, name='payments-mine'),

    # Chat
    path('messages', chat_views.messages_endpoint, name='messages'),
    path('messages/conversations', chat_views.conversations, name='messages-conversations'),
    path('messages/clear', chat_views.clear_conversation, name='messages-clear'),
    path('messages/<int:message_id>', chat_views.delete_message, name='messages-delete-message'),
    path('messages/upload', chat_views.upload_chat_attachment, name='messages-upload'),
    path('messages/attachment/download', chat_views.download_chat_attachment, name='messages-download-attachment'),
    path('messages/attachment/view', chat_views.view_chat_attachment, name='messages-view-attachment'),

    # Reviews
    path('reviews', review_views.reviews_endpoint, name='reviews'),
    path('reviews/mine', review_views.my_reviews, name='reviews-mine'),

    # Problems
    path('problems', problem_views.problems_endpoint, name='problems'),
    path('problems/mine', problem_views.my_problems, name='problems-mine'),
    path('problems/<int:problem_id>/close', problem_views.close_problem, name='problem-close'),
    path('problems/<int:problem_id>', problem_views.delete_problem, name='problem-delete'),
    path('problems/<int:problem_id>/proposals', problem_views.problem_proposals_endpoint, name='problem-proposals'),
    path('problems/<int:problem_id>/proposals/<int:proposal_id>/accept', problem_views.accept_proposal, name='problem-proposal-accept'),
    path('problems/<int:problem_id>/proposals/<int:proposal_id>/reject', problem_views.reject_proposal, name='problem-proposal-reject'),
    path('problems/<int:problem_id>/proposals/<int:proposal_id>/counter', problem_views.counter_proposal, name='problem-proposal-counter'),
    path('problems/<int:problem_id>/proposals/<int:proposal_id>/accept-counter', problem_views.accept_counter_offer, name='problem-proposal-accept-counter'),
    path('proposals/mine', problem_views.my_proposals, name='proposals-mine'),
    path('proposals/<int:proposal_id>', problem_views.withdraw_proposal, name='proposal-withdraw'),

    # Admin
    path('admin/stats', admin_views.stats, name='admin-stats'),
    path('admin/users', admin_views.list_users, name='admin-users'),
    path('admin/all-users', admin_views.list_all_users, name='admin-all-users'),
    path('admin/users/<int:user_id>/switch-role', admin_views.admin_switch_user_role, name='admin-user-switch-role'),
    path('admin/users/<int:user_id>/toggle-suspend', admin_views.admin_toggle_suspend_user, name='admin-user-toggle-suspend'),
    path('admin/payments', admin_views.list_payments, name='admin-payments'),
    path('admin/bookings', admin_views.list_bookings, name='admin-bookings'),
    path('admin/mentors/pending', admin_views.pending_mentors, name='admin-mentors-pending'),
    path('admin/mentors/<int:mentor_id>/approve', admin_views.approve_mentor, name='admin-mentor-approve'),
    path('admin/mentors/<int:mentor_id>/reject', admin_views.reject_mentor, name='admin-mentor-reject'),
    path('admin/disputes', admin_views.list_disputes, name='admin-disputes'),
    path('admin/disputes/<int:booking_id>/resolve', admin_views.resolve_dispute, name='admin-dispute-resolve'),
    path('admin/payouts', admin_views.payouts, name='admin-payouts'),
    path('admin/settings', admin_views.admin_settings, name='admin-settings'),
    path('admin/reviews', admin_views.list_reviews, name='admin-reviews'),
    path('admin/reviews/<int:review_id>', admin_views.delete_review, name='admin-review-delete'),
    path('admin/problems', admin_views.admin_problems, name='admin-problems'),
    path('admin/problems/<int:problem_id>/close', admin_views.admin_close_problem, name='admin-problem-close'),
    path('admin/refunds', admin_views.list_refunds, name='admin-refunds'),
    path('admin/notifications', admin_views.notifications, name='admin-notifications'),
    path('admin/audit-logs', admin_views.audit_logs, name='admin-audit-logs'),
    path('admin/contact-messages', admin_views.contact_messages, name='admin-contact-messages'),
    path('admin/pages', page_views.list_pages, name='admin-pages-list'),
    path('admin/pages/<slug:slug>', page_views.update_page, name='admin-page-update'),

    # Superadmin
    path('superadmin/admins', superadmin_views.list_admins, name='superadmin-admins'),
    path('superadmin/search-users', superadmin_views.search_users, name='superadmin-search-users'),
    path('superadmin/admins/<int:user_id>/promote', superadmin_views.promote_admin, name='superadmin-promote'),
    path('superadmin/admins/<int:user_id>/revoke', superadmin_views.revoke_admin, name='superadmin-revoke'),

    # Site Pages
    path('pages/<slug:slug>', page_views.get_page, name='page-get'),

    # Contact
    path('contact', contact_views.submit_contact, name='contact-submit'),

    # User Notifications (Mentors & Learners)
    path('notifications', notification_views.list_notifications, name='notifications-list'),
    path('notifications/<int:notification_id>/read', notification_views.mark_read, name='notification-mark-read'),
    path('notifications/mark-all-read', notification_views.mark_all_read, name='notifications-mark-all-read'),
    path('notifications/clear', notification_views.clear_notifications, name='notifications-clear'),

    # Support Requests & Inquiries
    path('support/tickets', support_views.list_or_create_tickets, name='support-tickets'),
    path('support/tickets/<str:ticket_id>', support_views.ticket_detail, name='support-ticket-detail'),
]
