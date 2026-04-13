# Generated migration for ActivityLog and UserSession models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_voucher_password'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('activity_type', models.CharField(choices=[('voucher_generate', 'Voucher Generation'), ('voucher_delete', 'Voucher Deletion'), ('voucher_batch_delete', 'Batch Voucher Deletion'), ('user_kick', 'User Kick'), ('router_add', 'Router Added'), ('router_delete', 'Router Deleted'), ('router_switch', 'Router Switched'), ('system_reboot', 'System Reboot'), ('system_reset', 'System Reset'), ('backup_manual', 'Manual Backup'), ('login', 'User Login'), ('logout', 'User Logout')], max_length=30)),
                ('description', models.TextField()),
                ('ip_address', models.CharField(blank=True, max_length=50)),
                ('user_agent', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('success', models.BooleanField(default=True)),
                ('error_message', models.TextField(blank=True)),
                ('user', models.CharField(blank=True, max_length=100)),
                ('router', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='dashboard.router')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='UserSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(max_length=100, unique=True)),
                ('user', models.CharField(blank=True, max_length=100)),
                ('ip_address', models.CharField(max_length=50)),
                ('user_agent', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_activity', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('router_id', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-last_activity'],
            },
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['activity_type', '-timestamp'], name='dashboard_a_activit_idx'),
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['router', '-timestamp'], name='dashboard_a_router_idx'),
        ),
    ]
