from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('geodata', '0002_alter_envifile_hdr_file_alter_envifile_img_file'),
    ]

    operations = [
        migrations.AlterField(
            model_name='envifile',
            name='name',
            field=models.CharField(max_length=255, verbose_name='数据名称'),
        ),
    ] 