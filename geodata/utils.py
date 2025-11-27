import logging  # 日志模块
from django.core.management import call_command  # 调用Django管理命令
from django.db import transaction  # 数据库事务
from .models import EnviFile, EnviData  # 导入模型
from django.db.models import Q  # 数据库查询工具

# 获取logger实例
logger = logging.getLogger(__name__)

class EnviProcessor:
    """ENVI文件处理工具类
    提供ENVI文件的处理功能，包括：
    1. 单个文件处理
    2. 批量文件处理
    3. 数据关联
    """
    
    @staticmethod
    def process_single_file(envi_file):
        """处理单个ENVI文件对

        Args:
            envi_file: EnviFile实例，包含.hdr和.img文件

        Returns:
            dict: 处理结果，包含：
                - status: 处理状态（'success'或'error'）
                - message: 处理消息
                - envi_data_id: 成功时返回关联的EnviData ID
        """
        try:
            # 使用事务确保数据一致性
            with transaction.atomic():
                logger.info(f"开始处理文件: {envi_file.name} (ID: {envi_file.id})")
                
                # 记录处理前的所有已关联的EnviData记录ID
                existing_ids = set(EnviData.objects.filter(
                    ~Q(envi_file=None)
                ).values_list('id', flat=True))
                
                # 调用Django管理命令处理文件并生成瓦片
                call_command('process_envi', envi_file.hdr_file.path, envi_file.img_file.path)
                
                # 获取处理后新创建的未关联的EnviData记录
                new_envi_data = EnviData.objects.filter(
                    Q(envi_file=None) | ~Q(id__in=existing_ids)
                ).order_by('-id').first()
                
                if new_envi_data:
                    # 建立EnviData和EnviFile的关联
                    new_envi_data.envi_file = envi_file
                    new_envi_data.save()
                    logger.info(f"成功关联 EnviData(ID:{new_envi_data.id}) 和 EnviFile(ID:{envi_file.id})")
                    return {
                        'status': 'success',
                        'message': '处理完成',
                        'envi_data_id': new_envi_data.id
                    }
                else:
                    raise Exception('处理完成但未找到对应的EnviData记录')

        except Exception as e:
            logger.error(f"处理文件失败: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    @staticmethod
    def process_files(file_pairs):
        """批量处理ENVI文件对

        Args:
            file_pairs: dict, 键为基础名称，值为包含'hdr'和'img'文件的字典
               例如：{
                   'file1': {'hdr': hdr_file1, 'img': img_file1},
                   'file2': {'hdr': hdr_file2, 'img': img_file2}
               }

        Returns:
            list: 处理结果列表，每个元素是一个字典，包含：
                - name: 文件名
                - status: 处理状态
                - message: 处理消息
        """
        results = []
        
        for base_name, files in file_pairs.items():
            # 检查文件对是否完整
            if not files['hdr'] or not files['img']:
                logger.warning(f"文件不完整: {base_name}")
                results.append({
                    'name': base_name,
                    'status': 'error',
                    'message': '文件不完整'
                })
                continue

            try:
                # 使用事务处理每个文件对
                with transaction.atomic():
                    # 创建EnviFile记录
                    envi_file = EnviFile(
                        name=base_name,
                        description=f"批量上传 - {base_name}"
                    )
                    envi_file.hdr_file = files['hdr']
                    envi_file.img_file = files['img']
                    envi_file.save()
                    
                    # 处理文件
                    process_result = EnviProcessor.process_single_file(envi_file)
                    process_result['name'] = base_name
                    results.append(process_result)
                    
            except Exception as e:
                logger.error(f"处理文件对 {base_name} 时出错: {str(e)}", exc_info=True)
                results.append({
                    'name': base_name,
                    'status': 'error',
                    'message': str(e)
                })
                continue
        
        return results