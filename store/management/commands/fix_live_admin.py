
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Repair the live admin account"

    def handle(self, *args, **options):
        username = os.environ.get("LIVE_ADMIN_USERNAME")
        password = os.environ.get("LIVE_ADMIN_PASSWORD")

        if not username or not password:
            raise CommandError(
                "Set LIVE_ADMIN_USERNAME and LIVE_ADMIN_PASSWORD "
                "in Render Environment first."
            )

        if len(password) < 12:
            raise CommandError(
                "Password must be at least 12 characters."
            )

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username
        )

        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Admin account configured: {username}"
            )
        )
