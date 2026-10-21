"""אותות Django — יצירת פרופיל אוטומטית לכל משתמש חדש."""

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """יוצר פרופיל אוטומטית בעת יצירת משתמש.

    בלי האות הזה הגישה ההפוכה ``request.user.profile`` הייתה מפילה
    עם ``RelatedObjectDoesNotExist`` עבור משתמשים שנרשמו לפני
    שהאות נוסף.
    """
    if created:
        Profile.objects.get_or_create(user=instance)
