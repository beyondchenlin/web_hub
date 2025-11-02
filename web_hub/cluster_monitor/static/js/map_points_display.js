/**
 * 地图点位显示功能
 * 在地图上显示具体的坐标点和姓名信息
 */

// 地图点位数据管理器
const MapPointsManager = {
    data: null,
    isLoaded: false,
    chart: null,
    
    // 加载点位数据
    async loadData() {
        try {
            console.log('📍 正在加载地图点位数据...');
            
            const response = await fetch('/static/data/map_points.json');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.data = await response.json();
            this.isLoaded = true;
            
            console.log('✅ 地图点位数据加载成功');
            console.log(`📈 总点位数: ${this.data.total_count}`);
            console.log(`🗺️ 省份数: ${this.data.province_count}`);
            
            return this.data;
            
        } catch (error) {
            console.error('❌ 地图点位数据加载失败:', error);
            
            // 使用模拟数据作为备用
            this.data = this.createMockData();
            this.isLoaded = true;
            
            console.log('🔄 使用模拟数据作为备用');
            return this.data;
        }
    },
    
    // 创建模拟数据
    createMockData() {
        const mockPoints = [
            { name: '张三', address: '北京市朝阳区', province: '北京市', coordinates: [116.4074, 39.9042], value: [116.4074, 39.9042, 1] },
            { name: '李四', address: '上海市浦东新区', province: '上海市', coordinates: [121.4737, 31.2304], value: [121.4737, 31.2304, 1] },
            { name: '王五', address: '广东省深圳市', province: '广东省', coordinates: [114.0579, 22.5431], value: [114.0579, 22.5431, 1] }
        ];
        
        return {
            total_count: mockPoints.length,
            province_count: 3,
            points: mockPoints,
            provinces: {
                '北京市': { count: 1, names: ['张三'], center: [116.4074, 39.9042] },
                '上海市': { count: 1, names: ['李四'], center: [121.4737, 31.2304] },
                '广东省': { count: 1, names: ['王五'], center: [114.0579, 22.5431] }
            }
        };
    },
    
    // 初始化地图点位显示
    async initMapPoints() {
        try {
            // 等待地图初始化完成
            if (!window.mapChart) {
                console.log('⏳ 等待地图初始化...');
                setTimeout(() => this.initMapPoints(), 1000);
                return;
            }
            
            // 加载数据
            await this.loadData();
            
            // 添加点位到地图
            this.addPointsToMap();

            // 添加点击事件
            this.addPointClickEvents();

            // 启动动态效果
            this.startDynamicEffects();

            console.log('✅ 地图点位显示初始化完成');
            
        } catch (error) {
            console.error('❌ 地图点位显示初始化失败:', error);
        }
    },
    
    // 添加点位到地图
    addPointsToMap() {
        if (!this.data || !window.mapChart) return;
        
        console.log('📍 正在添加点位到地图...');
        
        // 准备散点数据
        const scatterData = this.data.points.map(point => ({
            name: point.name,
            value: point.value,
            address: point.address,
            province: point.province,
            coordinates: point.coordinates
        }));
        
        // 获取当前地图配置
        const currentOption = window.mapChart.getOption();
        
        // 添加散点图系列（显示用户坐标点）
        const newSeries = [
            ...currentOption.series,
            {
                name: '用户分布',
                type: 'scatter',
                coordinateSystem: 'geo',
                data: scatterData,
                symbol: 'circle', // 圆形符号
                symbolSize: 6,    // 符号大小
                label: {
                    show: false // 不显示标签，避免地图过于拥挤
                },
                itemStyle: {
                    color: '#ff6b6b',     // 用户点颜色
                    opacity: 0.8,         // 透明度
                    borderColor: '#fff',  // 边框颜色
                    borderWidth: 1        // 边框宽度
                },
                emphasis: {
                    itemStyle: {
                        color: '#ff4757',
                        opacity: 1,
                        shadowBlur: 10,
                        shadowColor: '#ff6b6b'
                    }
                },
                tooltip: {
                    trigger: 'item',
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    borderColor: '#ff6b6b',
                    borderWidth: 1,
                    textStyle: {
                        color: '#fff'
                    },
                    formatter: function(params) {
                        const data = params.data;
                        return `
                            <div style="padding: 8px; line-height: 1.4;">
                                <div style="color: #ff6b6b; font-weight: bold; margin-bottom: 6px; font-size: 14px;">
                                    👤 ${data.name}
                                </div>
                                <div style="color: #ddd; margin-bottom: 4px; font-size: 12px;">
                                    📍 ${data.address}
                                </div>
                                <div style="color: #aaa; font-size: 11px;">
                                    🗺️ ${data.province}
                                </div>
                                <div style="color: #888; font-size: 10px; margin-top: 4px; font-family: monospace;">
                                    坐标: ${data.coordinates[0].toFixed(4)}, ${data.coordinates[1].toFixed(4)}
                                </div>
                            </div>
                        `;
                    }
                }
            }
        ];
        
        // 更新地图配置
        window.mapChart.setOption({
            series: newSeries
        });
        
        console.log(`✅ 已添加 ${scatterData.length} 个点位到地图`);
    },


    
    // 添加点击事件
    addPointClickEvents() {
        if (!window.mapChart) return;

        // 点击散点事件
        window.mapChart.on('click', 'series.scatter', (params) => {
            this.showPointDetail(params.data);
        });

        console.log('✅ 点位点击事件已绑定');
    },
    
    // 显示点位详情
    showPointDetail(pointData) {
        console.log('📍 点击点位:', pointData.name);
        
        // 创建详情弹窗
        this.createDetailModal(pointData);
    },
    
    // 创建详情弹窗
    createDetailModal(pointData) {
        // 移除旧的弹窗
        const oldModal = document.getElementById('point-detail-modal');
        if (oldModal) {
            oldModal.remove();
        }
        
        // 创建新弹窗
        const modal = document.createElement('div');
        modal.id = 'point-detail-modal';
        modal.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            z-index: 10001;
            min-width: 300px;
            max-width: 400px;
        `;
        
        // 获取同省份的其他用户
        const sameProvinceUsers = this.getSameProvinceUsers(pointData.province, pointData.name);
        
        modal.innerHTML = `
            <div style="border-bottom: 2px solid #ff6b6b; padding-bottom: 10px; margin-bottom: 15px;">
                <h3 style="margin: 0; color: #ff6b6b;">👤 ${pointData.name}</h3>
            </div>
            
            <div style="margin-bottom: 10px;">
                <strong>📍 地址:</strong><br>
                <span style="color: #666;">${pointData.address}</span>
            </div>
            
            <div style="margin-bottom: 10px;">
                <strong>🗺️ 省份:</strong><br>
                <span style="color: #666;">${pointData.province}</span>
            </div>
            
            <div style="margin-bottom: 15px;">
                <strong>📐 坐标:</strong><br>
                <span style="color: #666; font-family: monospace;">
                    ${pointData.coordinates[0].toFixed(6)}, ${pointData.coordinates[1].toFixed(6)}
                </span>
            </div>
            
            ${sameProvinceUsers.length > 0 ? `
                <div style="margin-bottom: 15px; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                    <strong>👥 同省份用户 (${sameProvinceUsers.length}人):</strong><br>
                    <div style="margin-top: 5px; max-height: 100px; overflow-y: auto;">
                        ${sameProvinceUsers.slice(0, 10).join('、')}
                        ${sameProvinceUsers.length > 10 ? '...' : ''}
                    </div>
                </div>
            ` : ''}
            
            <div style="text-align: center; margin-top: 20px;">
                <button onclick="document.getElementById('point-detail-modal').remove()" 
                        style="background: #ff6b6b; color: white; border: none; padding: 8px 20px; border-radius: 5px; cursor: pointer;">
                    关闭
                </button>
            </div>
        `;
        
        // 创建遮罩层
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 10000;
        `;
        overlay.onclick = () => modal.remove();
        
        document.body.appendChild(overlay);
        document.body.appendChild(modal);
        
        // 3秒后自动关闭遮罩层
        setTimeout(() => {
            if (overlay.parentNode) {
                overlay.remove();
            }
        }, 10000);
    },
    
    // 获取同省份用户
    getSameProvinceUsers(province, excludeName) {
        if (!this.data || !this.data.provinces[province]) return [];
        
        return this.data.provinces[province].names.filter(name => name !== excludeName);
    },
    
    // 显示省份统计
    showProvinceStats() {
        if (!this.data) return;
        
        console.log('📊 省份统计:');
        const sortedProvinces = Object.entries(this.data.provinces)
            .sort((a, b) => b[1].count - a[1].count);
            
        sortedProvinces.forEach(([province, data], index) => {
            console.log(`${index + 1}. ${province}: ${data.count}人`);
        });
    },
    
    // 聚焦到指定省份
    focusOnProvince(provinceName) {
        if (!this.data || !this.data.provinces[provinceName] || !window.mapChart) return;
        
        const center = this.data.provinces[provinceName].center;
        
        // 使用ECharts的缩放功能
        window.mapChart.dispatchAction({
            type: 'geoSelect',
            name: provinceName
        });

        console.log(`🎯 聚焦到省份: ${provinceName}`);
    },

    // 启动动态效果
    startDynamicEffects() {
        if (!window.mapChart || !this.data) return;

        console.log('✨ 启动用户点动态效果...');

        // 随机选择一些点进行呼吸灯效果
        this.animateRandomPoints();

        // 定期更新动画
        setInterval(() => {
            this.animateRandomPoints();
        }, 3000); // 每3秒更新一次动画
    },

    // 随机点动画
    animateRandomPoints() {
        if (!window.mapChart || !this.data) return;

        // 随机选择10-20个点进行动画
        const animateCount = Math.floor(Math.random() * 10) + 10;
        const selectedPoints = [];

        for (let i = 0; i < animateCount && i < this.data.points.length; i++) {
            const randomIndex = Math.floor(Math.random() * this.data.points.length);
            selectedPoints.push(randomIndex);
        }

        // 为选中的点添加涟漪效果
        const currentOption = window.mapChart.getOption();
        const scatterSeries = currentOption.series.find(s => s.name === '用户分布');

        if (scatterSeries) {
            // 重置所有点的样式
            scatterSeries.data.forEach((point, index) => {
                if (selectedPoints.includes(index)) {
                    // 添加涟漪效果
                    point.symbolSize = 8;
                    point.itemStyle = {
                        color: '#ff4757',
                        opacity: 1,
                        shadowBlur: 15,
                        shadowColor: '#ff6b6b'
                    };
                } else {
                    // 普通样式
                    point.symbolSize = 6;
                    point.itemStyle = {
                        color: '#ff6b6b',
                        opacity: 0.8,
                        borderColor: '#fff',
                        borderWidth: 1
                    };
                }
            });

            // 更新地图
            window.mapChart.setOption({
                series: currentOption.series
            });
        }
    }
};

// 自动初始化
document.addEventListener('DOMContentLoaded', function() {
    // 延迟初始化，确保地图系统已加载
    setTimeout(() => {
        MapPointsManager.initMapPoints();
    }, 5000);
});

// 导出到全局作用域
window.MapPointsManager = MapPointsManager;

// 开发者控制台帮助
console.log('📍 地图点位显示功能已加载');
console.log('💡 控制台命令:');
console.log('  MapPointsManager.showProvinceStats() - 显示省份统计');
console.log('  MapPointsManager.focusOnProvince("省份名") - 聚焦到指定省份');
console.log('  MapPointsManager.addPointsToMap() - 重新添加点位到地图');
