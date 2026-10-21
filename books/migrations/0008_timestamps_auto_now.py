"""ממלא את שדות הזמן החדשים וממיר אותם ל-auto_now/auto_now_add."""

import django.utils.timezone
from django.db import migrations, models

MODELS_WITH_TIMESTAMPS = (
    'book', 'chapter', 'profile', 'comment', 'category',
    'thread', 'forumpost', 'siteupdate', 'globalchatmsg', 'notification',
)


def backfill_timestamps(apps, schema_editor):
    """ממלא את שדות הזמן הריקים בערך הנוכחי."""
    now = django.utils.timezone.now()
    for model_name in MODELS_WITH_TIMESTAMPS:
        model = apps.get_model('books', model_name)
        model.objects.filter(created_at__isnull=True).update(created_at=now)
        model.objects.filter(updated_at__isnull=True).update(updated_at=now)


def nothing(apps, schema_editor):
    """פעולה הפוכה — אין למחוק נתונים."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0007_production_readiness'),
    ]

    operations = [
        migrations.RunPython(backfill_timestamps, nothing),
        migrations.AlterField(
            model_name='category',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='category',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='profile',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='profile',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='chapter',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='comment',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='forumpost',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='siteupdate',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='globalchatmsg',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='notification',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
