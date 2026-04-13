from django.db import models
from django.utils import timezone

PROFILE_CHOICES = [
    ('1jam',    '1 Jam'),
    ('3jam',    '3 Jam'),
    ('1hari',   '1 Hari'),
    ('1minggu', '1 Minggu'),
]

class Voucher(models.Model):
    code         = models.CharField(max_length=20, unique=True)
    password     = models.CharField(max_length=100, blank=True)  # Password terpisah dari code
    profile      = models.CharField(max_length=20, choices=PROFILE_CHOICES, default='1jam')
    duration_hours = models.FloatField(default=1)  # Termasuk decimal untuk menit
    duration_label = models.CharField(max_length=50, blank=True)  # Label asli: "5 Menit" atau "2 Jam"
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

    @property
    def expired(self):
        return bool(self.expires_at and timezone.now() >= self.expires_at)

    def mark_used(self):
        if not self.is_used:
            now = timezone.now()
            self.is_used = True
            self.used_at = now
            if not self.expires_at:
                self.expires_at = now + timedelta(hours=self.duration_hours)
            self.save()

class Router(models.Model):
    name = models.CharField(max_length=50)
    ip_address = models.CharField(max_length=50)
    username = models.CharField(max_length=50)
    password = models.CharField(max_length=50, blank=True)
    port = models.IntegerField(default=8728)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.ip_address}"

class BackupLog(models.Model):
    router = models.ForeignKey(Router, on_delete=models.CASCADE)
    backup_file = models.CharField(max_length=255)
    export_file = models.CharField(max_length=255, blank=True)
    backup_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='SUCCESS')  # SUCCESS, FAILED
    file_size = models.BigIntegerField(default=0)  # Size in bytes
    duration = models.FloatField(default=0)  # Backup duration in seconds

    class Meta:
        ordering = ['-backup_time']

    def __str__(self):
        return f"{self.router.name} - {self.backup_time}"

class SystemMetrics(models.Model):
    router = models.ForeignKey(Router, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # CPU & Memory
    cpu_load = models.IntegerField(default=0)  # Percentage
    ram_usage = models.IntegerField(default=0)  # Percentage
    free_memory_mb = models.IntegerField(default=0)
    total_memory_mb = models.IntegerField(default=0)
    
    # System Info
    uptime = models.CharField(max_length=50, blank=True)
    version = models.CharField(max_length=50, blank=True)
    board_name = models.CharField(max_length=100, blank=True)
    
    # Network
    internet_status = models.CharField(max_length=10, default='DOWN')  # UP/DOWN
    ping_latency = models.IntegerField(default=0)  # ms
    
    # Users
    active_users = models.IntegerField(default=0)
    banned_ips = models.IntegerField(default=0)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['router', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.router.name} - {self.timestamp}"

class InterfaceMetrics(models.Model):
    router = models.ForeignKey(Router, on_delete=models.CASCADE)
    system_metric = models.ForeignKey(SystemMetrics, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    name = models.CharField(max_length=50)
    status = models.CharField(max_length=10, default='DOWN')  # UP/DOWN
    tx_bytes = models.BigIntegerField(default=0)
    rx_bytes = models.BigIntegerField(default=0)
    tx_rate = models.FloatField(default=0)  # Mbps
    rx_rate = models.FloatField(default=0)  # Mbps

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.name} - {self.status}"

class ActiveUser(models.Model):
    router = models.ForeignKey(Router, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    user_id = models.CharField(max_length=50)  # MikroTik user ID
    username = models.CharField(max_length=100)
    ip_address = models.CharField(max_length=50)
    mac_address = models.CharField(max_length=20, blank=True)
    server = models.CharField(max_length=50, blank=True)
    uptime = models.CharField(max_length=50, blank=True)
    bytes_in = models.BigIntegerField(default=0)
    bytes_out = models.BigIntegerField(default=0)
    session_type = models.CharField(max_length=20, default='hotspot')  # hotspot/ppp
    
    is_active = models.BooleanField(default=True)
    disconnected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['router', 'username', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.username} - {self.ip_address}"

class NetworkTraffic(models.Model):
    router = models.ForeignKey(Router, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    interface_name = models.CharField(max_length=50)
    tx_bytes_total = models.BigIntegerField(default=0)
    rx_bytes_total = models.BigIntegerField(default=0)
    tx_rate_mbps = models.FloatField(default=0)
    rx_rate_mbps = models.FloatField(default=0)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['router', 'interface_name', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.interface_name} - {self.timestamp}"

class SystemAlert(models.Model):
    ALERT_TYPES = [
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('danger', 'Danger'),
        ('info', 'Info'),
    ]
    
    router = models.ForeignKey(Router, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    alert_type = models.CharField(max_length=10, choices=ALERT_TYPES, default='info')
    message = models.TextField()
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.alert_type}: {self.message[:50]}"

class VoucherUsage(models.Model):
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE)
    router = models.ForeignKey(Router, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    action = models.CharField(max_length=20)  # created, used, expired, deleted
    ip_address = models.CharField(max_length=50, blank=True)
    mac_address = models.CharField(max_length=20, blank=True)
    session_duration = models.IntegerField(default=0)  # seconds
    bytes_used = models.BigIntegerField(default=0)

    class Meta:
        ordering = ['-timestamp']

class ActivityLog(models.Model):
    ACTIVITY_TYPES = [
        ('voucher_generate', 'Voucher Generation'),
        ('voucher_delete', 'Voucher Deletion'),
        ('voucher_batch_delete', 'Batch Voucher Deletion'),
        ('user_kick', 'User Kick'),
        ('router_add', 'Router Added'),
        ('router_delete', 'Router Deleted'),
        ('router_switch', 'Router Switched'),
        ('system_reboot', 'System Reboot'),
        ('system_reset', 'System Reset'),
        ('backup_manual', 'Manual Backup'),
        ('login', 'User Login'),
        ('logout', 'User Logout'),
    ]
    
    router = models.ForeignKey(Router, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.CharField(max_length=100, blank=True)  # For web interface users
    timestamp = models.DateTimeField(auto_now_add=True)
    
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    ip_address = models.CharField(max_length=50, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Additional data as JSON
    metadata = models.JSONField(default=dict, blank=True)
    
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['activity_type', '-timestamp']),
            models.Index(fields=['router', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.activity_type} - {self.timestamp}"

class UserSession(models.Model):
    session_key = models.CharField(max_length=100, unique=True)
    user = models.CharField(max_length=100, blank=True)
    ip_address = models.CharField(max_length=50)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Session data
    router_id = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-last_activity']

    def __str__(self):
        return f"{self.user or 'Anonymous'} - {self.ip_address}"

    def __str__(self):
        return f"{self.voucher.code} - {self.action}"
