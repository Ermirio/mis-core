from datetime import timedelta

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from equipamentos.models import UserAccessPolicy


class UserAccessPolicyTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_admin_never_expires_and_can_open_admin_tools(self):
        admin = User.objects.create_superuser('root', password='safe-password')
        policy = UserAccessPolicy.objects.get(user=admin)
        self.assertIsNone(policy.expires_at)

        self.client.force_authenticate(admin)
        response = self.client.get(reverse('auth_admin_tools'))
        self.assertEqual(response.status_code, 200)

    def test_regular_user_is_hidden_from_admin_tools(self):
        user = User.objects.create_user('operator', password='safe-password')
        self.client.force_authenticate(user)
        response = self.client.get(reverse('auth_admin_tools'))
        self.assertEqual(response.status_code, 403)

    def test_staff_user_is_not_a_mis_admin_and_keeps_expiration(self):
        staff = User.objects.create_user('staff-user', password='safe-password', is_staff=True)
        policy = UserAccessPolicy.objects.get(user=staff)
        self.assertIsNotNone(policy.expires_at)

        self.client.force_authenticate(staff)
        response = self.client.get(reverse('auth_admin_tools'))
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('auth_me'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_admin'])
        self.assertNotIn('users', response.data)

    def test_staff_with_explicit_nodered_permission_can_cross_gateway(self):
        staff = User.objects.create_user('nodered-user', password='safe-password', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='access_nodered'))
        self.client.force_authenticate(staff)

        response = self.client.get(reverse('auth_admin_tools'), HTTP_X_ORIGINAL_URI='/nodered/')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('auth_admin_tools'), HTTP_X_ORIGINAL_URI='/grafana/')
        self.assertEqual(response.status_code, 403)

    def test_expired_user_cannot_login(self):
        user = User.objects.create_user('expired', password='safe-password')
        policy = UserAccessPolicy.objects.get(user=user)
        policy.expires_at = timezone.now() - timedelta(seconds=1)
        policy.save(update_fields=['expires_at', 'updated_at'])

        response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'expired', 'password': 'safe-password'},
            format='json',
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn('expirado', str(response.data).lower())

    def test_revalidation_restores_regular_user_access(self):
        admin = User.objects.create_superuser('root', password='safe-password')
        user = User.objects.create_user('operator', password='safe-password')
        policy = UserAccessPolicy.objects.get(user=user)
        policy.expires_at = timezone.now() - timedelta(days=1)
        policy.save(update_fields=['expires_at', 'updated_at'])

        policy.revalidate(admin)
        self.assertGreater(policy.expires_at, timezone.now() + timedelta(days=119))
        self.assertEqual(policy.revalidated_by, admin)

        response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'operator', 'password': 'safe-password'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)

    def test_me_does_not_expose_expiration_list(self):
        user = User.objects.create_user('operator', password='safe-password')
        self.client.force_authenticate(user)
        response = self.client.get(reverse('auth_me'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_admin'])
        self.assertNotIn('users', response.data)
