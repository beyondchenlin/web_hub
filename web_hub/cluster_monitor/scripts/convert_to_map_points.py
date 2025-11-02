#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将CSV数据转换为地图点位数据
包含具体的经纬度坐标和姓名信息
"""

import json
import csv
import os
import sys
from pathlib import Path

def convert_csv_to_map_points(csv_path, output_path):
    """
    将CSV文件转换为地图点位数据格式
    
    Args:
        csv_path: CSV文件路径
        output_path: 输出JSON文件路径
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(csv_path):
            print(f"❌ CSV文件不存在: {csv_path}")
            return False
            
        print(f"📖 正在读取CSV文件: {csv_path}")
        
        # 读取CSV数据
        points = []
        province_stats = {}
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, 2):
                # 获取基本信息
                name = row.get('name', '').strip()
                address = row.get('address', '').strip()
                latitude = row.get('latitude', '').strip()
                longitude = row.get('longitude', '').strip()
                geocoded = row.get('geocoded', '').strip()
                
                # 跳过无效记录
                if not name or name.lower() == 'nan' or not latitude or not longitude:
                    continue
                
                # 跳过未成功地理编码的记录
                if geocoded.upper() != 'TRUE':
                    continue
                
                try:
                    lat = float(latitude)
                    lng = float(longitude)
                    
                    # 验证坐标范围（中国境内）
                    if not (15 <= lat <= 55 and 70 <= lng <= 140):
                        print(f"⚠️ 第{row_num}行坐标超出中国范围，跳过: {name} ({lat}, {lng})")
                        continue
                        
                except (ValueError, TypeError):
                    print(f"⚠️ 第{row_num}行坐标格式错误，跳过: {name}")
                    continue
                
                # 提取省份信息
                province = extract_province_from_address(address)
                
                # 创建点位数据
                point = {
                    'name': name,
                    'address': address,
                    'province': province,
                    'coordinates': [lng, lat],  # ECharts使用 [经度, 纬度] 格式
                    'value': [lng, lat, 1]      # ECharts散点图格式 [经度, 纬度, 数值]
                }
                
                points.append(point)
                
                # 统计省份信息
                if province not in province_stats:
                    province_stats[province] = {
                        'count': 0,
                        'names': [],
                        'points': []
                    }
                
                province_stats[province]['count'] += 1
                province_stats[province]['names'].append(name)
                province_stats[province]['points'].append(point)
                
        print(f"📊 数据处理完成，共 {len(points)} 个有效点位")
        
        # 生成地图数据
        map_data = {
            'total_count': len(points),
            'province_count': len(province_stats),
            'points': points,
            'provinces': {},
            'generated_at': str(Path(__file__).stat().st_mtime),
            'source_file': 'home.csv'
        }
        
        # 处理省份统计数据
        for province, stats in province_stats.items():
            map_data['provinces'][province] = {
                'count': stats['count'],
                'names': list(set(stats['names'])),  # 去重
                'center': calculate_center_point(stats['points'])
            }
        
        # 保存JSON文件
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(map_data, f, ensure_ascii=False, indent=2)
            
        print(f"✅ 地图数据已生成: {output_path}")
        print(f"📈 统计信息:")
        print(f"   总点位数: {map_data['total_count']}")
        print(f"   省份数: {map_data['province_count']}")
        
        # 显示TOP10省份
        top_provinces = sorted(province_stats.items(), key=lambda x: x[1]['count'], reverse=True)[:10]
        print(f"\n🏆 TOP10省份:")
        for i, (province, stats) in enumerate(top_provinces, 1):
            print(f"   {i}. {province}: {stats['count']}人")
        
        return True
        
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def extract_province_from_address(address):
    """从地址字符串中提取省份信息"""
    if not address or address.strip() == '':
        return '未知省份'
    
    address = address.strip()
    
    # 定义省份映射规则
    province_patterns = [
        # 直辖市
        ('北京', '北京市'),
        ('上海', '上海市'), 
        ('天津', '天津市'),
        ('重庆', '重庆市'),
        
        # 省份
        ('河北省', '河北省'),
        ('山西省', '山西省'),
        ('辽宁省', '辽宁省'),
        ('吉林省', '吉林省'),
        ('黑龙江省', '黑龙江省'),
        ('江苏省', '江苏省'),
        ('浙江省', '浙江省'),
        ('安徽省', '安徽省'),
        ('福建省', '福建省'),
        ('江西省', '江西省'),
        ('山东省', '山东省'),
        ('河南省', '河南省'),
        ('湖北省', '湖北省'),
        ('湖南省', '湖南省'),
        ('广东省', '广东省'),
        ('海南省', '海南省'),
        ('四川省', '四川省'),
        ('贵州省', '贵州省'),
        ('云南省', '云南省'),
        ('陕西省', '陕西省'),
        ('甘肃省', '甘肃省'),
        ('青海省', '青海省'),
        
        # 自治区
        ('内蒙古', '内蒙古自治区'),
        ('广西', '广西壮族自治区'),
        ('西藏', '西藏自治区'),
        ('宁夏', '宁夏回族自治区'),
        ('新疆', '新疆维吾尔自治区'),
        
        # 特别行政区
        ('香港', '香港特别行政区'),
        ('澳门', '澳门特别行政区'),
    ]
    
    # 按照模式匹配省份
    for pattern, standard_name in province_patterns:
        if pattern in address:
            return standard_name
    
    return '其他地区'

def calculate_center_point(points):
    """计算点位的中心坐标"""
    if not points:
        return [116.4074, 39.9042]  # 默认北京坐标
    
    total_lng = sum(point['coordinates'][0] for point in points)
    total_lat = sum(point['coordinates'][1] for point in points)
    count = len(points)
    
    return [total_lng / count, total_lat / count]

def main():
    """主函数"""
    print("🚀 CSV转地图点位数据工具")
    print("=" * 50)
    
    # 设置路径
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / 'data'
    csv_path = data_dir / 'home.csv'
    json_path = data_dir / 'map_points.json'
    
    print(f"📂 CSV文件: {csv_path}")
    print(f"📂 JSON文件: {json_path}")
    
    # 执行转换
    success = convert_csv_to_map_points(csv_path, json_path)
    
    if success:
        print("\n✅ 转换完成！")
        print("现在可以在地图系统中显示具体的点位了。")
        
        # 复制到静态目录
        static_path = script_dir.parent / 'static' / 'data' / 'map_points.json'
        try:
            import shutil
            shutil.copy2(json_path, static_path)
            print(f"📋 已复制到静态目录: {static_path}")
        except Exception as e:
            print(f"⚠️ 复制到静态目录失败: {e}")
            print(f"请手动复制: copy {json_path} {static_path}")
    else:
        print("\n❌ 转换失败！")
        print("请检查错误信息并重试。")

if __name__ == '__main__':
    main()
