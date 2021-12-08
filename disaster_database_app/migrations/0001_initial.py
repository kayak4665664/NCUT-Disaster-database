# Generated by Django 3.2.2 on 2021-07-16 06:28

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Disaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_corrected', models.BooleanField()),
                ('url', models.TextField()),
                ('text', models.TextField()),
                ('title', models.TextField()),
                ('time', models.TextField()),
                ('location', models.TextField()),
                ('country', models.TextField(null=True)),
                ('province', models.TextField(null=True)),
                ('prefecture', models.TextField(null=True)),
                ('category', models.TextField()),
            ],
        ),
    ]