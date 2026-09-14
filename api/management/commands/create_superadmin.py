from django.core.management.base import BaseCommand, CommandError
from api.models import User


class Command(BaseCommand):
    help = 'Create a superadmin account for PairUp'

    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='Full name of the superadmin')
        parser.add_argument('email', type=str, help='Email address')
        parser.add_argument('password', type=str, help='Password (min 6 characters)')

    def handle(self, *args, **options):
        name = options['name'].strip()
        email = options['email'].strip().lower()
        password = options['password']

        if len(password) < 6:
            raise CommandError('Password must be at least 6 characters')

        if User.objects.filter(email=email).exists():
            raise CommandError(f'An account with email {email} already exists')

        user = User.objects.create_user(
            email=email,
            name=name,
            password=password,
            role='superadmin',
            is_staff=True,
            is_superuser=True
        )

        self.stdout.write(self.style.SUCCESS(f'Successfully created superadmin account: {user.name} ({user.email})'))
