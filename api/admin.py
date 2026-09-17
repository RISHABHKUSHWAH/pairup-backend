from django.contrib import admin
from .models import (
    User, MentorProfile, MentorExperience, MentorProject,
    MentorEducation, MentorCertification, MentorAward, MentorAvailability,
    Booking, Payment, Message, Review, ProblemPost, ProblemProposal,
    SessionNote, PlatformSetting, SitePage, ContactMessage, AuditLog
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'role', 'is_staff', 'created_at')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('name', 'email')
    ordering = ('-created_at',)


@admin.register(MentorProfile)
class MentorProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'hourly_rate', 'approval_status', 'online_status', 'rating_avg', 'sessions_completed')
    list_filter = ('approval_status', 'online_status')
    search_fields = ('user__name', 'user__email', 'title', 'skills')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'learner', 'mentor', 'status', 'price', 'duration_minutes', 'created_at')
    list_filter = ('status',)
    search_fields = ('learner__name', 'mentor__name', 'topic')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'amount', 'platform_fee', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'decrypted_preview', 'is_encrypted', 'created_at')
    search_fields = ('sender__name', 'receiver__name')
    readonly_fields = ('decrypted_preview',)

    def decrypted_preview(self, obj):
        text = obj.decrypted_body or ''
        return text[:50] + ('...' if len(text) > 50 else '')
    decrypted_preview.short_description = 'Decrypted Content'

    def is_encrypted(self, obj):
        return bool(obj.body and obj.body.startswith('enc:v1:'))
    is_encrypted.boolean = True
    is_encrypted.short_description = 'Encrypted'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'learner', 'mentor', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('learner__name', 'mentor__name', 'comment')


@admin.register(ProblemPost)
class ProblemPostAdmin(admin.ModelAdmin):
    list_display = ('id', 'learner', 'title', 'budget', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('learner__name', 'title', 'skills')


@admin.register(ProblemProposal)
class ProblemProposalAdmin(admin.ModelAdmin):
    list_display = ('id', 'problem', 'mentor', 'proposed_price', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ('setting_key', 'setting_value')


@admin.register(SitePage)
class SitePageAdmin(admin.ModelAdmin):
    list_display = ('slug', 'title', 'updated_at')


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'subject', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'actor_name', 'action', 'target_type', 'target_id', 'created_at')
    list_filter = ('action', 'target_type')
    search_fields = ('actor_name', 'action', 'details')


admin.site.register(MentorExperience)
admin.site.register(MentorProject)
admin.site.register(MentorEducation)
admin.site.register(MentorCertification)
admin.site.register(MentorAward)
admin.site.register(MentorAvailability)
admin.site.register(SessionNote)
