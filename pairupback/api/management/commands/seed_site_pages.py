from django.core.management.base import BaseCommand
from api.models import SitePage, PlatformSetting


class Command(BaseCommand):
    help = 'Seed initial site pages and platform settings for PairUp'

    def handle(self, *args, **options):
        # Platform settings
        PlatformSetting.objects.get_or_create(
            setting_key='commission_percent',
            defaults={'setting_value': '10'}
        )
        self.stdout.write(self.style.SUCCESS('Platform settings initialized.'))

        # Site pages
        pages = [
            (
                'privacy',
                'Privacy Policy',
                '<div class="card" style="background:var(--warn-bg);border-color:var(--warn);margin-bottom:24px;">'
                '<p style="font-size:12.5px;color:var(--warn);margin:0;line-height:1.6;">'
                '<strong>This is a starting template, not legal advice.</strong> Have a real lawyer review this before launching with real users and real payments.</p></div>'
                '<div class="section-label" style="margin-top:0;">What we collect</div>'
                '<p class="sub">Account details you provide, mentor profile information, session and booking records, chat messages, and payment records. We do not store your card details directly.</p>'
                '<div class="section-label">How we use it</div>'
                '<p class="sub">To operate the marketplace: matching learners with mentors, processing escrow payments, showing ratings and reviews, and providing support. We do not sell your personal data.</p>'
                '<div class="section-label">Your rights</div>'
                '<p class="sub">You may have the right to access, correct, or delete your personal data depending on where you live. Contact us to exercise these rights.</p>'
                '<div class="section-label">Contact</div>'
                '<p class="sub">Questions about this policy: <a href="mailto:support@pairup.app" style="color:var(--accent);">support@pairup.app</a></p>'
            ),
            (
                'terms',
                'Terms of Service',
                '<div class="card" style="background:var(--warn-bg);border-color:var(--warn);margin-bottom:24px;">'
                '<p style="font-size:12.5px;color:var(--warn);margin:0;line-height:1.6;">'
                '<strong>This is a starting template, not legal advice.</strong> Get this reviewed by a lawyer, especially the payment and liability sections.</p></div>'
                '<div class="section-label" style="margin-top:0;">1. What PairUp is</div>'
                '<p class="sub">A marketplace connecting learners with independent IT mentors for live, 1-to-1 debugging and coding help. Mentors are independent professionals, not employees.</p>'
                '<div class="section-label">2. Payments &amp; escrow</div>'
                '<p class="sub">Funds are held in escrow and released once a session is marked complete. PairUp deducts a platform fee from each transaction.</p>'
                '<div class="section-label">3. Prohibited use</div>'
                '<p class="sub">You may not solicit payment or contact outside the platform to avoid fees, or attempt to circumvent escrow or reviews.</p>'
                '<div class="section-label">4. Contact</div>'
                '<p class="sub">Questions: <a href="mailto:support@pairup.app" style="color:var(--accent);">support@pairup.app</a></p>'
            ),
            (
                'help',
                'Help &amp; Support',
                '<div class="section-label" style="margin-top:0;">For learners</div>'
                '<div class="card" style="margin-bottom:10px;"><div style="font-weight:700;font-size:14px;margin-bottom:6px;">How does payment work?</div>'
                '<p class="sub">You pay upfront, but it is held in escrow until the session is marked complete, so you are protected if a mentor does not show up.</p></div>'
                '<div class="card" style="margin-bottom:10px;"><div style="font-weight:700;font-size:14px;margin-bottom:6px;">Can I message a mentor before paying?</div>'
                '<p class="sub">Yes — every mentor profile has a Message button.</p></div>'
                '<div class="section-label">For mentors</div>'
                '<div class="card" style="margin-bottom:10px;"><div style="font-weight:700;font-size:14px;margin-bottom:6px;">How do I get paid?</div>'
                '<p class="sub">Once a learner marks a session complete, escrowed payment is released to your account.</p></div>'
            ),
            (
                'contact',
                'Contact',
                '<p class="sub" style="margin-bottom:20px;">Questions, disputes, bug reports, partnership ideas — send us a message and we will get back to you.</p>'
                '<div class="card" style="margin-bottom:10px;"><div class="section-label" style="margin-top:0;">Support</div>'
                '<a href="mailto:support@pairup.app" style="color:var(--accent);font-weight:600;">support@pairup.app</a>'
                '<p class="sub" style="margin-top:4px;">For account issues, disputes, and payment questions.</p></div>'
                '<div class="card"><div class="section-label" style="margin-top:0;">General &amp; partnerships</div>'
                '<a href="mailto:hello@pairup.app" style="color:var(--accent);font-weight:600;">hello@pairup.app</a></div>'
            ),
        ]

        for slug, title, content in pages:
            SitePage.objects.update_or_create(
                slug=slug,
                defaults={'title': title, 'content_html': content}
            )
            self.stdout.write(self.style.SUCCESS(f'Site page "{slug}" seeded.'))
