/**
 * 地图省份悬停功能
 * 显示省份人数统计和随机姓名
 */

// 省份数据管理器
const ProvinceDataManager = {
    data: null,
    isLoaded: false,
    
    // 加载省份数据
    async loadData() {
        try {
            console.log('📊 正在加载省份数据...');

            const response = await fetch('/static/data/map_points.json');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.data = await response.json();
            this.isLoaded = true;

            console.log('✅ 省份数据加载成功');
            console.log(`📈 在线人数: ${this.data.total_count}`);
            console.log(`🗺️ 省份数: ${Object.keys(this.data.provinces).length}`);

            return this.data;

        } catch (error) {
            console.error('❌ 省份数据加载失败:', error);

            // 使用模拟数据作为备用
            this.data = this.createMockData();
            this.isLoaded = true;

            console.log('🔄 使用模拟数据作为备用');
            return this.data;
        }
    },
    
    // 创建模拟数据
    createMockData() {
        const mockProvinces = {
            '北京': { count: 15, names: ['张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十', '郑一', '王二', '冯三', '陈四', '褚五', '卫六', '蒋七'] },
            '上海': { count: 12, names: ['刘明', '陈华', '张伟', '李娜', '王强', '赵敏', '孙丽', '周杰', '吴磊', '郑爽', '王芳', '李雷'] },
            '广东': { count: 20, names: ['黄志明', '林小雨', '梁大伟', '何美丽', '罗志祥', '邓紫棋', '谢霆锋', '古天乐', '刘德华', '张学友', '郭富城', '黎明', '陈奕迅', '容祖儿', '杨千嬅', '梁朝伟', '周润发', '成龙', '李连杰', '甄子丹'] },
            '浙江': { count: 8, names: ['马云', '宗庆后', '丁磊', '史玉柱', '鲁冠球', '李书福', '郭广昌', '南存辉'] },
            '江苏': { count: 10, names: ['任正非', '张近东', '严介和', '缪汉根', '朱共山', '车建新', '孙飘扬', '周海江', '陈发树', '许连捷'] }
        };
        
        return {
            total_count: Object.values(mockProvinces).reduce((sum, p) => sum + p.count, 0),
            provinces: mockProvinces,
            generated_at: Date.now(),
            source_file: '模拟数据'
        };
    },
    
    // 获取省份数据
    getProvinceData(provinceName) {
        if (!this.isLoaded || !this.data) {
            return null;
        }
        
        // 尝试精确匹配
        if (this.data.provinces[provinceName]) {
            return this.data.provinces[provinceName];
        }
        
        // 尝试模糊匹配（去掉"省"、"市"、"自治区"等后缀）
        const cleanName = provinceName.replace(/(省|市|自治区|特别行政区)$/, '');
        for (const [key, value] of Object.entries(this.data.provinces)) {
            const cleanKey = key.replace(/(省|市|自治区|特别行政区)$/, '');
            if (cleanKey === cleanName || key.includes(cleanName) || cleanName.includes(cleanKey)) {
                return value;
            }
        }
        
        return null;
    },
    
    // 获取当前正在使用的用户（从活跃用户点中获取）
    getActiveUsers(provinceName, count = 10) {
        // 首先尝试从UserPointsManager获取活跃用户
        if (window.UserPointsManager && window.UserPointsManager.activePoints) {
            const activeUsers = [];

            // 遍历所有活跃用户点
            for (const [id, userPoint] of window.UserPointsManager.activePoints) {
                if (userPoint.province === provinceName && userPoint.realName) {
                    activeUsers.push({
                        name: userPoint.realName,
                        address: userPoint.realAddress,
                        status: userPoint.status,
                        isActive: true // 所有从活跃用户点来的都是正在使用的用户
                    });
                }
            }

            // 如果活跃用户不足10个，从该省份的真实用户数据中补充
            if (activeUsers.length < count) {
                const provinceData = this.getProvinceData(provinceName);
                if (provinceData && provinceData.names) {
                    const existingNames = new Set(activeUsers.map(user => user.name));
                    const availableNames = provinceData.names.filter(name => !existingNames.has(name));

                    // 随机选择补充用户，确保总数达到10个
                    const needCount = count - activeUsers.length;
                    const shuffledNames = [...availableNames].sort(() => Math.random() - 0.5);

                    for (let i = 0; i < Math.min(needCount, shuffledNames.length); i++) {
                        activeUsers.push({
                            name: shuffledNames[i],
                            address: '',
                            status: 'using', // 标记为正在使用状态
                            isActive: true
                        });
                    }
                }
            }

            // 按状态排序：active > spawning > fading > using
            activeUsers.sort((a, b) => {
                const statusOrder = { 'active': 0, 'spawning': 1, 'fading': 2, 'using': 3 };
                return statusOrder[a.status] - statusOrder[b.status];
            });

            return activeUsers.slice(0, count);
        }

        // 如果UserPointsManager不可用，回退到显示该省份的用户
        const provinceData = this.getProvinceData(provinceName);
        if (!provinceData || !provinceData.names) {
            return [];
        }

        const names = [...provinceData.names]; // 复制数组
        const randomUsers = [];

        // 随机选择指定数量的姓名
        for (let i = 0; i < Math.min(count, names.length); i++) {
            const randomIndex = Math.floor(Math.random() * names.length);
            randomUsers.push({
                name: names.splice(randomIndex, 1)[0],
                address: '',
                status: 'using',
                isActive: true
            });
        }

        return randomUsers;
    }
};

// 省份悬停管理器
const ProvinceHoverManager = {
    isEnabled: false,
    tooltipElement: null,
    
    // 初始化
    async init() {
        try {
            // 加载数据
            await ProvinceDataManager.loadData();
            
            // 创建自定义tooltip元素
            this.createTooltipElement();
            
            // 启用悬停功能
            this.enable();
            
            console.log('✅ 省份悬停功能初始化完成');
            
        } catch (error) {
            console.error('❌ 省份悬停功能初始化失败:', error);
        }
    },
    
    // 创建tooltip元素
    createTooltipElement() {
        // 移除旧的tooltip
        const oldTooltip = document.getElementById('province-tooltip');
        if (oldTooltip) {
            oldTooltip.remove();
        }
        
        // 创建新的tooltip
        this.tooltipElement = document.createElement('div');
        this.tooltipElement.id = 'province-tooltip';
        this.tooltipElement.style.cssText = `
            position: fixed;
            background: rgba(0, 0, 0, 0.9);
            color: #ffffff;
            padding: 15px 20px;
            border-radius: 8px;
            border: 2px solid #00bcd4;
            font-size: 14px;
            line-height: 1.6;
            z-index: 10000;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s ease;
            max-width: 300px;
            box-shadow: 0 4px 20px rgba(0, 188, 212, 0.3);
        `;
        
        document.body.appendChild(this.tooltipElement);
    },
    
    // 启用悬停功能
    enable() {
        if (this.isEnabled) return;
        
        // 等待地图初始化完成
        const enableHover = () => {
            if (!window.mapChart) {
                setTimeout(enableHover, 1000);
                return;
            }
            
            // 添加鼠标事件监听
            window.mapChart.on('mouseover', 'geo', (params) => {
                this.showTooltip(params);
            });
            
            window.mapChart.on('mouseout', 'geo', () => {
                this.hideTooltip();
            });
            
            window.mapChart.on('mousemove', 'geo', (params) => {
                this.updateTooltipPosition(params.event.event);
            });
            
            this.isEnabled = true;
            console.log('✅ 省份悬停事件已绑定');
        };
        
        enableHover();
    },
    
    // 显示tooltip
    showTooltip(params) {
        if (!this.tooltipElement || !params.name) return;

        const provinceName = params.name;
        const provinceData = ProvinceDataManager.getProvinceData(provinceName);

        let content = `<div style="color: #00bcd4; font-weight: bold; margin-bottom: 10px;">📍 ${provinceName}</div>`;

        if (provinceData) {
            // 随机获取50-100个用户数据，但只显示10个姓名
            const randomCount = Math.floor(Math.random() * 51) + 50; // 50-100个随机数量
            const activeUsers = ProvinceDataManager.getActiveUsers(provinceName, randomCount);

            content += `<div style="color: #fce182; margin-bottom: 8px;">👥 在线人数: ${provinceData.count}人</div>`;

            if (activeUsers.length > 0) {
                // 只显示前10个用户姓名，但显示总获取数量
                const displayUsers = activeUsers.slice(0, 10);
                content += `<div style="color: #ffffff; margin-bottom: 5px;">正在使用用户 (获取${activeUsers.length}人，显示${displayUsers.length}人):</div>`;
                content += `<div style="color: #4ade80; font-size: 13px; line-height: 1.4;">`;

                // 显示最多10个用户姓名，每行显示5个
                const names = displayUsers.map(user => user.name);

                // 每行显示5个用户
                for (let i = 0; i < names.length; i += 5) {
                    const row = names.slice(i, i + 5).join('　');
                    content += `${row}<br/>`;
                }

                content += `</div>`;
            } else {
                content += `<div style="color: #95a5a6;">当前无正在使用的用户</div>`;
            }
        } else {
            content += `<div style="color: #95a5a6;">暂无数据</div>`;
        }

        this.tooltipElement.innerHTML = content;
        this.tooltipElement.style.opacity = '1';
    },
    
    // 隐藏tooltip
    hideTooltip() {
        if (this.tooltipElement) {
            this.tooltipElement.style.opacity = '0';
        }
    },
    
    // 更新tooltip位置
    updateTooltipPosition(event) {
        if (!this.tooltipElement || this.tooltipElement.style.opacity === '0') return;
        
        const x = event.clientX;
        const y = event.clientY;
        
        // 计算tooltip位置，避免超出屏幕
        const tooltipRect = this.tooltipElement.getBoundingClientRect();
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        
        let left = x + 15;
        let top = y + 15;
        
        // 右边界检查
        if (left + tooltipRect.width > windowWidth) {
            left = x - tooltipRect.width - 15;
        }
        
        // 下边界检查
        if (top + tooltipRect.height > windowHeight) {
            top = y - tooltipRect.height - 15;
        }
        
        // 确保不超出左边界和上边界
        left = Math.max(10, left);
        top = Math.max(10, top);
        
        this.tooltipElement.style.left = left + 'px';
        this.tooltipElement.style.top = top + 'px';
    },
    
    // 禁用悬停功能
    disable() {
        if (!this.isEnabled) return;
        
        if (window.mapChart) {
            window.mapChart.off('mouseover', 'geo');
            window.mapChart.off('mouseout', 'geo');
            window.mapChart.off('mousemove', 'geo');
        }
        
        this.hideTooltip();
        this.isEnabled = false;
        
        console.log('⏹️ 省份悬停功能已禁用');
    },
    
    // 重新加载数据
    async reloadData() {
        console.log('🔄 重新加载省份数据...');
        await ProvinceDataManager.loadData();
        console.log('✅ 省份数据重新加载完成');
    }
};

// 自动初始化
document.addEventListener('DOMContentLoaded', function() {
    // 延迟初始化，确保地图系统已加载
    setTimeout(() => {
        ProvinceHoverManager.init();
    }, 3000);
});

// 导出到全局作用域
window.ProvinceDataManager = ProvinceDataManager;
window.ProvinceHoverManager = ProvinceHoverManager;

// 开发者控制台帮助
console.log('🗺️ 省份悬停功能已加载');
console.log('💡 控制台命令:');
console.log('  ProvinceHoverManager.enable() - 启用悬停功能');
console.log('  ProvinceHoverManager.disable() - 禁用悬停功能');
console.log('  ProvinceHoverManager.reloadData() - 重新加载数据');
console.log('  ProvinceDataManager.getProvinceData("省份名") - 获取省份数据');
console.log('  ProvinceDataManager.getRandomNames("省份名", 10) - 获取随机姓名');
