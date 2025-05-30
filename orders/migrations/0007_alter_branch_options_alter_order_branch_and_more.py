# Generated by Django 5.2 on 2025-05-26 14:15

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0006_order_branch'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='branch',
            options={'ordering': ['name'], 'verbose_name': 'Branch', 'verbose_name_plural': 'Branches'},
        ),
        migrations.AlterField(
            model_name='order',
            name='branch',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='orders.branch'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['branch'], name='orders_orde_branch__c40543_idx'),
        ),
        migrations.AddConstraint(
            model_name='branch',
            constraint=models.UniqueConstraint(fields=('name',), name='unique_branch_name_city'),
        ),
    ]
