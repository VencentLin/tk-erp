from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', '管理员'),
        ('country_lead', '国家负责人'),
        ('operator', '操作员'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='operator')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '用户配置'
        verbose_name_plural = '用户配置'

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'

    def save(self, *args, **kwargs):
        should_be_staff = self.role in ('admin', 'country_lead')
        if self.user.is_staff != should_be_staff:
            self.user.is_staff = should_be_staff
            # Use update() to avoid triggering post_save signal recursion
            User.objects.filter(pk=self.user.pk).update(is_staff=should_be_staff)
        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
