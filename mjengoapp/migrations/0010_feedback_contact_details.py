from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('mjengoapp', '0009_feedback'),
    ]

    operations = [
        migrations.AddField(
            model_name='feedback',
            name='first_name',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='feedback',
            name='last_name',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='feedback',
            name='email',
            field=models.EmailField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='feedback',
            name='phone_number',
            field=models.CharField(blank=True, default='', max_length=15),
        ),
    ]

