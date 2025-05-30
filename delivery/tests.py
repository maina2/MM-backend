from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from users.models import CustomUser
from orders.models import Order
from delivery.models import Delivery
from delivery.utils import compute_shortest_route, geocode_address
import json

class DeliveryRouteOptimizationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='delivery1',
            password='pass123',
            email='delivery1@example.com',
            role='delivery'
        )
        self.order1 = Order.objects.create(
            customer=CustomUser.objects.create_user(
                username='customer1',
                password='pass123',
                email='customer1@example.com',
                role='customer'
            ),
            status='processing',
            total_amount=100.00
        )
        self.order2 = Order.objects.create(
            customer=CustomUser.objects.create_user(
                username='customer2',
                password='pass123',
                email='customer2@example.com',
                role='customer'
            ),
            status='processing',
            total_amount=150.00
        )
        self.delivery1 = Delivery.objects.create(
            order=self.order1,
            delivery_person=self.user,
            status='assigned',
            delivery_address='123 Market St, San Francisco, CA',
            latitude=37.7849,
            longitude=-122.4094
        )
        self.delivery2 = Delivery.objects.create(
            order=self.order2,
            delivery_person=self.user,
            status='assigned',
            delivery_address='456 Mission St, San Francisco, CA',
            latitude=37.7649,
            longitude=-122.4294
        )
        self.client.force_authenticate(user=self.user)

    def test_geocode_address(self):
        coords = geocode_address('123 Market St, San Francisco, CA')
        self.assertIsNotNone(coords)
        self.assertAlmostEqual(coords[0], 37.7849, places=2)
        self.assertAlmostEqual(coords[1], -122.4094, places=2)

    def test_compute_shortest_route(self):
        start = (37.7749, -122.4194)
        locations = [(37.7849, -122.4094), (37.7649, -122.4294)]
        route = compute_shortest_route(start, locations)
        self.assertIsNotNone(route)
        self.assertEqual(len(route), 4)  # Start -> loc1 -> loc2 -> start
        self.assertEqual(route[0], list(start))
        self.assertEqual(route[-1], list(start))

    def test_optimize_route_endpoint(self):
        response = self.client.post(
            reverse('delivery-person-optimize-route'),
            {
                'start_location': [37.7749, -122.4194],
                'delivery_ids': [self.delivery1.id, self.delivery2.id]
            },
            format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('optimized_route', response.data)
        self.assertEqual(len(response.data['optimized_route']), 4)
        self.assertEqual(response.data['optimized_route'][0], [37.7749, -122.4194])

    def test_optimize_route_invalid_delivery_ids(self):
        response = self.client.post(
            reverse('delivery-person-optimize-route'),
            {
                'start_location': [37.7749, -122.4194],
                'delivery_ids': [999]  # Non-existent ID
            },
            format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)

    def test_optimize_route_missing_coordinates(self):
        delivery_no_coords = Delivery.objects.create(
            order=self.order1,
            delivery_person=self.user,
            status='assigned',
            delivery_address='789 Howard St, San Francisco, CA'
        )
        response = self.client.post(
            reverse('delivery-person-optimize-route'),
            {
                'start_location': [37.7749, -122.4194],
                'delivery_ids': [delivery_no_coords.id]
            },
            format='json'
        )
        self.assertEqual(response.status_code, 200)  # Should geocode successfully
        self.assertIn('optimized_route', response.data)