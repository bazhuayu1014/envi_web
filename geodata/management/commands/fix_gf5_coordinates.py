from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Polygon
from geodata.models import EnviData
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '修复数据库中GF5影像的坐标顺序'

    def handle(self, *args, **options):
        # 获取所有GF5影像数据
        gf5_records = EnviData.objects.filter(name__startswith='GF5')
        count = gf5_records.count()
        fixed = 0

        self.stdout.write(f'找到 {count} 条GF5影像记录需要修复')

        for record in gf5_records:
            try:
                # 获取原始边界坐标
                original_coords = list(record.bounds.coords[0])
                
                # 交换每个点的经纬度顺序
                fixed_coords = [(y, x) for x, y in original_coords]
                
                # 创建新的多边形
                new_bounds = Polygon(fixed_coords)
                
                # 更新记录
                record.bounds = new_bounds
                record.center_point.x, record.center_point.y = record.center_point.y, record.center_point.x
                record.save()
                
                fixed += 1
                self.stdout.write(f'已修复记录: {record.name}')
                logger.info(f'记录 {record.name} 的原始坐标: {original_coords}')
                logger.info(f'记录 {record.name} 的修复后坐标: {fixed_coords}')
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'修复记录 {record.name} 时出错: {str(e)}'))
                logger.error(f'修复记录 {record.name} 时出错: {str(e)}')
                continue

        self.stdout.write(self.style.SUCCESS(f'完成! 共修复 {fixed}/{count} 条记录')) 