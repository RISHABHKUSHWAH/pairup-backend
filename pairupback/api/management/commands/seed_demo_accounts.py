from django.core.management.base import BaseCommand
from api.models import (
    User,
    MentorProfile,
    MentorExperience,
    MentorProject,
    MentorEducation,
    MentorCertification,
    MentorAvailability,
    ProblemPost,
    Booking,
    Review,
    Notification,
)


class Command(BaseCommand):
    help = 'Seeds standard demo accounts (Superadmin, Admin, Mentors, Learners) and initial sample marketplace data'

    def handle(self, *args, **options):
        # 1. Superadmin
        superadmin, _ = User.objects.get_or_create(
            email='super@example.com',
            defaults={'name': 'Super Admin', 'role': 'superadmin', 'is_staff': True, 'is_superuser': True}
        )
        superadmin.name = 'Super Admin'
        superadmin.role = 'superadmin'
        superadmin.set_password('supersecret123')
        superadmin.save()
        self.stdout.write(self.style.SUCCESS('Seeded super@example.com / supersecret123'))

        # 2. Admin
        admin, _ = User.objects.get_or_create(
            email='admin@example.com',
            defaults={'name': 'Platform Admin', 'role': 'admin', 'is_staff': True}
        )
        admin.name = 'Platform Admin'
        admin.role = 'admin'
        admin.set_password('adminsecret123')
        admin.save()
        self.stdout.write(self.style.SUCCESS('Seeded admin@example.com / adminsecret123'))

        # 3. Learner: Sarah
        learner, _ = User.objects.get_or_create(
            email='sarah@example.com',
            defaults={'name': 'Sarah Connor', 'role': 'learner'}
        )
        learner.name = 'Sarah Connor'
        learner.role = 'learner'
        learner.set_password('learner123')
        learner.save()
        self.stdout.write(self.style.SUCCESS('Seeded sarah@example.com / learner123'))

        # 4. Mentor: Alex Rivera
        alex, _ = User.objects.get_or_create(
            email='alex@example.com',
            defaults={'name': 'Alex Rivera', 'role': 'mentor'}
        )
        alex.name = 'Alex Rivera'
        alex.role = 'mentor'
        alex.set_password('mentor123')
        alex.save()

        alex_profile, _ = MentorProfile.objects.get_or_create(
            user=alex,
            defaults={
                'title': 'Senior Full Stack & Django Architect',
                'company': 'TechFlow Inc.',
                'years_experience': 7,
                'location': 'Bangalore, India',
                'languages': 'English, Hindi',
                'hourly_rate': 25.0,
                'skills': 'python, django, react, postgresql, docker',
                'bio': 'Senior backend & full stack engineer specializing in Python, Django REST Framework, database optimization, and React frontend architecture. Over 7 years of building production scale web platforms.',
                'github_url': 'https://github.com/alexrivera',
                'linkedin_url': 'https://linkedin.com/in/alexrivera',
                'approval_status': 'approved',
                'online_status': 1,
                'rating_avg': 4.9,
                'sessions_completed': 14,
                'disputes_count': 0,
            }
        )
        alex_profile.title = 'Senior Full Stack & Django Architect'
        alex_profile.company = 'TechFlow Inc.'
        alex_profile.skills = 'python, django, react, postgresql, docker'
        alex_profile.hourly_rate = 25.0
        alex_profile.bio = 'Senior backend & full stack engineer specializing in Python, Django REST Framework, database optimization, and React frontend architecture. Over 7 years of building production scale web platforms.'
        alex_profile.approval_status = 'approved'
        alex_profile.online_status = 1
        alex_profile.rating_avg = 4.9
        alex_profile.sessions_completed = 14
        alex_profile.save()

        # Experience & Education for Alex
        if not MentorExperience.objects.filter(user=alex).exists():
            MentorExperience.objects.create(
                user=alex,
                company='TechFlow Inc.',
                job_title='Staff Software Engineer',
                start_date='2022-01-01',
                end_date='2026-08-01',
                description='Architected microservices in Django and FastAPI, reduced API latency by 45%.'
            )
            MentorExperience.objects.create(
                user=alex,
                company='StartupHub Labs',
                job_title='Full Stack Developer',
                start_date='2019-03-01',
                end_date='2021-12-31',
                description='Built responsive SPAs in React with Django REST API backends.'
            )

        if not MentorProject.objects.filter(user=alex).exists():
            MentorProject.objects.create(
                user=alex,
                name='PairUp Real-Time Collab',
                url='https://github.com/alexrivera/pairup',
                description='Live pair programming platform with escrow-protected session booking.'
            )

        if not MentorEducation.objects.filter(user=alex).exists():
            MentorEducation.objects.create(
                user=alex,
                degree='B.Tech in Computer Science & Engineering',
                university='National Institute of Technology',
                year='2019'
            )

        if not MentorCertification.objects.filter(user=alex).exists():
            MentorCertification.objects.create(
                user=alex,
                name='AWS Certified Solutions Architect',
                issuer='Amazon Web Services',
                year='2023'
            )

        # Weekly availability for Alex (Mon - Fri, 6 PM - 10 PM)
        if not MentorAvailability.objects.filter(user=alex).exists():
            for day in range(1, 6):
                MentorAvailability.objects.create(
                    user=alex,
                    day_of_week=day,
                    start_time='18:00',
                    end_time='22:00'
                )

        self.stdout.write(self.style.SUCCESS('Seeded alex@example.com / mentor123 (Approved Mentor)'))

        # 5. Mentor: David Chen (DevOps / Cloud)
        david, _ = User.objects.get_or_create(
            email='david@example.com',
            defaults={'name': 'David Chen', 'role': 'mentor'}
        )
        david.name = 'David Chen'
        david.role = 'mentor'
        david.set_password('mentor123')
        david.save()

        david_profile, _ = MentorProfile.objects.get_or_create(
            user=david,
            defaults={
                'title': 'Principal DevOps & Cloud Engineer',
                'company': 'CloudScale Systems',
                'years_experience': 9,
                'location': 'Singapore',
                'languages': 'English, Mandarin',
                'hourly_rate': 35.0,
                'skills': 'devops, dsa, kubernetes, aws, terraform, docker',
                'bio': 'DevOps architect and Kubernetes certified administrator. I help developers debug deployment pipelines, CI/CD, and distributed infrastructure.',
                'github_url': 'https://github.com/davidchen',
                'linkedin_url': 'https://linkedin.com/in/davidchen',
                'approval_status': 'approved',
                'online_status': 1,
                'rating_avg': 5.0,
                'sessions_completed': 22,
                'disputes_count': 0,
            }
        )
        david_profile.title = 'Principal DevOps & Cloud Engineer'
        david_profile.company = 'CloudScale Systems'
        david_profile.skills = 'devops, dsa, kubernetes, aws, terraform, docker'
        david_profile.hourly_rate = 35.0
        david_profile.bio = 'DevOps architect and Kubernetes certified administrator. I help developers debug deployment pipelines, CI/CD, and distributed infrastructure.'
        david_profile.approval_status = 'approved'
        david_profile.online_status = 1
        david_profile.rating_avg = 5.0
        david_profile.sessions_completed = 22
        david_profile.save()

        # Weekly availability for David
        if not MentorAvailability.objects.filter(user=david).exists():
            for day in [0, 2, 4, 6]:
                MentorAvailability.objects.create(
                    user=david,
                    day_of_week=day,
                    start_time='16:00',
                    end_time='21:00'
                )

        self.stdout.write(self.style.SUCCESS('Seeded david@example.com / mentor123 (Approved Mentor)'))

        # 6. Sample Completed Bookings and Reviews
        booking1 = Booking.objects.filter(learner=learner, mentor=alex).first()
        if not booking1:
            booking1 = Booking.objects.create(
                learner=learner,
                mentor=alex,
                topic='Django ORM query optimization & transaction deadlock',
                duration_minutes=30,
                price=750.0,
                status='completed'
            )
        if not Review.objects.filter(booking=booking1).exists():
            Review.objects.create(
                booking=booking1,
                mentor=alex,
                learner=learner,
                rating=5,
                comment='Alex helped me fix a tricky Django database locking issue in less than 20 minutes! Super clear explanations.'
            )

        booking2 = Booking.objects.filter(learner=learner, mentor=david).first()
        if not booking2:
            booking2 = Booking.objects.create(
                learner=learner,
                mentor=david,
                topic='Kubernetes Ingress and cert-manager TLS debugging',
                duration_minutes=30,
                price=1050.0,
                status='completed'
            )
        if not Review.objects.filter(booking=booking2).exists():
            Review.objects.create(
                booking=booking2,
                mentor=david,
                learner=learner,
                rating=5,
                comment='Incredible DevOps expertise. Helped me debug a broken Kubernetes ingress and TLS cert in no time.'
            )

        # 7. Sample Open Problem Request
        if not ProblemPost.objects.filter(learner=learner).exists():
            ProblemPost.objects.create(
                learner=learner,
                title='Django REST Framework custom token auth returning 401',
                description='I implemented a custom JWT authentication class in DRF, but authenticated requests to protected endpoints return 401 Unauthorized. Need help reviewing my authenticate() method.',
                skills='python, django, jwt',
                budget=600.0,
                status='open'
            )

        # 8. Seed realistic notifications for demo accounts if empty
        if not Notification.objects.filter(user=alex).exists():
            Notification.objects.create(
                user=alex,
                title='New Problem Matching Your Skills 💡',
                message="Sarah Connor posted: 'Django REST Framework custom token auth returning 401' (Budget: $600).",
                notification_type='problem',
                link='/mentor/explore-problems',
                is_read=False,
            )
            Notification.objects.create(
                user=alex,
                title='New 5★ Review Received! ⭐',
                message="Sarah Connor left a 5-star review: 'Alex helped me fix a tricky Django database locking issue in less than 20 minutes!'",
                notification_type='review',
                link='/mentor/reviews',
                is_read=False,
            )
            Notification.objects.create(
                user=alex,
                title='Escrow Funds Released! 💰',
                message='$750 has been released to your balance for completed session with Sarah Connor.',
                notification_type='payment',
                link='/mentor/earnings',
                is_read=True,
            )

        if not Notification.objects.filter(user=learner).exists():
            Notification.objects.create(
                user=learner,
                title='Problem Request Published 🚀',
                message="Your problem 'Django REST Framework custom token auth returning 401' is now live. Mentors can submit proposals.",
                notification_type='problem',
                link='/learner/my-problems',
                is_read=False,
            )
            Notification.objects.create(
                user=learner,
                title='Welcome to PairUp! 🚀',
                message='Explore vetted expert mentors or post a problem request to get unstuck fast.',
                notification_type='system',
                link='/learner/explore',
                is_read=True,
            )

        self.stdout.write(self.style.SUCCESS('Successfully seeded all standard demo accounts and marketplace data!'))
