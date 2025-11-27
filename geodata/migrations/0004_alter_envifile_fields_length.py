from django.db import migrations, models
import geodata.models

class Migration(migrations.Migration):

    dependencies = [
        ('geodata', '0003_alter_envifile_name_length'),
    ]

    operations = [
        migrations.AlterField(
            model_name='envifile',
            name='hdr_file',
            field=models.FileField(
                max_length=255,
                storage=geodata.models.keep_name_storage,
                upload_to='envi_files/%Y/%m/%d/',
                verbose_name='HDR文件'
            ),
        ),
        migrations.AlterField(
            model_name='envifile',
            name='img_file',
            field=models.FileField(
                max_length=255,
                storage=geodata.models.keep_name_storage,
                upload_to='envi_files/%Y/%m/%d/',
                verbose_name='IMG文件'
            ),
        ),
    ] 