from django.db import migrations

def fix_sensor_types(apps, schema_editor):
    EnviData = apps.get_model('geodata', 'EnviData')
    for data in EnviData.objects.all():
        # 根据文件名判断传感器类型
        if data.name.startswith('S2'):
            data.sensor_type = 'S2'
        elif data.name.startswith('GF5'):
            data.sensor_type = 'GF5'
        data.save()

def reverse_migration(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('geodata', '0006_update_existing_records'),
    ]

    operations = [
        migrations.RunPython(fix_sensor_types, reverse_migration),
    ] 