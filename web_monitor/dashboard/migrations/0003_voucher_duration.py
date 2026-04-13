# Generated migration for adding duration_label and updating duration_hours field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0002_router'),
    ]

    operations = [
        migrations.AlterField(
            model_name='voucher',
            name='duration_hours',
            field=models.FloatField(default=1),
        ),
        migrations.AddField(
            model_name='voucher',
            name='duration_label',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
