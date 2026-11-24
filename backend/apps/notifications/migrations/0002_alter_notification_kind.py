from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="kind",
            field=models.CharField(choices=[
                ("booking_created", "Reserva recibida"),
                ("booking_confirmed", "Reserva confirmada"),
                ("booking_rescheduled", "Reserva reprogramada"),
                ("booking_canceled", "Reserva cancelada"),
                ("booking_reminder", "Recordatorio de reserva"),
            ], max_length=32),
        ),
    ]
