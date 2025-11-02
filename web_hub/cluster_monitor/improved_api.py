#!/usr/bin/env python3
"""
改进的任务分发API
提供更详细的错误信息和状态反馈
"""

from flask import jsonify, request
from datetime import datetime

def setup_improved_task_api(app, monitor_instance):
    """设置改进的任务API"""
    
    @app.route('/api/send-task-v2', methods=['POST'])
    def send_task_v2():
        """发送任务 - 改进版本"""
        try:
            task_data = request.json
            if not task_data:
                return jsonify({
                    'success': False,
                    'error': '缺少任务数据',
                    'code': 'MISSING_TASK_DATA',
                    'timestamp': datetime.now().isoformat()
                }), 400
            
            # 检查必需字段
            required_fields = ['title']
            missing_fields = [field for field in required_fields if field not in task_data]
            if missing_fields:
                return jsonify({
                    'success': False,
                    'error': f'缺少必需字段: {missing_fields}',
                    'code': 'MISSING_REQUIRED_FIELDS',
                    'timestamp': datetime.now().isoformat()
                }), 400
            
            # 检查可用机器
            total_machines = len(monitor_instance.machines)
            online_machines = [m for m in monitor_instance.machines if m.is_online]
            available_machines = [m for m in online_machines if not m.is_busy]
            
            if not available_machines:
                return jsonify({
                    'success': False,
                    'error': '没有可用的处理机器',
                    'code': 'NO_AVAILABLE_MACHINES',
                    'details': {
                        'total_machines': total_machines,
                        'online_machines': len(online_machines),
                        'busy_machines': len([m for m in online_machines if m.is_busy]),
                        'offline_machines': total_machines - len(online_machines)
                    },
                    'timestamp': datetime.now().isoformat()
                }), 503
            
            # 分发任务
            selected_machine = monitor_instance.select_best_machine()
            if selected_machine:
                success = monitor_instance.send_task_to_machine(selected_machine, task_data)
                if success:
                    return jsonify({
                        'success': True,
                        'message': '任务已成功分发',
                        'machine': {
                            'url': selected_machine.url,
                            'priority': selected_machine.priority
                        },
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': '任务分发失败',
                        'code': 'DISPATCH_FAILED',
                        'machine': selected_machine.url,
                        'timestamp': datetime.now().isoformat()
                    }), 500
            else:
                return jsonify({
                    'success': False,
                    'error': '无法选择合适的机器',
                    'code': 'NO_SUITABLE_MACHINE',
                    'timestamp': datetime.now().isoformat()
                }), 503
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': '服务器内部错误',
                'code': 'INTERNAL_ERROR',
                'details': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500
    
    @app.route('/api/cluster-status', methods=['GET'])
    def get_cluster_status():
        """获取详细集群状态"""
        try:
            machines_status = []
            for machine in monitor_instance.machines:
                machine_info = {
                    'url': machine.url,
                    'host': machine.host,
                    'port': machine.port,
                    'priority': machine.priority,
                    'is_online': machine.is_online,
                    'is_busy': machine.is_busy,
                    'current_tasks': machine.current_tasks,
                    'last_check': machine.last_check,
                    'response_time': getattr(machine, 'response_time', None),
                    'last_error': getattr(machine, 'last_error', None)
                }
                machines_status.append(machine_info)
            
            return jsonify({
                'success': True,
                'cluster': {
                    'total_machines': len(monitor_instance.machines),
                    'online_machines': len([m for m in monitor_instance.machines if m.is_online]),
                    'available_machines': len([m for m in monitor_instance.machines if m.is_online and not m.is_busy]),
                    'monitoring_active': monitor_instance.monitoring_active
                },
                'machines': machines_status,
                'stats': monitor_instance.stats,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500
