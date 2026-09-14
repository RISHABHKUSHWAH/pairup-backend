from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None, role='learner', **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, name=name, role=role, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, name, password, role='superadmin', **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('learner', 'Learner'),
        ('mentor', 'Mentor'),
        ('admin', 'Admin'),
        ('superadmin', 'Superadmin'),
    )

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='learner')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def save(self, *args, **kwargs):
        if self.role in ('admin', 'superadmin'):
            self.is_staff = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.email}) - {self.role}"


class MentorProfile(models.Model):
    APPROVAL_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mentor_profile')
    photo_url = models.CharField(max_length=500, null=True, blank=True)
    title = models.CharField(max_length=255, default='', blank=True)
    company = models.CharField(max_length=255, default='', blank=True)
    years_experience = models.IntegerField(default=0)
    location = models.CharField(max_length=255, default='', blank=True)
    languages = models.CharField(max_length=500, default='', blank=True)  # comma separated
    bio = models.TextField(null=True, blank=True, default='')
    skills = models.CharField(max_length=500, default='', blank=True)     # comma separated
    hourly_rate = models.FloatField(default=0.0)
    github_url = models.CharField(max_length=500, null=True, blank=True)
    linkedin_url = models.CharField(max_length=500, null=True, blank=True)
    portfolio_url = models.CharField(max_length=500, null=True, blank=True)
    youtube_url = models.CharField(max_length=500, null=True, blank=True)
    x_url = models.CharField(max_length=500, null=True, blank=True)
    website_url = models.CharField(max_length=500, null=True, blank=True)
    approval_status = models.CharField(max_length=20, choices=APPROVAL_CHOICES, default='pending')
    online_status = models.IntegerField(default=0)
    rating_avg = models.FloatField(default=0.0)
    sessions_completed = models.IntegerField(default=0)
    disputes_count = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"MentorProfile: {self.user.name}"


class MentorExperience(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='experience')
    job_title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    start_date = models.CharField(max_length=50)
    end_date = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']


class MentorProject(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    url = models.CharField(max_length=500, null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']


class MentorEducation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='education')
    degree = models.CharField(max_length=255)
    university = models.CharField(max_length=255)
    year = models.CharField(max_length=50, null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']


class MentorCertification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certifications')
    name = models.CharField(max_length=255)
    issuer = models.CharField(max_length=255, null=True, blank=True)
    year = models.CharField(max_length=50, null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']


class MentorAward(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='awards')
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    year = models.CharField(max_length=50, null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']


class MentorAvailability(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='availability')
    day_of_week = models.IntegerField()  # 0 to 6
    start_time = models.CharField(max_length=20)
    end_time = models.CharField(max_length=20)

    class Meta:
        ordering = ['day_of_week', 'start_time']


class Contract(models.Model):
    STATUS_CHOICES = (
        ('proposed', 'Proposed'),
        ('active', 'Active'),
        ('completed_by_mentor', 'Completed by Mentor'),
        ('completed', 'Completed'),
        ('disputed', 'Disputed'),
        ('declined', 'Declined'),
    )

    learner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learner_contracts')
    mentor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mentor_contracts')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_contracts')

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    technology = models.CharField(max_length=255, blank=True, default='')
    topics = models.JSONField(default=list, blank=True)

    total_sessions = models.IntegerField(default=3)
    session_duration_minutes = models.IntegerField(default=60)
    total_price = models.FloatField(default=0.0)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='proposed')

    dispute_reason = models.TextField(null=True, blank=True)
    disputed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_disputes_raised')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Contract #{self.id}: {self.title} ({self.learner.name} & {self.mentor.name}) - {self.status}"


class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('paid', 'Paid'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('disputed', 'Disputed'),
    )

    learner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learner_bookings')
    mentor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mentor_bookings')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='sessions')
    session_number = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    topic = models.TextField(null=True, blank=True)
    duration_minutes = models.IntegerField(default=30)
    price = models.FloatField(default=0.0)
    scheduled_at = models.CharField(max_length=50, null=True, blank=True)
    dispute_reason = models.TextField(null=True, blank=True)
    disputed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='disputes_raised')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking #{self.id} ({self.learner.name} -> {self.mentor.name}: {self.status})"


class Payment(models.Model):
    STATUS_CHOICES = (
        ('held', 'Held'),
        ('released', 'Released'),
        ('refunded', 'Refunded'),
    )

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    amount = models.FloatField()
    platform_fee = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='held')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        ref = f"Booking #{self.booking_id}" if self.booking_id else f"Contract #{self.contract_id}"
        return f"Payment #{self.id} for {ref}: ${self.amount} ({self.status})"


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class Review(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review')
    learner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    mentor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received')
    rating = models.IntegerField()
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ProblemPost(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('closed', 'Closed'),
    )

    learner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='problem_posts')
    title = models.CharField(max_length=255)
    description = models.TextField()
    skills = models.CharField(max_length=500, default='', blank=True)
    budget = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ProblemProposal(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('negotiating', 'Negotiating'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('rejected', 'Rejected'),
    )

    problem = models.ForeignKey(ProblemPost, on_delete=models.CASCADE, related_name='proposals')
    mentor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proposals')
    message = models.TextField()
    proposed_price = models.FloatField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    counter_price = models.FloatField(null=True, blank=True)
    counter_message = models.TextField(default='', blank=True)
    last_action_by = models.CharField(max_length=20, default='mentor')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('problem', 'mentor')
        ordering = ['-created_at']


class SessionNote(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='session_notes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='session_notes')
    notes = models.TextField(default='', blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('booking', 'user')


class PlatformSetting(models.Model):
    setting_key = models.CharField(max_length=100, primary_key=True)
    setting_value = models.TextField(default='')

    def __str__(self):
        return f"{self.setting_key} = {self.setting_value}"


class SitePage(models.Model):
    slug = models.CharField(max_length=100, primary_key=True)
    title = models.CharField(max_length=255)
    content_html = models.TextField(default='')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class ContactMessage(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255, default='', blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_logs')
    actor_name = models.CharField(max_length=255)
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100, null=True, blank=True)
    target_id = models.IntegerField(null=True, blank=True)
    details = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, default='system')  # session, proposal, payment, review, problem, system
    link = models.CharField(max_length=255, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification({self.user.email} - {self.title})"


class SessionFile(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='session_files')
    uploader = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_session_files')
    file = models.FileField(upload_to='session_files/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_size = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"File '{self.filename}' for Booking #{self.booking_id}"


class SessionSummary(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='summary')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_summaries')
    summary_text = models.TextField()
    action_items = models.TextField(blank=True, default='')
    duration_seconds = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Summary for Booking #{self.booking_id}"


class SessionSignal(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='signals')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    signal_type = models.CharField(max_length=50)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"Signal({self.signal_type} from {self.sender.email} in Booking #{self.booking_id})"

