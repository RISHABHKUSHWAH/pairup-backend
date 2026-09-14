from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from api.models import (
    User, MentorProfile, Booking, Payment, Review,
    ProblemPost, ProblemProposal, PlatformSetting, SitePage
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


