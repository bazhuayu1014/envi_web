"""
遥感数据管理系统的视图函数模块

本模块包含了处理Web请求的所有视图函数，包括：
- 地图显示
- 文件上传和下载
- 空间查询
- 工作站管理
- 数据处理等功能
"""

from django.core.files.storage import FileSystemStorage
from django.shortcuts import redirect, render, get_object_or_404
from django.core.management import call_command
from django.http import JsonResponse, FileResponse
from django.contrib.gis.db import models
from django.views.decorators.http import require_http_methods
from django.db import transaction
from .models import EnviData, EnviFile, WorkStation, WorkStationFile
import logging
import os
import json
from django.contrib.gis.geos import GEOSGeometry
from datetime import datetime
from django.db.models import Q
from .utils import EnviProcessor
from django.contrib.auth.decorators import login_required
import zipfile
import tempfile
import shutil
from django.conf import settings

# 配置日志记录器
logger = logging.getLogger(__name__)

@login_required
def map_view(request):
    """
    显示地图主页视图
    
    加载所有遥感数据并在地图上显示。用户可以在此页面上：
    - 查看所有已上传的遥感影像范围
    - 进行空间查询
    - 测量距离和面积
    - 下载数据等操作
    """
    envi_data = EnviData.objects.all()
    return render(request, 'geodata/map.html', {'envi_data': envi_data})

@login_required
def file_list_view(request):
    """
    显示可下载的ENVI文件列表
    
    展示系统中所有可下载的遥感数据文件，包括：
    - 原始数据
    - PC方法蚀变数据
    - Ratio方法蚀变数据
    用户可以按卫星类型筛选和下载文件。
    """
    envi_files = EnviFile.objects.select_related('envi_data').all().order_by('-upload_date')
    return render(request, 'geodata/file_list.html', {'envi_files': envi_files})

@login_required
@require_http_methods(["GET"])
def download_file(request, file_id):
    """
    下载ENVI文件
    
    处理文件下载请求，支持：
    - HDR和IMG文件下载
    - 原始数据、PC方法和Ratio方法蚀变数据的下载
    - 下载计数统计
    
    Args:
        file_id: 要下载的文件ID
        
    GET参数:
        type: 文件类型(hdr/img)
        data_type: 数据类型(original/pc/ratio)
    """
    envi_file = get_object_or_404(EnviFile, id=file_id)
    file_type = request.GET.get('type', 'hdr')  # hdr 或 img
    data_type = request.GET.get('data_type', 'original')  # original, pc 或 ratio
    
    # 根据数据类型选择对应的文件
    if data_type == 'pc':
        if file_type == 'hdr':
            if not envi_file.pc_hdr_file:
                return JsonResponse({'error': '未找到PC方法蚀变HDR文件'}, status=404)
            file_path = envi_file.pc_hdr_file.path
            filename = os.path.basename(envi_file.pc_hdr_file.name)
        else:
            if not envi_file.pc_img_file:
                return JsonResponse({'error': '未找到PC方法蚀变IMG文件'}, status=404)
            file_path = envi_file.pc_img_file.path
            filename = os.path.basename(envi_file.pc_img_file.name)
    elif data_type == 'ratio':
        if file_type == 'hdr':
            if not envi_file.ratio_hdr_file:
                return JsonResponse({'error': '未找到Ratio方法蚀变HDR文件'}, status=404)
            file_path = envi_file.ratio_hdr_file.path
            filename = os.path.basename(envi_file.ratio_hdr_file.name)
        else:
            if not envi_file.ratio_img_file:
                return JsonResponse({'error': '未找到Ratio方法蚀变IMG文件'}, status=404)
            file_path = envi_file.ratio_img_file.path
            filename = os.path.basename(envi_file.ratio_img_file.name)
    else:  # original
        if file_type == 'hdr':
            file_path = envi_file.hdr_file.path
            filename = os.path.basename(envi_file.hdr_file.name)
        else:
            file_path = envi_file.img_file.path
            filename = os.path.basename(envi_file.img_file.name)
    
    # 增加下载计数
    envi_file.download_count += 1
    envi_file.save()
    
    response = FileResponse(open(file_path, 'rb'), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required
@transaction.atomic
def process_envi(request):
    """
    处理ENVI文件上传和处理
    
    处理单个ENVI文件的上传，包括：
    - 文件上传和保存
    - 调用处理命令生成瓦片
    - 创建数据记录
    - 错误处理和回滚
    
    使用数据库事务确保数据一致性。
    """
    if request.method == 'POST':
        try:
            hdr_file = request.FILES.get('hdr_file')
            img_file = request.FILES.get('img_file')
            description = request.POST.get('description', '')
            
            if not hdr_file or not img_file:
                logger.warning('文件上传不完整')
                return render(request, 'geodata/upload.html', {'error': '请同时上传HDR和IMG文件'})

            # 开启数据库事务
            with transaction.atomic():
                # 创建EnviFile记录
                envi_file = EnviFile(
                    description=description,
                    hdr_file=hdr_file,
                    img_file=img_file
                )
                envi_file.save()
                
                try:
                    # 处理文件并生成瓦片
                    call_command('process_envi', envi_file.hdr_file.path, envi_file.img_file.path)
                    logger.info(f'ENVI处理成功: {envi_file.name}')
                    
                    # 获取最新创建的EnviData记录并关联
                    try:
                        latest_envi_data = EnviData.objects.latest('id')
                        if not latest_envi_data.envi_file:  # 确保这是刚创建的记录
                            latest_envi_data.envi_file = envi_file
                            latest_envi_data.save()
                            logger.info(f'成功关联EnviData(ID:{latest_envi_data.id})和EnviFile(ID:{envi_file.id})')
                        else:
                            # 如果最新记录已经有关联文件，可能是处理出错
                            raise Exception('无法找到对应的EnviData记录')
                    except EnviData.DoesNotExist:
                        # 如果没有找到EnviData记录，清理已上传的文件
                        raise Exception('处理完成但未创建EnviData记录')
                    
                    return redirect('geodata:map')
                except Exception as e:
                    # 如果处理过程出错，回滚事务（这会自动删除已创建的EnviFile记录）
                    logger.error(f'数据处理失败: {str(e)}', exc_info=True)
                    transaction.set_rollback(True)
                    return render(request, 'geodata/upload.html', {'error': f'数据处理失败: {str(e)}'})
        except Exception as e:
            logger.critical(f'系统错误: {str(e)}', exc_info=True)
            return render(request, 'geodata/upload.html', {'error': '系统发生意外错误'})
    
    return render(request, 'geodata/upload.html')

from django.contrib.gis.db.models.functions import Transform

@login_required
def envi_data_api(request):
    """
    获取所有遥感数据的API端点
    
    返回所有遥感数据的GeoJSON格式响应，包括：
    - 影像边界几何信息
    - 基本属性（名称、传感器类型、分辨率等）
    - 获取日期和坐标系信息
    - 瓦片URL和关联文件信息
    
    用于在地图上显示影像范围和属性信息。
    """
    try:
        envi_data = EnviData.objects.all()
        features = []
        
        for data in envi_data:
            try:
                geometry = json.loads(data.bounds.geojson) if data.bounds else None
                features.append({
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "name": data.name,
                        'sensor_type': data.sensor_type,
                        "resolution": data.resolution,
                        "acquisition_date": data.acquisition_date.strftime('%Y-%m-%d'),
                        "tile_url": data.tile_url,
                        "file_id": data.envi_file.id if data.envi_file else None,
                        "coordinate_system": data.coordinate_system,
                        "wavelength_info": data.wavelength_info
                    }
                })
            except Exception as e:
                logger.error(f'要素序列化失败 ID{data.id}: {str(e)}')
                continue

        return JsonResponse({
            "type": "FeatureCollection",
            "features": features
        }, safe=False)
    
    except Exception as e:
        logger.exception("API请求失败: %s", e)
        return JsonResponse({'error': '数据处理失败，请稍后重试'}, status=500)

@login_required
@require_http_methods(["POST"])
def spatial_query(request):
    """
    空间查询API端点
    
    处理空间查询请求，支持：
    - 多边形区域查询
    - 线缓冲区查询
    - 时间范围过滤
    - 卫星类型过滤
    
    请求体参数：
        geometry: GeoJSON格式的查询几何对象
        startDate: 开始日期（可选）
        endDate: 结束日期（可选）
        sensorTypes: 卫星类型列表（可选）
    
    返回满足条件的遥感数据列表，包含详细的属性信息。
    """
    try:
        data = json.loads(request.body)
        logger.info(f"接收到空间查询请求: {json.dumps(data, indent=2)}")
        
        geometry = data.get('geometry')
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        sensor_types = data.get('sensorTypes', [])
        
        logger.info(f"查询参数: 开始日期={start_date}, 结束日期={end_date}, 卫星类型={sensor_types}")
        
        # 获取数据库中的所有记录数
        total_records = EnviData.objects.count()
        logger.info(f"数据库中的总记录数: {total_records}")
        
        # 构建查询
        query = EnviData.objects.all()
        
        # 应用卫星类型过滤
        if sensor_types:
            query = query.filter(sensor_type__in=sensor_types)
            logger.info(f"应用卫星类型过滤 {sensor_types}, 剩余记录数: {query.count()}")
        
        # 处理日期范围过滤
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(acquisition_date__gte=start_date)
                logger.info(f"应用开始日期过滤 {start_date}, 剩余记录数: {query.count()}")
            except ValueError as e:
                logger.error(f"开始日期格式错误: {e}")
                return JsonResponse({'error': '开始日期格式错误'}, status=400)
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(acquisition_date__lte=end_date)
                logger.info(f"应用结束日期过滤 {end_date}, 剩余记录数: {query.count()}")
            except ValueError as e:
                logger.error(f"结束日期格式错误: {e}")
                return JsonResponse({'error': '结束日期格式错误'}, status=400)
        
        # 处理空间查询
        if geometry:
            try:
                # 创建搜索几何对象，设置SRID为4326（WGS84）
                search_geometry = GEOSGeometry(json.dumps(geometry), srid=4326)
                logger.info(f"原始搜索几何对象: {search_geometry.wkt}")

                # 如果是LineString，创建缓冲区
                if search_geometry.geom_type == 'LineString':
                    buffer_size = 1.0  # 1度缓冲区（约111km）
                    search_geometry = search_geometry.buffer(buffer_size)
                    logger.info(f"将LineString转换为带缓冲区的多边形: {search_geometry.wkt}")
                
                # 使用空间过滤
                matching_records = []
                for record in query:
                    if record.bounds:
                        try:
                            # 交换坐标顺序（处理坐标系差异）
                            swapped_wkt = record.bounds.wkt.replace('POLYGON ((', '').replace('))', '')
                            coords = [coord.strip().split() for coord in swapped_wkt.split(',')]
                            swapped_coords = [f"{y} {x}" for x, y in [coord for coord in coords]]
                            swapped_wkt = 'POLYGON ((' + ', '.join(swapped_coords) + '))'
                            record_bounds = GEOSGeometry(swapped_wkt, srid=4326)
                            
                            if search_geometry.intersects(record_bounds):
                                matching_records.append(record.id)
                                logger.info(f"找到匹配记录: ID={record.id}, 名称={record.name}")
                                
                        except Exception as e:
                            logger.error(f"处理记录 {record.id} 时出错: {e}", exc_info=True)
                            continue
                
                # 应用空间过滤结果
                if matching_records:
                    query = query.filter(id__in=matching_records)
                    logger.info(f"空间过滤后的匹配记录数: {query.count()}")
                else:
                    query = EnviData.objects.none()
                    logger.info("空间过滤后没有匹配记录")
                
            except Exception as e:
                logger.error(f"几何对象处理错误: {e}", exc_info=True)
                return JsonResponse({'error': f'几何对象处理错误: {str(e)}'}, status=400)
        
        # 构建查询结果
        results = []
        for envi_data in query:
            try:
                result = {
                    'id': envi_data.id,
                    'name': envi_data.name,
                    'sensor_type': envi_data.sensor_type,
                    'acquisition_date': envi_data.acquisition_date.strftime('%Y-%m-%d'),
                    'resolution': envi_data.resolution,
                    'coordinate_system': envi_data.coordinate_system,
                    'wavelength_info': envi_data.wavelength_info,
                    'size': envi_data.envi_file.file_size if envi_data.envi_file else 0,
                    'has_pc_alteration': bool(envi_data.envi_file and envi_data.envi_file.pc_hdr_file),
                    'has_ratio_alteration': bool(envi_data.envi_file and envi_data.envi_file.ratio_hdr_file)
                }
                if envi_data.bounds:
                    result['bounds'] = json.loads(envi_data.bounds.json)
                results.append(result)
                logger.info(f"添加结果: {result['name']} ({result['sensor_type']})")
            except Exception as e:
                logger.error(f"处理结果时出错 ID {envi_data.id}: {e}")
                continue
        
        logger.info(f"最终返回结果数量: {len(results)}")
        return JsonResponse({'results': results})
        
    except Exception as e:
        logger.error(f"空间查询出错: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def download_image(request, image_id):
    """
    下载单个影像文件的API端点
    
    根据影像ID下载对应的文件，同时更新下载计数。
    
    Args:
        image_id: 要下载的影像ID
    
    返回文件下载响应或错误信息。
    """
    try:
        envi_data = EnviData.objects.get(id=image_id)
        if not envi_data.envi_file:
            return JsonResponse({'error': '文件不存在'}, status=404)

        # 增加下载计数
        envi_data.envi_file.download_count += 1
        envi_data.envi_file.save()

        # 返回文件下载响应
        response = FileResponse(open(envi_data.envi_file.img_file.path, 'rb'))
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = f'attachment; filename="{envi_data.name}.img"'
        return response
    except EnviData.DoesNotExist:
        return JsonResponse({'error': '影像不存在'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(['GET', 'POST'])
def batch_upload(request):
    """
    批量上传ENVI文件
    
    处理多个ENVI文件的同时上传，支持：
    - 多文件选择和拖拽上传
    - HDR和IMG文件自动配对
    - 批量处理和进度显示
    - 处理结果实时反馈
    
    POST请求参数：
        files: 要上传的文件列表
    
    返回上传结果，包括成功和失败的文件信息。
    """
    if request.method == 'POST':
        try:
            files = request.FILES.getlist('files')
            if not files:
                return JsonResponse({
                    'success': False,
                    'error': '没有接收到文件'
                })

            # 用于临时存储文件对
            file_pairs = {}
            
            # 第一步：整理文件对
            for file in files:
                try:
                    ext = file.name.rsplit('.', 1)[1].lower()
                    base_name = file.name.rsplit('.', 1)[0]
                    
                    if base_name not in file_pairs:
                        file_pairs[base_name] = {'hdr': None, 'img': None}
                    
                    if ext in ['hdr', 'img']:
                        file_pairs[base_name][ext] = file

                except Exception as e:
                    logger.error(f"处理文件 {file.name} 时出错: {str(e)}", exc_info=True)
                    return JsonResponse({
                        'success': False,
                        'error': f'文件名格式错误: {file.name}'
                    })

            # 第二步：使用EnviProcessor处理文件对
            results = EnviProcessor.process_files(file_pairs)
            
            # 统计处理结果
            success_count = sum(1 for r in results if r['status'] == 'success')
            total_count = len(results)
            
            return JsonResponse({
                'success': True,
                'message': f'已完成 {total_count} 个文件的处理，其中 {success_count} 个成功',
                'results': results,
                'redirect_url': '/geodata/'
            })

        except Exception as e:
            logger.error(f"批量上传处理失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f"上传处理失败: {str(e)}"
            })

    # GET请求返回上传页面
    return render(request, 'geodata/batch_upload.html')

@login_required
@require_http_methods(['GET', 'POST'])
def alteration_upload(request):
    """
    蚀变数据批量上传
    
    处理蚀变指数数据的上传，支持：
    - PC方法和Ratio方法蚀变数据
    - 多文件批量上传
    - 自动关联到原始数据
    - 实时处理进度反馈
    
    POST请求参数：
        files: 要上传的文件列表
        alteration_type: 蚀变类型(pc/ratio)
    
    返回上传结果，包括成功和失败的文件信息。
    """
    if request.method == 'POST':
        try:
            files = request.FILES.getlist('files')
            alteration_type = request.POST.get('alteration_type')
            
            if not files:
                return JsonResponse({
                    'success': False,
                    'error': '请选择要上传的文件'
                })

            # 用于存储处理结果
            results = []
            success_count = 0
            
            # 按文件名分组（.hdr和.img）
            file_pairs = {}
            for file in files:
                base_name = file.name.rsplit('.', 1)[0]
                ext = file.name.rsplit('.', 1)[1].lower()
                
                if base_name not in file_pairs:
                    file_pairs[base_name] = {'hdr': None, 'img': None}
                
                if ext == 'hdr':
                    file_pairs[base_name]['hdr'] = file
                elif ext == 'img':
                    file_pairs[base_name]['img'] = file

            # 处理每对文件
            for base_name, pair in file_pairs.items():
                try:
                    if not pair['hdr'] or not pair['img']:
                        results.append({
                            'name': base_name,
                            'status': 'error',
                            'message': '文件不完整，需要同时上传HDR和IMG文件'
                        })
                        continue

                    # 从文件名中提取原始文件名
                    original_name = base_name.replace('_PC_alt', '').replace('_ratio_alt', '')
                    
                    # 查找对应的原始数据记录
                    try:
                        original_file = EnviFile.objects.get(name__startswith=original_name)
                        
                        # 根据蚀变类型更新对应的字段
                        if alteration_type == 'pc':
                            original_file.pc_hdr_file = pair['hdr']
                            original_file.pc_img_file = pair['img']
                        else:  # ratio
                            original_file.ratio_hdr_file = pair['hdr']
                            original_file.ratio_img_file = pair['img']

                        original_file.save()
                        success_count += 1
                        results.append({
                            'name': base_name,
                            'status': 'success',
                            'message': '上传成功'
                        })
                        
                    except EnviFile.DoesNotExist:
                        results.append({
                            'name': base_name,
                            'status': 'error',
                            'message': f'未找到对应的原始数据文件：{original_name}'
                        })
                        
                except Exception as e:
                    logger.error(f"处理文件 {base_name} 时出错: {str(e)}", exc_info=True)
                    results.append({
                        'name': base_name,
                        'status': 'error',
                        'message': str(e)
                    })

            return JsonResponse({
                'success': True,
                'message': f'已完成 {len(results)} 个文件的处理，其中 {success_count} 个成功',
                'results': results
            })
            
        except Exception as e:
            logger.error(f"蚀变数据上传失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'上传失败: {str(e)}'
            })
    
    # GET请求显示上传页面
    return render(request, 'geodata/alteration_upload.html', {
        'envi_files': EnviFile.objects.all().order_by('-upload_date')
    })

@login_required
def workstation_list(request):
    """
    显示用户的工作站列表
    
    展示当前用户创建的所有工作站，包括：
    - 工作站名称和描述
    - 创建时间
    - 包含的文件数量
    - 创建新工作站的功能
    """
    workstations = WorkStation.objects.filter(user=request.user)
    return render(request, 'geodata/workstation_list.html', {
        'workstations': workstations
    })

@login_required
def workstation_detail(request, pk):
    """
    显示工作站详情页面
    
    展示指定工作站的详细信息，包括：
    - 工作站基本信息
    - 包含的文件列表
    - 文件操作功能（下载、移除等）
    - 文件备注编辑功能
    
    Args:
        pk: 工作站的主键ID
    """
    workstation = get_object_or_404(WorkStation, pk=pk, user=request.user)
    files = WorkStationFile.objects.filter(workstation=workstation)
    return render(request, 'geodata/workstation_detail.html', {
        'workstation': workstation,
        'files': files
    })

@login_required
@require_http_methods(["POST"])
def create_workstation(request):
    """
    创建新的工作站
    
    处理创建工作站的请求，支持：
    - 设置工作站名称和描述
    - 自动关联到当前用户
    
    请求体参数：
        name: 工作站名称
        description: 工作站描述（可选）
    
    返回新创建的工作站信息。
    """
    data = json.loads(request.body)
    name = data.get('name')
    description = data.get('description', '')
    
    if not name:
        return JsonResponse({'error': '工作站名称不能为空'}, status=400)
    
    workstation = WorkStation.objects.create(
        user=request.user,
        name=name,
        description=description
    )
    
    return JsonResponse({
        'id': workstation.id,
        'name': workstation.name,
        'description': workstation.description,
        'created_at': workstation.created_at.isoformat()
    })

@login_required
@require_http_methods(["POST"])
def add_to_workstation(request):
    """
    添加文件到工作站
    
    将选中的文件添加到指定的工作站中，支持：
    - 批量添加多个文件
    - 自动去重（已存在的文件不会重复添加）
    
    请求体参数：
        workstation_id: 目标工作站ID
        file_ids: 要添加的文件ID列表
    
    返回添加结果，包括成功添加的文件数量。
    """
    data = json.loads(request.body)
    workstation_id = data.get('workstation_id')
    file_ids = data.get('file_ids', [])
    
    if not workstation_id or not file_ids:
        return JsonResponse({'error': '参数错误'}, status=400)
    
    workstation = get_object_or_404(WorkStation, pk=workstation_id, user=request.user)
    
    added_files = []
    for file_id in file_ids:
        try:
            envi_file = EnviFile.objects.get(pk=file_id)
            WorkStationFile.objects.get_or_create(
                workstation=workstation,
                envi_file=envi_file
            )
            added_files.append(file_id)
        except Exception as e:
            continue
    
    return JsonResponse({
        'message': f'成功添加 {len(added_files)} 个文件到工作站',
        'added_files': added_files
    })

@login_required
@require_http_methods(["POST"])
def remove_from_workstation(request):
    """
    从工作站移除文件
    
    将选中的文件从工作站中移除，支持：
    - 批量移除多个文件
    - 仅移除工作站关联，不删除原始文件
    
    请求体参数：
        workstation_id: 工作站ID
        file_ids: 要移除的文件ID列表
    
    返回移除结果。
    """
    data = json.loads(request.body)
    workstation_id = data.get('workstation_id')
    file_ids = data.get('file_ids', [])
    
    if not workstation_id or not file_ids:
        return JsonResponse({'error': '参数错误'}, status=400)
    
    workstation = get_object_or_404(WorkStation, pk=workstation_id, user=request.user)
    
    WorkStationFile.objects.filter(
        workstation=workstation,
        envi_file_id__in=file_ids
    ).delete()
    
    return JsonResponse({
        'message': f'成功移除选中的文件',
        'removed_files': file_ids
    })

@login_required
@require_http_methods(["POST"])
def batch_download(request):
    """
    批量下载工作站中的文件
    
    将选中的文件打包下载，支持：
    - 多文件打包下载
    - 自动创建临时ZIP文件
    - 下载完成后自动清理临时文件
    - 更新文件下载计数
    
    POST请求参数：
        workstation_id: 工作站ID
        file_ids: 要下载的文件ID列表
    
    返回ZIP文件下载响应。
    """
    try:
        workstation_id = request.POST.get('workstation_id')
        file_ids = request.POST.getlist('file_ids')
        
        if not workstation_id or not file_ids:
            return JsonResponse({'error': '参数错误'}, status=400)
        
        workstation = get_object_or_404(WorkStation, pk=workstation_id, user=request.user)
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        zip_filename = f'workstation_{workstation.id}_files.zip'
        zip_path = os.path.join(temp_dir, zip_filename)
        
        try:
            # 创建ZIP文件
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_id in file_ids:
                    try:
                        envi_file = EnviFile.objects.get(pk=file_id)
                        
                        # 添加HDR文件
                        if envi_file.hdr_file:
                            hdr_name = os.path.basename(envi_file.hdr_file.name)
                            zipf.write(envi_file.hdr_file.path, hdr_name)
                        
                        # 添加IMG文件
                        if envi_file.img_file:
                            img_name = os.path.basename(envi_file.img_file.name)
                            zipf.write(envi_file.img_file.path, img_name)
                        
                        # 增加下载计数
                        envi_file.download_count += 1
                        envi_file.save()
                        
                    except Exception as e:
                        logger.error(f"添加文件 {file_id} 到ZIP时出错: {str(e)}")
                        continue
            
            # 打开文件并创建响应
            if os.path.exists(zip_path):
                response = FileResponse(
                    open(zip_path, 'rb'),
                    content_type='application/zip',
                    as_attachment=True,
                    filename=zip_filename
                )
                
                # 注册一个回调来清理临时文件
                response._resource_closers.append(lambda: cleanup_temp_files(temp_dir))
                
                return response
            else:
                raise Exception("ZIP文件创建失败")
                
        except Exception as e:
            # 如果在处理过程中出现错误，清理临时文件并返回错误响应
            cleanup_temp_files(temp_dir)
            logger.error(f"创建ZIP文件时出错: {str(e)}")
            return JsonResponse({'error': '创建下载文件失败'}, status=500)
            
    except Exception as e:
        logger.error(f"批量下载处理失败: {str(e)}")
        return JsonResponse({'error': '下载处理失败'}, status=500)

def cleanup_temp_files(temp_dir):
    """
    清理临时文件
    
    删除批量下载过程中创建的临时文件和目录。
    
    Args:
        temp_dir: 临时目录的路径
    """
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    except Exception as e:
        logger.error(f"清理临时文件失败: {str(e)}")

@login_required
@require_http_methods(["POST"])
def save_file_note(request):
    """
    保存工作站文件备注
    
    更新工作站中文件的备注信息。
    
    请求体参数：
        workstation_id: 工作站ID
        file_id: 文件ID
        note: 新的备注内容
    
    返回更新后的备注信息。
    """
    try:
        data = json.loads(request.body)
        workstation_id = data.get('workstation_id')
        file_id = data.get('file_id')
        note = data.get('note', '')
        
        if not workstation_id or not file_id:
            return JsonResponse({'error': '参数错误'}, status=400)
        
        # 获取工作站文件记录
        workstation_file = get_object_or_404(
            WorkStationFile,
            workstation_id=workstation_id,
            workstation__user=request.user,
            envi_file_id=file_id
        )
        
        # 更新备注
        workstation_file.notes = note
        workstation_file.save()
        
        return JsonResponse({
            'message': '备注已保存',
            'note': note
        })
        
    except Exception as e:
        logger.error(f"保存文件备注时出错: {str(e)}")
        return JsonResponse({'error': '保存备注失败'}, status=500)

@login_required
@require_http_methods(["GET"])
def image_info(request, image_id):
    """
    获取影像详细信息的API端点
    
    返回指定影像的详细属性信息，包括：
    - 基本信息（名称、传感器类型等）
    - 空间信息（分辨率、坐标系等）
    - 时间信息（获取日期）
    - 波段信息
    - 几何范围
    
    Args:
        image_id: 要查询的影像ID
    
    返回JSON格式的影像信息。
    """
    try:
        envi_data = get_object_or_404(EnviData, id=image_id)
        
        # 构建响应数据
        response_data = {
            'id': envi_data.id,
            'name': envi_data.name,
            'sensor_type': envi_data.sensor_type,
            'resolution': envi_data.resolution,
            'acquisition_date': envi_data.acquisition_date.strftime('%Y-%m-%d'),
            'coordinate_system': envi_data.coordinate_system,
            'wavelength_info': envi_data.wavelength_info,
            'tile_url': envi_data.tile_url,
            'geometry': json.loads(envi_data.bounds.json) if envi_data.bounds else None
        }
        
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(f"获取影像信息失败 ID {image_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)
