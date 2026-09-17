from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from api.models import (
    User, MentorProfile, Booking, Payment, Review,
    ProblemPost, ProblemProposal, PlatformSetting, SitePage, Message
)
from api.auth import generate_jwt


class PairUpApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        PlatformSetting.objects.create(setting_key='commission_percent', setting_value='10')

        # Test learner
        self.learner = User.objects.create_user(
            email='learner@example.com',
            name='Alice Learner',
            password='password123',
            role='learner'
        )
        self.learner_token = generate_jwt(self.learner)

        # Test mentor
        self.mentor = User.objects.create_user(
            email='mentor@example.com',
            name='Bob Mentor',
            password='password123',
            role='mentor'
        )
        self.mentor_profile = MentorProfile.objects.create(
            user=self.mentor,
            title='Senior Fullstack Engineer',
            company='Acme Corp',
            skills='python, django, react',
            hourly_rate=50.0,
            approval_status='approved',
            online_status=1
        )
        self.mentor_token = generate_jwt(self.mentor)

        # Test admin
        self.admin = User.objects.create_user(
            email='admin@example.com',
            name='Admin User',
            password='password123',
            role='admin',
            is_staff=True
        )
        self.admin_token = generate_jwt(self.admin)

        # Test superadmin
        self.superadmin = User.objects.create_user(
            email='super@example.com',
            name='Super Admin',
            password='password123',
            role='superadmin',
            is_staff=True,
            is_superuser=True
        )
        self.superadmin_token = generate_jwt(self.superadmin)

    # --- 1. Auth Tests ---
    def test_register_and_login(self):
        # Register new learner
        res = self.client.post('/api/auth/register', {
            'name': 'Charlie New',
            'email': 'charlie@example.com',
            'password': 'password123',
            'role': 'learner'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', res.data)
        self.assertEqual(res.data['user']['role'], 'learner')

        # Duplicate email
        res2 = self.client.post('/api/auth/register', {
            'name': 'Charlie New',
            'email': 'charlie@example.com',
            'password': 'password123',
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_409_CONFLICT)

        # Login
        res3 = self.client.post('/api/auth/login', {
            'email': 'charlie@example.com',
            'password': 'password123'
        }, format='json')
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertIn('token', res3.data)

        # Login invalid password
        res4 = self.client.post('/api/auth/login', {
            'email': 'charlie@example.com',
            'password': 'wrongpassword'
        }, format='json')
        self.assertEqual(res4.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_auth_me(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res = self.client.get('/api/auth/me')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['name'], 'Alice Learner')

        # Update me
        res2 = self.client.put('/api/auth/me', {'name': 'Alice Updated'}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.learner.refresh_from_db()
        self.assertEqual(self.learner.name, 'Alice Updated')

    # --- 2. Mentor Endpoints ---
    def test_mentors_list_and_detail(self):
        res = self.client.get('/api/mentors')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], 'Bob Mentor')
        self.assertIn('python', res.data[0]['skills'])

        # Search filter
        res_filter = self.client.get('/api/mentors?skill=python')
        self.assertEqual(len(res_filter.data), 1)

        res_none = self.client.get('/api/mentors?skill=ruby')
        self.assertEqual(len(res_none.data), 0)

        # Detail
        res_det = self.client.get(f'/api/mentors/{self.mentor.id}')
        self.assertEqual(res_det.status_code, status.HTTP_200_OK)
        self.assertEqual(res_det.data['user_id'], self.mentor.id)
        self.assertEqual(res_det.data['title'], 'Senior Fullstack Engineer')

    def test_mentor_profile_update_and_online_toggle(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.mentor_token}')
        res = self.client.put('/api/mentors/me', {
            'title': 'Principal Architect',
            'hourly_rate': 75.0,
            'skills': 'python, django, rust'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.title, 'Principal Architect')
        self.assertEqual(self.mentor_profile.hourly_rate, 75.0)

        # Toggle online status
        res2 = self.client.put('/api/mentors/me/online-status', {'online': False}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.online_status, 0)

    def test_apply_as_mentor(self):
        # Learner applies to become a mentor
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res = self.client.post('/api/mentors/apply', {
            'title': 'Junior Python Developer',
            'bio': 'Passionate about coding',
            'skills': 'python, flask',
            'hourly_rate': 25.0
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.learner.refresh_from_db()
        self.assertEqual(self.learner.role, 'mentor')
        self.assertTrue(MentorProfile.objects.filter(user=self.learner, approval_status='pending').exists())

    # --- 3. Booking & Escrow Flow ---
    def test_full_booking_escrow_flow(self):
        # 1. Learner requests session
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res = self.client.post('/api/bookings', {
            'mentor_id': self.mentor.id,
            'topic': 'Debug Django ORM queries',
            'duration_minutes': 60,
            'price': 50.0
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        booking_id = res.data['id']

        # 2. Mentor accepts booking
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.mentor_token}')
        res_accept = self.client.post(f'/api/bookings/{booking_id}/accept')
        self.assertEqual(res_accept.status_code, status.HTTP_200_OK)

        booking = Booking.objects.get(id=booking_id)
        self.assertEqual(booking.status, 'accepted')

        # 3. Learner pays (simulated escrow hold)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res_pay = self.client.post(f'/api/bookings/{booking_id}/pay')
        self.assertEqual(res_pay.status_code, status.HTTP_200_OK)

        booking.refresh_from_db()
        self.assertEqual(booking.status, 'paid')
        payment = Payment.objects.get(booking=booking)
        self.assertEqual(payment.status, 'held')
        self.assertEqual(payment.amount, 50.0)
        self.assertEqual(payment.platform_fee, 5.0)  # 10% commission

        # 4. Session notes auto-saving
        res_notes = self.client.put(f'/api/bookings/{booking_id}/notes', {'notes': 'Discussed select_related'}, format='json')
        self.assertEqual(res_notes.status_code, status.HTTP_200_OK)
        get_notes = self.client.get(f'/api/bookings/{booking_id}/notes')
        self.assertEqual(get_notes.data['notes'], 'Discussed select_related')

        # 5. Complete session -> funds released
        res_comp = self.client.post(f'/api/bookings/{booking_id}/complete')
        self.assertEqual(res_comp.status_code, status.HTTP_200_OK)

        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(booking.status, 'completed')
        self.assertEqual(payment.status, 'released')
        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.sessions_completed, 1)

        # 6. Learner leaves review
        res_rev = self.client.post('/api/reviews', {
            'booking_id': booking_id,
            'rating': 5,
            'comment': 'Awesome mentoring session!'
        }, format='json')
        self.assertEqual(res_rev.status_code, status.HTTP_201_CREATED)
        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.rating_avg, 5.0)

    def test_dispute_and_admin_resolve(self):
        # Create a paid booking directly
        booking = Booking.objects.create(
            learner=self.learner,
            mentor=self.mentor,
            topic='Unfinished session',
            price=40.0,
            status='paid'
        )
        Payment.objects.create(booking=booking, amount=40.0, platform_fee=4.0, status='held')

        # Learner disputes
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res = self.client.post(f'/api/bookings/{booking.id}/dispute', {'reason': 'Mentor was absent'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'disputed')

        # Admin resolves with refund
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        res_resolve = self.client.post(f'/api/admin/disputes/{booking.id}/resolve', {'action': 'refund'}, format='json')
        self.assertEqual(res_resolve.status_code, status.HTTP_200_OK)

        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
        self.assertEqual(booking.payments.first().status, 'refunded')

    def test_cancel_booking_learner_and_mentor(self):
        # 1. Learner creates a booking (pending)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res = self.client.post('/api/bookings', {
            'mentor_id': self.mentor.id,
            'topic': 'Cancel Test Pending',
            'duration_minutes': 60,
            'price': 50.0
        }, format='json')
        booking_id = res.data['id']

        # Learner cancels pending booking
        res_cancel = self.client.post(f'/api/bookings/{booking_id}/cancel', {'reason': 'Learner changed mind'}, format='json')
        self.assertEqual(res_cancel.status_code, status.HTTP_200_OK)
        booking = Booking.objects.get(id=booking_id)
        self.assertEqual(booking.status, 'cancelled')
        self.assertIn('Learner changed mind', booking.dispute_reason)

        # Cannot cancel again
        res_cancel_again = self.client.post(f'/api/bookings/{booking_id}/cancel', {}, format='json')
        self.assertEqual(res_cancel_again.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. Mentor accepts a new booking, then mentor cancels
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res2 = self.client.post('/api/bookings', {
            'mentor_id': self.mentor.id,
            'topic': 'Cancel Test Mentor',
            'duration_minutes': 30,
            'price': 25.0
        }, format='json')
        booking2_id = res2.data['id']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.mentor_token}')
        self.client.post(f'/api/bookings/{booking2_id}/accept')

        # Mentor cancels accepted booking
        res_mentor_cancel = self.client.post(f'/api/bookings/{booking2_id}/cancel', {'reason': 'Mentor unavailable'}, format='json')
        self.assertEqual(res_mentor_cancel.status_code, status.HTTP_200_OK)
        booking2 = Booking.objects.get(id=booking2_id)
        self.assertEqual(booking2.status, 'cancelled')

        # 3. Learner pays for a booking (escrow held), then cancels -> payment status refunded
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res3 = self.client.post('/api/bookings', {
            'mentor_id': self.mentor.id,
            'topic': 'Cancel Test Paid Escrow',
            'duration_minutes': 60,
            'price': 50.0
        }, format='json')
        booking3_id = res3.data['id']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.mentor_token}')
        self.client.post(f'/api/bookings/{booking3_id}/accept')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        self.client.post(f'/api/bookings/{booking3_id}/pay')
        booking3 = Booking.objects.get(id=booking3_id)
        self.assertEqual(booking3.status, 'paid')
        self.assertEqual(booking3.payments.first().status, 'held')

        # Learner cancels paid session
        res_paid_cancel = self.client.post(f'/api/bookings/{booking3_id}/cancel', {'reason': 'Emergency schedule conflict'}, format='json')
        self.assertEqual(res_paid_cancel.status_code, status.HTTP_200_OK)
        booking3.refresh_from_db()
        self.assertEqual(booking3.status, 'cancelled')
        self.assertEqual(booking3.payments.first().status, 'refunded')


    # --- 4. Chat & Anti-Leak Filter ---
    def test_chat_messages_and_leak_filter(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')

        # Normal message
        res = self.client.post('/api/messages', {
            'receiver_id': self.mentor.id,
            'body': 'Hi, are you available tomorrow?'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Message with phone number -> blocked
        res_leak1 = self.client.post('/api/messages', {
            'receiver_id': self.mentor.id,
            'body': 'Call me at +1 555-123-4567'
        }, format='json')
        self.assertEqual(res_leak1.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn('safety', res_leak1.data['error'])

        # Message with email -> blocked
        res_leak2 = self.client.post('/api/messages', {
            'receiver_id': self.mentor.id,
            'body': 'Email me at test@outside.com'
        }, format='json')
        self.assertEqual(res_leak2.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Message with URL -> blocked
        res_leak3 = self.client.post('/api/messages', {
            'receiver_id': self.mentor.id,
            'body': 'Check https://external.com'
        }, format='json')
        self.assertEqual(res_leak3.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

        # List conversation
        res_list = self.client.get(f'/api/messages?with={self.mentor.id}')
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data), 1)

    def test_delete_chat_and_message_rules(self):
        # 1. Learner sends message to Mentor
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res_send = self.client.post('/api/messages', {
            'receiver_id': self.mentor.id,
            'body': 'Message to be tested for deletion'
        }, format='json')
        self.assertEqual(res_send.status_code, status.HTTP_201_CREATED)
        msg_id = res_send.data['id']

        # 2. Mentor sends reply to Learner
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.mentor_token}')
        res_reply = self.client.post('/api/messages', {
            'receiver_id': self.learner.id,
            'body': 'Reply to be tested'
        }, format='json')
        self.assertEqual(res_reply.status_code, status.HTTP_201_CREATED)
        reply_id = res_reply.data['id']

        # 3. Learner attempts to delete mentor's message for 'everyone' -> Forbidden (only own message)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res_forbid = self.client.delete(f'/api/messages/{reply_id}?delete_for=everyone')
        self.assertEqual(res_forbid.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Learner deletes own recent message for 'everyone' -> Deleted for both
        res_del_everyone = self.client.delete(f'/api/messages/{msg_id}?delete_for=everyone')
        self.assertEqual(res_del_everyone.status_code, status.HTTP_200_OK)
        self.assertFalse(Message.objects.filter(id=msg_id).exists())

        # 5. Learner deletes mentor's message for 'me' -> Hidden for learner, visible for mentor
        res_del_me = self.client.delete(f'/api/messages/{reply_id}?delete_for=me')
        self.assertEqual(res_del_me.status_code, status.HTTP_200_OK)

        # Verify learner does not see it
        res_learner_view = self.client.get(f'/api/messages?with={self.mentor.id}')
        self.assertEqual(len(res_learner_view.data), 0)

        # Verify mentor STILL sees it
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.mentor_token}')
        res_mentor_view = self.client.get(f'/api/messages?with={self.learner.id}')
        self.assertEqual(len(res_mentor_view.data), 1)
        self.assertEqual(res_mentor_view.data[0]['id'], reply_id)

        # 6. Test clear conversation on own side
        # Mentor sends a new message
        res_new = self.client.post('/api/messages', {
            'receiver_id': self.learner.id,
            'body': 'Another message for clearing'
        }, format='json')
        self.assertEqual(res_new.status_code, status.HTTP_201_CREATED)

        # Mentor clears conversation with learner
        res_clear = self.client.delete(f'/api/messages/clear?with={self.learner.id}')
        self.assertEqual(res_clear.status_code, status.HTTP_200_OK)

        # Mentor sees 0 messages
        res_mentor_after = self.client.get(f'/api/messages?with={self.learner.id}')
        self.assertEqual(len(res_mentor_after.data), 0)

        # Learner STILL sees the message that was sent to them!
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res_learner_after = self.client.get(f'/api/messages?with={self.mentor.id}')
        self.assertEqual(len(res_learner_after.data), 1)

    def test_chat_encryption_at_rest(self):
        # 1. Learner sends confidential chat message
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        secret_text = 'Confidential project details and discussion topic'
        res_send = self.client.post('/api/messages', {
            'receiver_id': self.mentor.id,
            'body': secret_text
        }, format='json')
        self.assertEqual(res_send.status_code, status.HTTP_201_CREATED)
        msg_id = res_send.data['id']

        # 2. Verify encrypted at rest in Database
        db_msg = Message.objects.get(id=msg_id)
        self.assertTrue(db_msg.body.startswith('enc:v1:'))
        self.assertNotIn(secret_text, db_msg.body)
        self.assertEqual(db_msg.decrypted_body, secret_text)

        # 3. Verify API endpoints decrypt on-the-fly for authorized participants
        # Learner views conversation
        res_learner = self.client.get(f'/api/messages?with={self.mentor.id}')
        self.assertEqual(res_learner.status_code, status.HTTP_200_OK)
        found_learner = [m for m in res_learner.data if m['id'] == msg_id]
        self.assertEqual(len(found_learner), 1)
        self.assertEqual(found_learner[0]['body'], secret_text)

        # Mentor views conversation
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.mentor_token}')
        res_mentor = self.client.get(f'/api/messages?with={self.learner.id}')
        self.assertEqual(res_mentor.status_code, status.HTTP_200_OK)
        found_mentor = [m for m in res_mentor.data if m['id'] == msg_id]
        self.assertEqual(len(found_mentor), 1)
        self.assertEqual(found_mentor[0]['body'], secret_text)

        # Mentor views conversations list summary
        res_conv = self.client.get('/api/messages/conversations')
        self.assertEqual(res_conv.status_code, status.HTTP_200_OK)
        conv = next((c for c in res_conv.data if c.get('user_id') == self.learner.id or c.get('other_id') == self.learner.id), None)
        self.assertIsNotNone(conv)
        self.assertEqual(conv['last_message'], secret_text)

        # 4. Verify direct crypto helper behaves properly
        from api.crypto import encrypt_text, decrypt_text
        cipher = encrypt_text('hello secret')
        self.assertTrue(cipher.startswith('enc:v1:'))
        self.assertEqual(decrypt_text(cipher), 'hello secret')
        # Idempotent (does not double encrypt)
        self.assertEqual(encrypt_text(cipher), cipher)
        # Legacy plain text backward compatibility
        self.assertEqual(decrypt_text('legacy plain'), 'legacy plain')

    # --- 5. Reverse Problem Marketplace ---
    def test_problem_post_and_proposal_acceptance(self):
        # Learner posts problem
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res = self.client.post('/api/problems', {
            'title': 'Need help with Docker Compose',
            'description': 'Networking between containers is failing',
            'skills': 'docker, devops',
            'budget': 60.0
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        problem_id = res.data['id']

        # Mentor submits proposal
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.mentor_token}')
        res_prop = self.client.post(f'/api/problems/{problem_id}/proposals', {
            'message': 'I can help fix your docker network configuration in 30 mins',
            'proposed_price': 50.0
        }, format='json')
        self.assertEqual(res_prop.status_code, status.HTTP_201_CREATED)
        proposal_id = res_prop.data['id']

        # Learner accepts proposal
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res_accept = self.client.post(f'/api/problems/{problem_id}/proposals/{proposal_id}/accept')
        self.assertEqual(res_accept.status_code, status.HTTP_200_OK)
        self.assertIn('booking_id', res_accept.data)

        problem = ProblemPost.objects.get(id=problem_id)
        self.assertEqual(problem.status, 'closed')
        proposal = ProblemProposal.objects.get(id=proposal_id)
        self.assertEqual(proposal.status, 'accepted')

    # --- 6. Admin & Superadmin Operations ---
    def test_admin_stats_and_superadmin_delegation(self):
        # Admin stats
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        res_stats = self.client.get('/api/admin/stats')
        self.assertEqual(res_stats.status_code, status.HTTP_200_OK)
        self.assertIn('total_learners', res_stats.data)
        self.assertIn('revenue_by_day', res_stats.data)

        # Superadmin promote user
        test_user = User.objects.create_user(
            email='moderator@example.com',
            name='New Mod',
            password='password123',
            role='learner'
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.superadmin_token}')
        res_promote = self.client.post(f'/api/superadmin/admins/{test_user.id}/promote')
        self.assertEqual(res_promote.status_code, status.HTTP_200_OK)
        test_user.refresh_from_db()
        self.assertEqual(test_user.role, 'admin')

        # Revoke
        res_revoke = self.client.post(f'/api/superadmin/admins/{test_user.id}/revoke')
        self.assertEqual(res_revoke.status_code, status.HTTP_200_OK)
        test_user.refresh_from_db()
        self.assertEqual(test_user.role, 'learner')

    def test_admin_mentor_approval_and_rejection(self):
        # Create pending mentor
        applicant = User.objects.create_user(
            email='applicant@example.com',
            name='Dave Applicant',
            password='password123',
            role='learner'
        )
        app_profile = MentorProfile.objects.create(
            user=applicant,
            title='Cloud Architect',
            skills='aws, terraform, gcp',
            hourly_rate=80.0,
            approval_status='pending'
        )

        # Admin lists pending mentors
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        res_pending = self.client.get('/api/admin/mentors/pending')
        self.assertEqual(res_pending.status_code, status.HTTP_200_OK)
        self.assertTrue(any(m.get('user_id') == applicant.id and m.get('id') == applicant.id for m in res_pending.data))

        # Admin approves mentor via user_id
        res_approve = self.client.post(f'/api/admin/mentors/{applicant.id}/approve')
        self.assertEqual(res_approve.status_code, status.HTTP_200_OK)
        app_profile.refresh_from_db()
        self.assertEqual(app_profile.approval_status, 'approved')
        applicant.refresh_from_db()
        self.assertEqual(applicant.role, 'mentor')

        # Create second pending mentor to test rejection via profile_id
        applicant2 = User.objects.create_user(
            email='applicant2@example.com',
            name='Eve Reject',
            password='password123',
            role='learner'
        )
        app_profile2 = MentorProfile.objects.create(
            user=applicant2,
            title='Junior Dev',
            skills='scratch',
            hourly_rate=20.0,
            approval_status='pending'
        )

        # Admin rejects mentor via profile_id
        res_reject = self.client.post(f'/api/admin/mentors/{app_profile2.id}/reject')
        self.assertEqual(res_reject.status_code, status.HTTP_200_OK)
        app_profile2.refresh_from_db()
        self.assertEqual(app_profile2.approval_status, 'rejected')

        # 404 for non-existent mentor
        res_404 = self.client.post('/api/admin/mentors/999999/approve')
        self.assertEqual(res_404.status_code, status.HTTP_404_NOT_FOUND)

    def test_switch_role_endpoints(self):
        # 1. Self-switch: learner switches to mentor
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res_to_mentor = self.client.post('/api/auth/switch-role', {'role': 'mentor'}, format='json')
        self.assertEqual(res_to_mentor.status_code, status.HTTP_200_OK)
        self.assertEqual(res_to_mentor.data['user']['role'], 'mentor')
        self.learner.refresh_from_db()
        self.assertEqual(self.learner.role, 'mentor')
        self.assertTrue(MentorProfile.objects.filter(user=self.learner, approval_status='approved').exists())

        # Self-switch: mentor switches back to learner
        new_token = res_to_mentor.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_token}')
        res_to_learner = self.client.post('/api/auth/switch-role', {'role': 'learner'}, format='json')
        self.assertEqual(res_to_learner.status_code, status.HTTP_200_OK)
        self.assertEqual(res_to_learner.data['user']['role'], 'learner')
        self.learner.refresh_from_db()
        self.assertEqual(self.learner.role, 'learner')

        # 2. Admin switch user role
        target_user = User.objects.create_user(
            email='switchtarget@example.com',
            name='Target User',
            password='password123',
            role='learner'
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        res_admin_switch = self.client.post(f'/api/admin/users/{target_user.id}/switch-role', {'role': 'mentor'}, format='json')
        self.assertEqual(res_admin_switch.status_code, status.HTTP_200_OK)
        target_user.refresh_from_db()
        self.assertEqual(target_user.role, 'mentor')

        # Admin switches back to learner
        res_admin_back = self.client.post(f'/api/admin/users/{target_user.id}/switch-role', {'role': 'learner'}, format='json')
        self.assertEqual(res_admin_back.status_code, status.HTTP_200_OK)
        target_user.refresh_from_db()
        self.assertEqual(target_user.role, 'learner')

    # --- 16. Booking Duration & Booked Slots Hiding Tests ---
    def test_booking_duration_and_slot_hiding(self):
        # 1. Check initial available slots on a future date (e.g. 2026-10-15)
        test_date = '2026-10-15'
        res_slots = self.client.get(f'/api/mentors/{self.mentor.id}/available-slots?date={test_date}&duration=60')
        self.assertEqual(res_slots.status_code, status.HTTP_200_OK)
        initial_times = [s['time'] for s in res_slots.data['slots']]
        self.assertIn('14:00', initial_times)
        self.assertIn('14:30', initial_times)
        self.assertIn('15:00', initial_times)

        # 2. Learner books session with duration 60 mins at 14:00
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        res_book = self.client.post('/api/bookings', {
            'mentor_id': self.mentor.id,
            'topic': 'System Architecture Discussion',
            'duration_minutes': 60,
            'scheduled_at': f'{test_date}T14:00:00',
            'price': 50.0
        }, format='json')
        self.assertEqual(res_book.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_book.data['duration_minutes'], 60)
        self.assertEqual(res_book.data['scheduled_at'], f'{test_date}T14:00:00')

        # 3. Available slots for this date should now HIDE 14:00 and overlapping 14:30
        res_slots_after = self.client.get(f'/api/mentors/{self.mentor.id}/available-slots?date={test_date}&duration=60')
        self.assertEqual(res_slots_after.status_code, status.HTTP_200_OK)
        updated_times = [s['time'] for s in res_slots_after.data['slots']]

        # 14:00 is booked -> NOT SHOWN!
        self.assertNotIn('14:00', updated_times)
        # 14:30 would overlap with 14:00-15:00 -> NOT SHOWN!
        self.assertNotIn('14:30', updated_times)
        # 13:00 and 15:00 do not overlap -> SHOWN!
        self.assertIn('13:00', updated_times)
        self.assertIn('15:00', updated_times)

        # 4. Another learner attempts to book overlapping slot (14:30) -> HTTP 409 Conflict
        charlie = User.objects.create_user(
            email='charlie.conflict@example.com',
            name='Charlie Conflict',
            password='password123',
            role='learner'
        )
        charlie_token = generate_jwt(charlie)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {charlie_token}')

        res_conflict = self.client.post('/api/bookings', {
            'mentor_id': self.mentor.id,
            'topic': 'Overlapping booking attempt',
            'duration_minutes': 30,
            'scheduled_at': f'{test_date}T14:30:00',
            'price': 25.0
        }, format='json')
        self.assertEqual(res_conflict.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('already booked', res_conflict.data['error'])

        # 5. Non-conflicting slot (15:00) with custom duration (45 mins) succeeds
        res_free = self.client.post('/api/bookings', {
            'mentor_id': self.mentor.id,
            'topic': 'Non-conflicting booking',
            'duration_minutes': 45,
            'scheduled_at': f'{test_date}T15:00:00',
            'price': 37.5
        }, format='json')
        self.assertEqual(res_free.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_free.data['duration_minutes'], 45)

        # 6. Verify booked slots endpoint lists the busy intervals
        res_booked = self.client.get(f'/api/mentors/{self.mentor.id}/booked-slots')
        self.assertEqual(res_booked.status_code, status.HTTP_200_OK)
        booked_list = res_booked.data['booked_slots']
        self.assertGreaterEqual(len(booked_list), 2)

        # 7. Milestone contract session conflict check
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.learner_token}')
        from api.models import Contract
        contract = Contract.objects.create(
            learner=self.learner,
            mentor=self.mentor,
            created_by=self.learner,
            title='Mentorship Contract',
            total_sessions=3,
            status='active'
        )
        milestone = Booking.objects.create(
            learner=self.learner,
            mentor=self.mentor,
            contract=contract,
            session_number=1,
            duration_minutes=60,
            status='pending'
        )
        # Attempt to schedule milestone at 14:00 (already booked) -> 409 Conflict
        res_sched = self.client.post(f'/api/contracts/{contract.id}/sessions/{milestone.id}/schedule', {
            'scheduled_at': f'{test_date}T14:00:00'
        }, format='json')
        self.assertEqual(res_sched.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('already booked', res_sched.data['error'])

        # Attempt to schedule milestone at 16:00 (free) -> 200 OK
        res_sched_ok = self.client.post(f'/api/contracts/{contract.id}/sessions/{milestone.id}/schedule', {
            'scheduled_at': f'{test_date}T16:00:00'
        }, format='json')
        self.assertEqual(res_sched_ok.status_code, status.HTTP_200_OK)

    def test_available_dates_excludes_unavailable_days(self):
        """
        Verifies:
        1. /api/mentors/<id>/available-dates only returns days the mentor has open slots.
        2. Days where the mentor has no scheduled availability are strictly omitted.
        3. If all slots on an available day become booked, that day is automatically omitted.
        """
        from datetime import datetime, timedelta
        from api.models import MentorAvailability, MentorProfile

        # Create mentor with availability ONLY on Saturdays (day_of_week=6) from 10:00 to 12:00
        mentor_user = User.objects.create(email='weekend_mentor@example.com', name='Weekend Mentor', role='mentor')
        MentorProfile.objects.create(user=mentor_user, hourly_rate=60.0, approval_status='approved')
        MentorAvailability.objects.create(
            user=mentor_user,
            day_of_week=6,  # Saturday
            start_time='10:00',
            end_time='12:00'
        )

        res = self.client.get(f'/api/mentors/{mentor_user.id}/available-dates?duration=60&days=14')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        dates = res.data['available_dates']
        self.assertGreaterEqual(len(dates), 1)

        # Every single date returned MUST be a Saturday (day_of_week 6)
        for d in dates:
            parsed = datetime.strptime(d['date'], '%Y-%m-%d').date()
            js_day = (parsed.weekday() + 1) % 7
            self.assertEqual(js_day, 6, f"Expected Saturday (6), got {js_day} for date {d['date']}")
            self.assertEqual(d['weekday'], 'Saturday')

        first_sat = dates[0]['date']

        # Book the slots on first_sat (10:00-11:00 and 11:00-12:00)
        Booking.objects.create(
            learner=self.learner,
            mentor=mentor_user,
            topic='Session 1',
            duration_minutes=60,
            scheduled_at=f'{first_sat}T10:00:00',
            price=60.0,
            status='paid'
        )
        Booking.objects.create(
            learner=self.learner,
            mentor=mentor_user,
            topic='Session 2',
            duration_minutes=60,
            scheduled_at=f'{first_sat}T11:00:00',
            price=60.0,
            status='paid'
        )

        # Fetch available dates again: first_sat must now be completely gone!
        res_after = self.client.get(f'/api/mentors/{mentor_user.id}/available-dates?duration=60&days=14')
        self.assertEqual(res_after.status_code, status.HTTP_200_OK)
        dates_after = res_after.data['available_dates']
        date_strings = [d['date'] for d in dates_after]
        self.assertNotIn(first_sat, date_strings, f"Fully booked date {first_sat} should not be shown")






