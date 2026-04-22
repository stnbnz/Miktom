from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0005_activitylog_usersession"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutomationRunLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_name", models.CharField(db_index=True, max_length=100)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(default="RUNNING", max_length=20)),
                ("summary", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "router",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="dashboard.router",
                    ),
                ),
            ],
            options={
                "ordering": ["-started_at"],
                "db_table": "dashboard_automationrunlog",
            },
        ),
        migrations.AddIndex(
            model_name="automationrunlog",
            index=models.Index(fields=["task_name", "-started_at"], name="dashboard_a_task_na_6eb543_idx"),
        ),
        migrations.AddIndex(
            model_name="automationrunlog",
            index=models.Index(fields=["status", "-started_at"], name="dashboard_a_status_8bb9b8_idx"),
        ),
    ]
