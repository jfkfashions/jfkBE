# Generated migration file

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("biobio", "0020_alter_measurement_username"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="order_id",
            field=models.CharField(blank=True, max_length=20, unique=True),
        ),
    ]
