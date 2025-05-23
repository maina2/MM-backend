# Generated by Django 5.2 on 2025-05-22 10:31

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_product_discount_percentage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='products', to='products.branch'),
        ),
    ]
