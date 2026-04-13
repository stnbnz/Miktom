from django.db import models

PROFILE_CHOICES = [
    ('1jam',    '1 Jam'),
    ('3jam',    '3 Jam'),
    ('1hari',   '1 Hari'),
    ('1minggu', '1 Minggu'),
]

class Voucher(models.Model):
    code         = models.CharField(max_length=20, unique=True)
    profile      = models.CharField(max_length=20, choices=PROFILE_CHOICES, default='1jam')
    duration_hours = models.IntegerField(default=1)
    price        = models.IntegerField(default=0)   # Harga dalam Rupiah
    created_at   = models.DateTimeField(auto_now_add=True)
    used_at      = models.DateTimeField(null=True, blank=True)
    expires_at   = models.DateTimeField(null=True, blank=True)
    is_used      = models.BooleanField(default=False)
    batch        = models.CharField(max_length=50, blank=True)  # ID batch generate

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} ({self.profile})"

class Router(models.Model):
    name = models.CharField(max_length=50)
    ip_address = models.CharField(max_length=50)
    username = models.CharField(max_length=50)
    password = models.CharField(max_length=50, blank=True)
    port = models.IntegerField(default=8728)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.ip_address}"
