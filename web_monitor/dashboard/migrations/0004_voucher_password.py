# Generated migration for adding password field to Voucher

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_voucher_duration'),
    ]

    operations = [
        migrations.AddField(
            model_name='voucher',
            name='password',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
