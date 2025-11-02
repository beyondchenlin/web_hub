// 全新重构的地图配置系统
// 简化配置，强制颜色设置，确保可靠性

// ========== 全新的配置结构 ==========
const NEW_MAP_CONFIG = {
    // 石家庄中心节点配置
    centerNode: {
        position: [114.48, 38.03],
        name: '石家庄',
        color: '#dc3545',           // 红色
        borderColor: '#dc3545',     // 红色边框 - 与填充色一致
        size: 15,                   // 节点本身大小（适中）
        rippleColor: '#dc3545',     // 扩散颜色（红色）
        rippleScale: 6,             // 大扩散效果（节点本身不变，只是扩散大）
        ripplePeriod: 2,            // 扩散周期
        zlevel: 20                  // 渲染层级
    },
    
    // 普通节点配置
    normalNodes: {
        color: '#fce182',           // 金色 - 强制设置
        borderColor: '#fce182',     // 金色边框 - 与填充色相同  
        size: 10,                   // 节点大小
        rippleColor: '#fce182',     // 扩散颜色（金色）
        rippleScale: 1,             // 扩散保持原始大小
        ripplePeriod: 4,            // 扩散周期
        zlevel: 10                  // 渲染层级
    },
    
    // 飞线配置
    flylines: {
        color: '#fce182',           // 金色
        arrowColor: '#dc3545',      // 红色箭头
        width: 1,                   // 线条宽度
        arrowSize: 5,               // 箭头大小
        period: 4,                  // 动画周期
        curveness: 0.3,             // 弯曲度
        zlevel: 2                   // 渲染层级
    },
    
    // 地图基础配置
    geo: {
        zoom: 1.2,
        backgroundColor: '#1a1e45',
        borderColor: '#22ccfb',
        borderWidth: 1
    }
};

// ========== 真实用户数据 ==========
let REAL_USER_DATA = null;
let REAL_USER_INDEX = 0;

// 加载真实用户数据
async function loadRealUserData() {
    try {
        const response = await fetch('/static/data/map_points.json');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        REAL_USER_DATA = await response.json();
        console.log(`✅ 真实用户数据加载成功: ${REAL_USER_DATA.total_count}个用户`);

        // 打乱用户数组确保随机性
        shuffleArray(REAL_USER_DATA.points);

        return REAL_USER_DATA;
    } catch (error) {
        console.error('❌ 真实用户数据加载失败:', error);
        return null;
    }
}

// 打乱数组
function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
}

// 获取下一个真实用户
function getNextRealUser() {
    if (!REAL_USER_DATA || !REAL_USER_DATA.points || REAL_USER_DATA.points.length === 0) {
        return null;
    }

    const user = REAL_USER_DATA.points[REAL_USER_INDEX];
    REAL_USER_INDEX = (REAL_USER_INDEX + 1) % REAL_USER_DATA.points.length;

    // 如果循环一轮，重新打乱
    if (REAL_USER_INDEX === 0) {
        shuffleArray(REAL_USER_DATA.points);
    }

    return user;
}

// ========== 处理节点数据 ==========
const TEST_NODES_DATA = [
    { name: '上海', position: [121.4648, 31.2891] },
    { name: '北京市', position: [116.4551, 40.2539] },
    { name: '广东', position: [113.12244, 23.009505] },
    { name: '江苏', position: [118.8062, 31.9208] },
    { name: '浙江', position: [119.5313, 29.8773] },
    { name: '四川', position: [103.9526, 30.7617] }
];

// ========== 用户点系统配置 ==========

// 用户点配置
const USER_POINTS_CONFIG = {
    // 外观配置 - 基于普通节点但更小
    appearance: {
        color: '#f4d03f',           // 稍浅的金色，与处理节点区分
        borderColor: '#f4d03f',     // 边框颜色
        size: 4,                    // 进一步减小尺寸
        rippleColor: '#f4d03f',     // 扩散颜色
        rippleScale: 1,             // 扩散保持原始大小，不放大
        ripplePeriod: 4,            // 稍慢的扩散周期
        zlevel: 5                   // 渲染层级（在飞线之上，普通节点之下）
    },

    // 数量控制（数据层800-1000，显示层50-100）
    quantity: {
        totalUsers: 900,            // 总用户数据量（800-1000）
        target: 75,                 // 地图显示目标数量（50-100之间）
        minActive: 50,              // 最少显示数量
        maxActive: 100,             // 最多显示数量
        spawnRate: 5                // 每次生成的显示数量
    },

    // 生命周期配置（平滑自然的出现消失）
    lifecycle: {
        minLifetime: 10000,         // 最短生命周期 10秒（平衡性能和效果）
        maxLifetime: 30000,         // 最长生命周期 30秒（适中）
        fadeInDuration: 4000,       // 渐显时间 4秒（平滑自然）
        fadeOutDuration: 6000       // 渐隐时间 6秒（平滑自然）
    },

    // 飞线配置
    flylines: {
        color: '#f39c12',           // 用户飞线颜色（橙色，与处理节点飞线区分）
        arrowColor: '#e74c3c',      // 箭头颜色（红色）
        width: 1,                   // 线条宽度
        arrowSize: 4,               // 箭头大小（比普通飞线小）
        period: 3,                  // 动画周期（比普通飞线快）
        curveness: 0.2,             // 弯曲度（比普通飞线直一些）
        zlevel: 1                   // 渲染层级（在普通飞线之下）
    }
};

// 全国各省份人口密度权重配置
const POPULATION_WEIGHTS = {
    '广东': 15,     // 人口最多
    '山东': 12,
    '河南': 12,
    '四川': 10,
    '江苏': 10,
    '河北': 9,
    '湖南': 8,
    '安徽': 8,
    '湖北': 7,
    '浙江': 7,
    '广西': 6,
    '云南': 6,
    '江西': 6,
    '辽宁': 5,
    '福建': 5,
    '陕西': 5,
    '黑龙江': 4,
    '山西': 4,
    '贵州': 4,
    '重庆': 4,
    '吉林': 3,
    '甘肃': 3,
    '内蒙古': 3,
    '新疆': 3,
    '上海': 8,     // 直辖市，人口密度高
    '北京': 8,
    '天津': 5,
    '海南': 2,
    '宁夏': 1,
    '青海': 1,
    '西藏': 1,
    '香港': 2,
    '澳门': 1,
    '台湾': 6
};

// 省份坐标数据（用于用户点随机分布）
const PROVINCE_COORDINATES = {
    '北京': [116.4551, 40.2539],
    '天津': [117.4219, 39.4189],
    '上海': [121.4648, 31.2891],
    '重庆': [106.3586, 29.5647],
    '河北': [114.4995, 38.1006],
    '山西': [112.3352, 37.9413],
    '辽宁': [123.1238, 42.1216],
    '吉林': [125.8154, 44.2584],
    '黑龙江': [127.9688, 45.368],
    '江苏': [118.8062, 31.9208],
    '浙江': [119.5313, 29.8773],
    '安徽': [117.29, 32.0581],
    '福建': [119.4543, 25.9222],
    '江西': [116.0046, 28.6633],
    '山东': [117.1582, 36.8701],
    '河南': [113.4668, 34.6234],
    '湖北': [114.3896, 30.6628],
    '湖南': [113.0823, 28.2568],
    '广东': [113.12244, 23.009505],
    '广西': [108.479, 23.1152],
    '海南': [110.3893, 19.8516],
    '四川': [103.9526, 30.7617],
    '贵州': [106.6992, 26.7682],
    '云南': [102.9199, 25.4663],
    '西藏': [91.11, 29.97],
    '陕西': [109.1162, 34.2004],
    '甘肃': [103.5901, 36.3043],
    '青海': [101.4038, 36.8207],
    '宁夏': [106.3586, 38.1775],
    '新疆': [87.9236, 43.5883],
    '内蒙古': [111.4124, 40.4901],
    '香港': [114.2578, 22.3242],
    '澳门': [113.5439, 22.1758],
    '台湾': [121.0254, 23.5986]
};

// 用户点数据结构定义
class UserPoint {
    constructor(id, province, position, targetNode, realName = null, realAddress = null) {
        this.id = id;                           // 唯一标识
        this.province = province;               // 所属省份
        this.position = position;               // 地理坐标 [lng, lat]
        this.targetNode = targetNode;           // 目标节点（7个节点之一）
        this.realName = realName;               // 真实姓名（如果有）
        this.realAddress = realAddress;         // 真实地址（如果有）
        this.isRealUser = !!(realName && realAddress); // 是否为真实用户
        this.createdAt = Date.now();            // 创建时间
        this.lifetime = this.generateLifetime(); // 生命周期（毫秒）
        this.status = 'spawning';               // 状态：spawning, active, fading, dead
        this.opacity = 0;                       // 当前透明度
        this.lastUpdate = Date.now();           // 最后更新时间
        this.fadeStartTime = null;              // 开始消失的时间
        this.transmissionProgress = 0;          // 传输进度 (0-1)
    }

    // 生成完全随机的生命周期（避免批量刷新）
    generateLifetime() {
        const min = USER_POINTS_CONFIG.lifecycle.minLifetime;
        const max = USER_POINTS_CONFIG.lifecycle.maxLifetime;

        // 完全随机分布，每个节点都有不同的生命周期
        const baseLifetime = Math.random() * (max - min) + min;

        // 添加额外的随机扰动，确保绝对不会同时消失
        const randomOffset = (Math.random() - 0.5) * 2000; // ±1秒的随机偏移
        const uniqueOffset = Math.random() * 1000; // 额外的0-1秒偏移

        return Math.floor(baseLifetime + randomOffset + uniqueOffset);
    }

    // 检查是否应该消失
    shouldDie() {
        return Date.now() - this.createdAt >= this.lifetime;
    }

    // 获取剩余生命时间
    getRemainingLife() {
        return Math.max(0, this.lifetime - (Date.now() - this.createdAt));
    }

    // 获取生命周期进度 (0-1)
    getLifecycleProgress() {
        const age = Date.now() - this.createdAt;
        return Math.min(1, age / this.lifetime);
    }

    // 计算传输进度
    updateTransmissionProgress() {
        const progress = this.getLifecycleProgress();
        // 传输在生命周期的中间阶段最活跃
        if (progress < 0.2) {
            this.transmissionProgress = progress * 2.5; // 0-0.5
        } else if (progress < 0.8) {
            this.transmissionProgress = 0.5 + (progress - 0.2) * 0.83; // 0.5-1.0
        } else {
            this.transmissionProgress = Math.max(0, 1 - (progress - 0.8) * 5); // 1.0-0
        }
    }

    // 更新状态（增强版）
    updateStatus() {
        const now = Date.now();
        const age = now - this.createdAt;
        const fadeInDuration = USER_POINTS_CONFIG.lifecycle.fadeInDuration;
        const fadeOutDuration = USER_POINTS_CONFIG.lifecycle.fadeOutDuration;

        // 更新传输进度
        this.updateTransmissionProgress();

        if (age < fadeInDuration) {
            // 渐显阶段
            this.status = 'spawning';
            this.opacity = this.easeInOut(age / fadeInDuration);
        } else if (this.shouldDie()) {
            // 消失阶段
            if (this.status !== 'fading') {
                this.status = 'fading';
                this.fadeStartTime = now;
                // 开始消失时的日志
                if (Math.random() < 0.1) { // 10%概率输出，避免日志过多
                    console.log(`🌅 用户点开始消失: ${this.id} (${this.province})`);
                }
            }
            const fadeAge = now - this.fadeStartTime;
            this.opacity = Math.max(0, 1 - this.easeInOut(fadeAge / fadeOutDuration));

            if (this.opacity <= 0) {
                this.status = 'dead';
            }
        } else {
            // 活跃阶段
            this.status = 'active';
            this.opacity = 1;
        }

        this.lastUpdate = now;
    }

    // 缓动函数，让渐变更平滑自然
    easeInOut(t) {
        // 使用更平滑的三次贝塞尔曲线
        return t * t * (3 - 2 * t);
    }

    // 获取调试信息
    getDebugInfo() {
        return {
            id: this.id,
            province: this.province,
            target: this.targetNode.name,
            status: this.status,
            opacity: this.opacity.toFixed(2),
            age: Math.floor((Date.now() - this.createdAt) / 1000) + 's',
            remaining: Math.floor(this.getRemainingLife() / 1000) + 's',
            progress: (this.getLifecycleProgress() * 100).toFixed(1) + '%',
            transmission: (this.transmissionProgress * 100).toFixed(1) + '%'
        };
    }
}

// 全局用户点管理器 - 增强内存管理
const UserPointsManager = {
    activePoints: new Map(),        // 活跃用户点 Map<id, UserPoint>
    nextId: 1,                      // 下一个ID
    updateTimer: null,              // 更新定时器
    renderTimer: null,              // 渲染定时器
    maintenanceTimer: null,         // 维护定时器
    isRunning: false,               // 是否正在运行
    positionHistory: new Map(),     // 位置历史记录 Map<province, Array<[lng, lat]>>
    timeoutHandles: new Set(),      // 活跃的setTimeout句柄
    intervalHandles: new Set(),     // 活跃的setInterval句柄

    // 获取所有目标节点（6个处理节点 + 1个石家庄中心）
    getAllTargetNodes() {
        const targets = [...TEST_NODES_DATA];  // 6个处理节点
        targets.push({                         // 石家庄中心节点
            name: NEW_MAP_CONFIG.centerNode.name,
            position: NEW_MAP_CONFIG.centerNode.position
        });
        return targets;
    },

    // 根据人口密度权重随机选择省份（优化分散算法）
    selectRandomProvince() {
        const provinces = Object.keys(POPULATION_WEIGHTS);
        const weights = Object.values(POPULATION_WEIGHTS);

        // 获取当前各省份的用户点数量
        const currentDistribution = this.getCurrentProvinceDistribution();

        // 计算调整后的权重（减少已有用户点多的省份的权重）
        const adjustedWeights = provinces.map((province, index) => {
            const currentCount = currentDistribution[province] || 0;
            const baseWeight = weights[index];

            // 如果某省份用户点过多，降低其权重
            const maxAllowed = Math.ceil(this.activePoints.size * (baseWeight / weights.reduce((a, b) => a + b, 0)) * 1.5);
            if (currentCount >= maxAllowed) {
                return Math.max(1, baseWeight * 0.3); // 大幅降低权重但保持最小值
            }

            // 如果某省份用户点过少，增加其权重
            const minExpected = Math.floor(this.activePoints.size * (baseWeight / weights.reduce((a, b) => a + b, 0)) * 0.5);
            if (currentCount < minExpected) {
                return baseWeight * 1.8; // 增加权重
            }

            return baseWeight;
        });

        const totalWeight = adjustedWeights.reduce((sum, weight) => sum + weight, 0);
        let random = Math.random() * totalWeight;

        for (let i = 0; i < provinces.length; i++) {
            random -= adjustedWeights[i];
            if (random <= 0) {
                return provinces[i];
            }
        }
        return provinces[0]; // fallback
    },

    // 获取当前各省份的用户点分布
    getCurrentProvinceDistribution() {
        const distribution = {};
        for (const point of this.activePoints.values()) {
            distribution[point.province] = (distribution[point.province] || 0) + 1;
        }
        return distribution;
    },

    // 在省份内生成随机坐标（增强随机性，确保每次位置不同）
    generateRandomPosition(province) {
        const baseCoord = PROVINCE_COORDINATES[province];
        if (!baseCoord) return [116.4, 39.9]; // 默认北京

        // 根据省份大小调整偏移范围
        const provinceSize = this.getProvinceSize(province);
        const offsetRange = provinceSize.range;

        // 增强随机性，确保每次位置都不同
        const randomSeed = Math.random() * 1000; // 增加随机种子

        // 使用多种分布模式避免聚集，增加随机性
        const distributionMode = Math.random();
        let offsetLng, offsetLat;

        if (distributionMode < 0.3) {
            // 30% 概率：完全随机分布（增大范围）
            offsetLng = (Math.random() - 0.5) * offsetRange.lng * 1.5;
            offsetLat = (Math.random() - 0.5) * offsetRange.lat * 1.5;
        } else if (distributionMode < 0.5) {
            // 20% 概率：环形分布（多个环）
            const angle = Math.random() * 2 * Math.PI;
            const ringIndex = Math.floor(Math.random() * 3); // 3个不同的环
            const radius = (0.2 + ringIndex * 0.3 + Math.random() * 0.2) * Math.min(offsetRange.lng, offsetRange.lat);
            offsetLng = Math.cos(angle) * radius;
            offsetLat = Math.sin(angle) * radius;
        } else if (distributionMode < 0.7) {
            // 20% 概率：网格分布（随机网格点）
            const gridX = Math.floor(Math.random() * 5) - 2; // -2 到 2
            const gridY = Math.floor(Math.random() * 5) - 2;
            offsetLng = gridX * offsetRange.lng / 4 + (Math.random() - 0.5) * offsetRange.lng / 8;
            offsetLat = gridY * offsetRange.lat / 4 + (Math.random() - 0.5) * offsetRange.lat / 8;
        } else {
            // 30% 概率：边缘和角落分布
            const position = Math.floor(Math.random() * 8); // 8个不同位置
            const edgeOffset = 0.6 + Math.random() * 0.3; // 0.6-0.9的边缘位置

            switch (position) {
                case 0: // 上边缘
                    offsetLng = (Math.random() - 0.5) * offsetRange.lng;
                    offsetLat = offsetRange.lat * edgeOffset;
                    break;
                case 1: // 右上角
                    offsetLng = offsetRange.lng * edgeOffset;
                    offsetLat = offsetRange.lat * edgeOffset;
                    break;
                case 2: // 右边缘
                    offsetLng = offsetRange.lng * edgeOffset;
                    offsetLat = (Math.random() - 0.5) * offsetRange.lat;
                    break;
                case 3: // 右下角
                    offsetLng = offsetRange.lng * edgeOffset;
                    offsetLat = -offsetRange.lat * edgeOffset;
                    break;
                case 4: // 下边缘
                    offsetLng = (Math.random() - 0.5) * offsetRange.lng;
                    offsetLat = -offsetRange.lat * edgeOffset;
                    break;
                case 5: // 左下角
                    offsetLng = -offsetRange.lng * edgeOffset;
                    offsetLat = -offsetRange.lat * edgeOffset;
                    break;
                case 6: // 左边缘
                    offsetLng = -offsetRange.lng * edgeOffset;
                    offsetLat = (Math.random() - 0.5) * offsetRange.lat;
                    break;
                case 7: // 左上角
                    offsetLng = -offsetRange.lng * edgeOffset;
                    offsetLat = offsetRange.lat * edgeOffset;
                    break;
            }
        }

        // 添加微小的随机扰动，确保即使是相同模式也有不同位置
        offsetLng += (Math.random() - 0.5) * offsetRange.lng * 0.1;
        offsetLat += (Math.random() - 0.5) * offsetRange.lat * 0.1;

        const newPosition = [
            baseCoord[0] + offsetLng,
            baseCoord[1] + offsetLat
        ];

        // 检查是否与历史位置太接近，如果是则重新生成
        const history = this.positionHistory.get(province) || [];
        const minDistance = 0.05; // 最小距离阈值

        let attempts = 0;
        while (attempts < 5) { // 最多尝试5次
            let tooClose = false;
            for (const histPos of history) {
                const distance = Math.sqrt(
                    Math.pow(newPosition[0] - histPos[0], 2) +
                    Math.pow(newPosition[1] - histPos[1], 2)
                );
                if (distance < minDistance) {
                    tooClose = true;
                    break;
                }
            }

            if (!tooClose) break;

            // 重新生成位置
            offsetLng = (Math.random() - 0.5) * offsetRange.lng * 1.5;
            offsetLat = (Math.random() - 0.5) * offsetRange.lat * 1.5;
            newPosition[0] = baseCoord[0] + offsetLng;
            newPosition[1] = baseCoord[1] + offsetLat;
            attempts++;
        }

        // 记录新位置到历史中
        history.push([newPosition[0], newPosition[1]]);
        // 只保留最近的20个位置
        if (history.length > 20) {
            history.shift();
        }
        this.positionHistory.set(province, history);

        return newPosition;
    },

    // 获取省份大小信息（用于调整分布范围）
    getProvinceSize(province) {
        const sizeMap = {
            // 大省份 - 更大的分布范围
            '新疆': { range: { lng: 3.0, lat: 2.5 } },
            '西藏': { range: { lng: 2.8, lat: 2.3 } },
            '内蒙古': { range: { lng: 2.5, lat: 2.0 } },
            '青海': { range: { lng: 2.2, lat: 1.8 } },
            '四川': { range: { lng: 2.0, lat: 1.8 } },
            '黑龙江': { range: { lng: 2.0, lat: 1.5 } },
            '甘肃': { range: { lng: 2.0, lat: 1.5 } },
            '云南': { range: { lng: 1.8, lat: 1.5 } },
            '广西': { range: { lng: 1.8, lat: 1.3 } },
            '湖南': { range: { lng: 1.5, lat: 1.3 } },
            '陕西': { range: { lng: 1.5, lat: 1.3 } },
            '河北': { range: { lng: 1.5, lat: 1.3 } },
            '吉林': { range: { lng: 1.5, lat: 1.2 } },
            '湖北': { range: { lng: 1.5, lat: 1.2 } },
            '广东': { range: { lng: 1.5, lat: 1.2 } },
            '贵州': { range: { lng: 1.3, lat: 1.2 } },
            '江西': { range: { lng: 1.3, lat: 1.2 } },
            '河南': { range: { lng: 1.3, lat: 1.0 } },
            '山西': { range: { lng: 1.3, lat: 1.0 } },
            '山东': { range: { lng: 1.3, lat: 1.0 } },
            '辽宁': { range: { lng: 1.2, lat: 1.0 } },
            '安徽': { range: { lng: 1.2, lat: 1.0 } },
            '福建': { range: { lng: 1.2, lat: 1.0 } },
            '江苏': { range: { lng: 1.0, lat: 1.0 } },
            '浙江': { range: { lng: 1.0, lat: 1.0 } },
            '重庆': { range: { lng: 1.0, lat: 0.8 } },
            // 小省份/直辖市 - 较小的分布范围
            '宁夏': { range: { lng: 0.8, lat: 0.8 } },
            '海南': { range: { lng: 0.8, lat: 0.8 } },
            '北京': { range: { lng: 0.6, lat: 0.6 } },
            '天津': { range: { lng: 0.6, lat: 0.6 } },
            '上海': { range: { lng: 0.5, lat: 0.5 } },
            '香港': { range: { lng: 0.3, lat: 0.3 } },
            '澳门': { range: { lng: 0.2, lat: 0.2 } },
            '台湾': { range: { lng: 1.0, lat: 1.2 } }
        };

        return sizeMap[province] || { range: { lng: 1.0, lat: 1.0 } }; // 默认中等大小
    },

    // 随机选择目标节点
    selectRandomTarget() {
        const targets = this.getAllTargetNodes();
        return targets[Math.floor(Math.random() * targets.length)];
    },

    // 创建新用户点（使用真实用户数据）
    createUserPoint() {
        const realUser = getNextRealUser();

        if (!realUser) {
            // 如果没有真实用户数据，回退到原始方法
            console.warn('⚠️ 无真实用户数据，回退到随机生成');
            const province = this.selectRandomProvince();
            const position = this.generateRandomPosition(province);
            const targetNode = this.selectRandomTarget();

            const userPoint = new UserPoint(
                `user_${this.nextId++}`,
                province,
                position,
                targetNode
            );

            this.activePoints.set(userPoint.id, userPoint);
            return userPoint;
        }

        // 使用真实用户数据
        const targetNode = this.selectRandomTarget();

        const userPoint = new UserPoint(
            `real_user_${this.nextId++}`,
            realUser.province,
            realUser.coordinates, // 使用真实坐标
            targetNode,
            realUser.name,        // 真实姓名
            realUser.address      // 真实地址
        );

        this.activePoints.set(userPoint.id, userPoint);
        // 适度减少日志输出频率
        if (Math.random() < 0.1) { // 10%概率输出创建日志
            console.log(`👤 创建真实用户点: ${userPoint.id} (${realUser.name} @ ${realUser.province} -> ${targetNode.name})`);
        }
        return userPoint;
    },

    // 批量创建用户点
    createMultipleUserPoints(count) {
        const created = [];
        for (let i = 0; i < count; i++) {
            created.push(this.createUserPoint());
        }
        return created;
    },

    // 更新所有用户点状态（动态平衡版）
    updateAllUserPoints() {
        const deadPoints = [];

        // 更新每个用户点的状态
        for (const [id, point] of this.activePoints) {
            point.updateStatus();
            if (point.status === 'dead') {
                deadPoints.push(id);
            }
        }

        // 移除死亡的用户点，立即安排新的补充（无限循环）- 增强内存管理
        deadPoints.forEach(id => {
            const deadPoint = this.activePoints.get(id);
            if (deadPoint) {
                console.log(`💀 用户点消失: ${id} (${deadPoint.province} -> ${deadPoint.targetNode.name}) 生存${Math.floor((Date.now() - deadPoint.createdAt)/1000)}秒`);
            }
            this.activePoints.delete(id);

            // 安排新用户点在适中随机时间后自然出现 - 管理setTimeout句柄
            const delay = Math.random() * 30000 + 10000; // 10-40秒内随机出现
            const timeoutHandle = setTimeout(() => {
                // 从句柄集合中移除
                this.timeoutHandles.delete(timeoutHandle);
                
                if (this.isRunning) {
                    const newPoint = this.createUserPoint();
                    // 适度减少日志输出频率
                    if (Math.random() < 0.15) { // 15%概率输出
                        console.log(`✨ 循环补充: ${newPoint.id} (${newPoint.province} -> ${newPoint.targetNode.name}) 延迟${Math.floor(delay/1000)}秒`);
                    }
                }
            }, delay);
            
            // 记录句柄以便后续清理
            this.timeoutHandles.add(timeoutHandle);
        });

        return deadPoints.length;
    },

    // 维持动态显示数量（50-100随机变化）
    maintainTargetCount() {
        const currentCount = this.activePoints.size;
        const minCount = USER_POINTS_CONFIG.quantity.minActive;
        const maxCount = USER_POINTS_CONFIG.quantity.maxActive;

        // 动态调整目标数量（在50-100之间随机）
        if (Math.random() < 0.1) { // 10%概率调整目标
            USER_POINTS_CONFIG.quantity.target = Math.floor(Math.random() * (maxCount - minCount) + minCount);
            console.log(`🎲 动态调整显示目标: ${USER_POINTS_CONFIG.quantity.target}个用户点`);
        }

        const targetCount = USER_POINTS_CONFIG.quantity.target;

        // 维持在50-100范围内
        if (currentCount < minCount - 10) {
            // 数量不足，补充一些
            const needed = Math.min(5, targetCount - currentCount);
            this.createStaggeredUserPoints(needed);
            console.log(`📈 补充显示用户点: +${needed} (当前: ${currentCount})`);
        } else if (currentCount > maxCount + 10) {
            // 数量过多，移除一些
            const excess = currentCount - targetCount;
            const toRemove = Math.min(5, excess);
            this.removeExcessUserPoints(toRemove);
            console.log(`📉 移除显示用户点: -${toRemove} (当前: ${currentCount})`);
        }

        // 减少分散检查频率
        if (Math.random() < 0.02) { // 2%概率执行分散检查
            this.enforceDistribution();
        }
    },

    // 错开时间创建用户点（避免同时出现）- 增强内存管理
    createStaggeredUserPoints(count) {
        console.log(`🎯 安排${count}个用户点错开时间创建...`);

        for (let i = 0; i < count; i++) {
            const delay = Math.random() * 10000; // 0-10秒内随机延迟

            const timeoutHandle = setTimeout(() => {
                // 从句柄集合中移除
                this.timeoutHandles.delete(timeoutHandle);
                
                if (this.isRunning) {
                    this.createUserPoint();
                }
            }, delay);
            
            // 记录句柄以便后续清理
            this.timeoutHandles.add(timeoutHandle);
        }
    },

    // 创建平衡的用户点（优先补充到用户点少的省份）
    createBalancedUserPoints(count) {
        const distribution = this.getCurrentProvinceDistribution();
        const provinces = Object.keys(POPULATION_WEIGHTS);

        // 找出用户点数量最少的省份
        const underRepresented = provinces.filter(province => {
            const currentCount = distribution[province] || 0;
            const expectedCount = Math.floor(this.activePoints.size * (POPULATION_WEIGHTS[province] / Object.values(POPULATION_WEIGHTS).reduce((a, b) => a + b, 0)));
            return currentCount < expectedCount * 0.7; // 少于期望值的70%
        });

        for (let i = 0; i < count; i++) {
            let targetProvince;
            if (underRepresented.length > 0 && Math.random() < 0.8) {
                // 80%概率选择代表性不足的省份
                targetProvince = underRepresented[Math.floor(Math.random() * underRepresented.length)];
            } else {
                // 20%概率正常随机选择
                targetProvince = this.selectRandomProvince();
            }

            const position = this.generateRandomPosition(targetProvince);
            const targetNode = this.selectRandomTarget();

            const userPoint = new UserPoint(
                `user_${this.nextId++}`,
                targetProvince,
                position,
                targetNode
            );

            this.activePoints.set(userPoint.id, userPoint);
        }
    },

    // 移除过多的用户点（优先移除聚集省份的用户点）
    removeExcessUserPoints(count) {
        const distribution = this.getCurrentProvinceDistribution();
        const provinces = Object.keys(POPULATION_WEIGHTS);

        // 找出用户点过多的省份
        const overRepresented = [];
        provinces.forEach(province => {
            const currentCount = distribution[province] || 0;
            const expectedCount = Math.floor(this.activePoints.size * (POPULATION_WEIGHTS[province] / Object.values(POPULATION_WEIGHTS).reduce((a, b) => a + b, 0)));
            if (currentCount > expectedCount * 1.3) { // 超过期望值的130%
                // 找出该省份的所有用户点
                const provincePoints = Array.from(this.activePoints.entries())
                    .filter(([id, point]) => point.province === province);
                overRepresented.push(...provincePoints);
            }
        });

        // 优先移除过多省份的用户点
        let removed = 0;
        while (removed < count && overRepresented.length > 0) {
            const randomIndex = Math.floor(Math.random() * overRepresented.length);
            const [id] = overRepresented.splice(randomIndex, 1);
            this.activePoints.delete(id);
            removed++;
            console.log(`📉 移除聚集用户点: ${id}`);
        }

        // 如果还需要移除更多，随机移除
        while (removed < count) {
            const pointIds = Array.from(this.activePoints.keys());
            if (pointIds.length === 0) break;

            const randomId = pointIds[Math.floor(Math.random() * pointIds.length)];
            this.activePoints.delete(randomId);
            removed++;
            console.log(`📉 移除多余用户点: ${randomId}`);
        }
    },

    // 强制执行分散分布
    enforceDistribution() {
        const distribution = this.getCurrentProvinceDistribution();
        const totalPoints = this.activePoints.size;
        const provinces = Object.keys(POPULATION_WEIGHTS);
        const totalWeight = Object.values(POPULATION_WEIGHTS).reduce((a, b) => a + b, 0);

        let needsRebalance = false;

        // 检查是否有省份严重偏离期望分布
        provinces.forEach(province => {
            const currentCount = distribution[province] || 0;
            const expectedCount = Math.floor(totalPoints * (POPULATION_WEIGHTS[province] / totalWeight));
            const deviation = Math.abs(currentCount - expectedCount) / Math.max(expectedCount, 1);

            if (deviation > 0.5) { // 偏差超过50%
                needsRebalance = true;
            }
        });

        if (needsRebalance) {
            console.log('⚖️ 检测到分布不均，执行重新平衡...');
            // 移除一些聚集的点，让系统自然重新分布
            this.removeExcessUserPoints(Math.min(20, Math.floor(totalPoints * 0.05)));
        }
    },

    // 获取当前统计信息
    getStats() {
        const points = Array.from(this.activePoints.values());
        const stats = {
            total: points.length,
            spawning: points.filter(p => p.status === 'spawning').length,
            active: points.filter(p => p.status === 'active').length,
            fading: points.filter(p => p.status === 'fading').length,
            byProvince: {},
            byTarget: {}
        };

        // 按省份统计
        points.forEach(point => {
            stats.byProvince[point.province] = (stats.byProvince[point.province] || 0) + 1;
            stats.byTarget[point.targetNode.name] = (stats.byTarget[point.targetNode.name] || 0) + 1;
        });

        return stats;
    },

    // 启动用户点系统
    start() {
        if (this.isRunning) {
            console.log('⚠️ 用户点系统已在运行');
            return;
        }

        console.log('🚀 启动用户点系统...');
        this.isRunning = true;

        // 分批创建初始用户点，避免一次性创建太多
        this.createInitialUserPoints();

        // 启动定时更新（平衡性能和流畅度）- 管理interval句柄
        this.updateTimer = setInterval(() => {
            this.lifecycleUpdate();
        }, 3000); // 每3秒更新一次，平衡性能和效果
        
        // 记录interval句柄
        this.intervalHandles.add(this.updateTimer);

        console.log('✅ 用户点系统启动完成');
    },

    // 完全随机的用户点创建系统
    createInitialUserPoints() {
        const targetCount = USER_POINTS_CONFIG.quantity.target;

        const totalUsers = USER_POINTS_CONFIG.quantity.totalUsers;

        console.log(`🔄 启动分层用户点系统...`);
        console.log(`📊 数据层: ${totalUsers}个用户（模拟真实用户数据）`);
        console.log(`🎨 显示层: ${targetCount}个用户点（地图可视化）`);
        console.log(`📱 显示范围: ${USER_POINTS_CONFIG.quantity.minActive}-${USER_POINTS_CONFIG.quantity.maxActive}个随机变化`);

        // 只创建显示层的用户点，但模拟更大的数据量 - 管理setTimeout句柄
        for (let i = 0; i < targetCount; i++) {
            // 在60秒内随机分布出现时间
            const delay = Math.random() * 60000;

            const timeoutHandle = setTimeout(() => {
                // 从句柄集合中移除
                this.timeoutHandles.delete(timeoutHandle);
                
                if (this.isRunning) {
                    this.createUserPoint();
                }
            }, delay);
            
            // 记录句柄以便后续清理
            this.timeoutHandles.add(timeoutHandle);
        }

        console.log(`✅ ${targetCount}个显示用户点已安排在60秒内随机出现`);
        console.log(`🔄 每个显示点代表${Math.floor(totalUsers/targetCount)}个真实用户`);
        console.log(`♾️ 显示点消失后立即随机补充，数量在50-100间动态变化`);
        console.log(`💫 模拟${totalUsers}个用户的真实数据传输场景`);
    },

    // 生命周期更新（主要更新循环）
    lifecycleUpdate() {
        try {
            // 更新所有用户点状态
            const removedCount = this.updateAllUserPoints();

            // 维持目标数量
            this.maintainTargetCount();

            // 定期输出详细统计信息（适度频率）
            if (Math.random() < 0.08) { // 8%概率输出统计，平衡信息量
                this.logDetailedStats(removedCount);
            }

            // 显示动态变化（适度减少）
            if (removedCount > 0 && Math.random() < 0.5) { // 50%概率输出动态变化信息
                console.log(`🔄 动态平衡: ${removedCount}个节点消失，${removedCount}个新节点将在5秒内出现`);
            }

            // 内存清理检查
            if (Math.random() < 0.02) { // 2%概率进行内存检查
                this.memoryCleanup();
            }

        } catch (error) {
            console.error('❌ 生命周期更新失败:', error);
        }
    },

    // 输出详细统计信息（增强分布显示）
    logDetailedStats(removedCount) {
        const stats = this.getStats();
        const flylineStats = this.getFlylineStats();
        const distribution = this.getCurrentProvinceDistribution();

        console.log('📊 用户点系统状态:');
        console.log(`  总数: ${stats.total} | 生成中: ${stats.spawning} | 活跃: ${stats.active} | 消失中: ${stats.fading}`);
        console.log(`  本轮移除: ${removedCount} | 飞线数: ${flylineStats.total}`);
        console.log(`  目标分布:`, Object.entries(flylineStats.byTarget)
            .map(([name, count]) => `${name}:${count}`)
            .join(', '));

        // 显示省份分布（只显示用户点数量最多的前10个省份）
        const topProvinces = Object.entries(distribution)
            .sort(([,a], [,b]) => b - a)
            .slice(0, 10);

        if (topProvinces.length > 0) {
            console.log('🗺️ 省份分布 (前10):');
            topProvinces.forEach(([province, count]) => {
                const expectedCount = Math.floor(stats.total * (POPULATION_WEIGHTS[province] / Object.values(POPULATION_WEIGHTS).reduce((a, b) => a + b, 0)));
                const ratio = expectedCount > 0 ? (count / expectedCount).toFixed(1) : 'N/A';
                console.log(`    ${province}: ${count}个 (期望:${expectedCount}, 比例:${ratio})`);
            });
        }
    },

    // 内存清理
    memoryCleanup() {
        const beforeSize = this.activePoints.size;

        // 强制清理已死亡但未移除的点（防御性编程）
        const deadPoints = [];
        for (const [id, point] of this.activePoints) {
            if (point.status === 'dead' ||
                Date.now() - point.createdAt > point.lifetime + 10000) { // 超时10秒强制清理
                deadPoints.push(id);
            }
        }

        deadPoints.forEach(id => this.activePoints.delete(id));

        if (deadPoints.length > 0) {
            console.log(`🧹 内存清理: 移除${deadPoints.length}个僵尸用户点`);
        }

        // 检查内存使用情况
        const afterSize = this.activePoints.size;
        if (afterSize > USER_POINTS_CONFIG.quantity.maxActive * 1.5) {
            console.warn(`⚠️ 用户点数量异常: ${afterSize}, 执行紧急清理`);
            this.emergencyCleanup();
        }
    },

    // 紧急清理（当用户点数量异常时）
    emergencyCleanup() {
        const targetSize = USER_POINTS_CONFIG.quantity.target;
        const currentSize = this.activePoints.size;

        if (currentSize <= targetSize) return;

        // 按创建时间排序，移除最老的点
        const points = Array.from(this.activePoints.entries())
            .sort(([,a], [,b]) => a.createdAt - b.createdAt);

        const toRemove = currentSize - targetSize;
        for (let i = 0; i < toRemove; i++) {
            const [id] = points[i];
            this.activePoints.delete(id);
        }

        console.log(`🚨 紧急清理完成: 移除${toRemove}个用户点`);
    },

    // 停止用户点系统 - 增强内存管理
    stop() {
        if (!this.isRunning) {
            console.log('⚠️ 用户点系统未运行');
            return;
        }

        console.log('🛑 停止用户点系统...');
        this.isRunning = false;

        // 清理所有定时器
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
            this.intervalHandles.delete(this.updateTimer);
            this.updateTimer = null;
        }

        if (this.renderTimer) {
            clearInterval(this.renderTimer);
            this.intervalHandles.delete(this.renderTimer);
            this.renderTimer = null;
        }

        if (this.maintenanceTimer) {
            clearInterval(this.maintenanceTimer);
            this.intervalHandles.delete(this.maintenanceTimer);
            this.maintenanceTimer = null;
        }

        // 清理所有setTimeout句柄
        this.timeoutHandles.forEach(handle => {
            clearTimeout(handle);
        });
        this.timeoutHandles.clear();

        // 清理所有setInterval句柄
        this.intervalHandles.forEach(handle => {
            clearInterval(handle);
        });
        this.intervalHandles.clear();

        // 清空所有用户点和位置历史
        this.activePoints.clear();
        this.positionHistory.clear();
        
        console.log('✅ 用户点系统已停止，所有定时器已清理');
    },

    // 清理内存泄漏 - 新增方法
    cleanupMemoryLeaks() {
        console.log('🧹 执行内存泄漏清理...');
        
        // 清理过期的timeout句柄（防御性编程）
        const timeoutsCleaned = this.timeoutHandles.size;
        this.timeoutHandles.forEach(handle => {
            clearTimeout(handle);
        });
        this.timeoutHandles.clear();

        // 清理无效的interval句柄
        const intervalsCleaned = this.intervalHandles.size;
        this.intervalHandles.forEach(handle => {
            clearInterval(handle);
        });
        this.intervalHandles.clear();

        // 清理位置历史记录中的过期数据
        let positionsCleared = 0;
        this.positionHistory.forEach((history, province) => {
            if (history.length > 50) { // 超过50个位置记录时清理
                const keepCount = 20; // 只保留最近20个
                history.splice(0, history.length - keepCount);
                positionsCleared += history.length - keepCount;
            }
        });

        console.log(`🧹 内存清理完成: 清理${timeoutsCleaned}个超时句柄, ${intervalsCleaned}个间隔句柄, ${positionsCleared}个位置记录`);
        
        return {
            timeoutsCleaned,
            intervalsCleaned,
            positionsCleared
        };
    },

    // 重启用户点系统
    restart() {
        this.stop();
        setTimeout(() => this.start(), 1000);
    },

    // 获取用于渲染的用户点数据
    getRenderData() {
        return Array.from(this.activePoints.values())
            .filter(point => point.status === 'active' || point.status === 'spawning' || point.status === 'fading')
            .map(point => ({
                name: point.realName || `用户_${point.id}`, // 使用真实姓名
                value: point.position, // 只传递坐标
                // 保存原始数据用于飞线生成
                _userPoint: point
            }));
    },

    // 获取用于渲染的飞线数据
    getFlylineData() {
        return Array.from(this.activePoints.values())
            .filter(point => point.status === 'active' || point.status === 'fading')
            .map(point => {
                // 为每条飞线添加额外的样式信息
                const flyline = [
                    { coord: point.position },
                    { coord: point.targetNode.position }
                ];

                // 根据目标节点类型调整飞线样式
                const isToCenter = point.targetNode.name === NEW_MAP_CONFIG.centerNode.name;
                flyline.lineStyle = {
                    color: isToCenter ? '#e67e22' : USER_POINTS_CONFIG.flylines.color, // 到中心的飞线用不同颜色
                    width: isToCenter ? 1.5 : USER_POINTS_CONFIG.flylines.width,
                    opacity: point.opacity * 0.8 // 根据用户点透明度调整飞线透明度
                };

                flyline.effect = {
                    color: isToCenter ? '#c0392b' : USER_POINTS_CONFIG.flylines.arrowColor,
                    symbolSize: isToCenter ? 5 : USER_POINTS_CONFIG.flylines.arrowSize
                };

                return flyline;
            });
    },

    // 获取飞线统计信息
    getFlylineStats() {
        const points = Array.from(this.activePoints.values())
            .filter(point => point.status === 'active' || point.status === 'fading');

        const stats = {
            total: points.length,
            toCenter: 0,
            toProcessingNodes: 0,
            byTarget: {}
        };

        points.forEach(point => {
            const targetName = point.targetNode.name;
            stats.byTarget[targetName] = (stats.byTarget[targetName] || 0) + 1;

            if (targetName === NEW_MAP_CONFIG.centerNode.name) {
                stats.toCenter++;
            } else {
                stats.toProcessingNodes++;
            }
        });

        return stats;
    }
};

// ========== 核心重构函数 ==========

/**
 * 创建石家庄中心节点系列
 */
function createNewCenterNode() {
    const config = NEW_MAP_CONFIG.centerNode;
    
    return {
        type: 'effectScatter',
        coordinateSystem: 'geo',
        zlevel: config.zlevel,
        rippleEffect: {
            show: true,
            period: config.ripplePeriod,
            scale: config.rippleScale,
            brushType: 'stroke',
            color: config.rippleColor
        },
        symbol: 'circle',
        symbolSize: config.size,
        itemStyle: {
            color: config.color,
            borderColor: config.borderColor,
            borderWidth: 2,
            opacity: 1
        },
        data: [{
            name: config.name,
            value: config.position.concat([100]),
            itemStyle: {
                color: config.color,
                borderColor: config.borderColor,
                borderWidth: 2,
                opacity: 1
            }
        }]
    };
}

/**
 * 创建普通节点系列 - 强制金色
 */
function createNewNormalNodes() {
    const config = NEW_MAP_CONFIG.normalNodes;
    
    return {
        type: 'effectScatter',
        coordinateSystem: 'geo',
        zlevel: config.zlevel,
        rippleEffect: {
            show: true,
            period: config.ripplePeriod,
            scale: config.rippleScale,
            brushType: 'stroke',
            color: config.rippleColor
        },
        symbol: 'circle',
        symbolSize: config.size,
        itemStyle: {
            color: config.color,        // 强制金色
            borderColor: config.borderColor,
            borderWidth: 1,
            opacity: 1
        },
        data: TEST_NODES_DATA.map(node => ({
            name: node.name,
            value: node.position.concat([Math.floor(Math.random() * 5) + 1]),
            itemStyle: {
                color: config.color,    // 每个数据点也强制金色
                borderColor: config.borderColor,
                borderWidth: 1,
                opacity: 1
            }
        }))
    };
}

/**
 * 创建基础飞线系列 - 永久显示的金色飞线
 */
function createNewFlylines() {
    const config = NEW_MAP_CONFIG.flylines;
    const centerPos = NEW_MAP_CONFIG.centerNode.position;

    // 生成基础飞线数据
    const flylineData = TEST_NODES_DATA.map(node => ([
        { coord: node.position },
        { coord: centerPos }
    ]));

    return {
        name: '基础飞线', // 明确命名，避免被覆盖
        type: 'lines',
        coordinateSystem: 'geo',
        zlevel: config.zlevel + 10, // 大幅提高层级，确保在最顶层
        silent: true, // 防止交互干扰
        progressive: 0, // 禁用渐进渲染，确保立即显示
        progressiveThreshold: 1, // 强制立即渲染
        effect: {
            show: true,
            period: config.period,
            trailLength: 0,
            symbol: 'arrow',
            symbolSize: config.arrowSize,
            color: config.arrowColor,
            constantSpeed: 40, // 添加恒定速度，确保动画连续性
            loop: true // 确保动画循环
        },
        lineStyle: {
            color: config.color,
            width: config.width,
            opacity: 1,
            curveness: config.curveness
        },
        data: flylineData,
        // 强化永久显示设置
        animation: true,
        animationDuration: 0, // 立即显示，无淡入动画
        animationDelay: 0, // 无延迟
        animationEasing: 'linear', // 线性动画，更稳定
        z: 999, // 最高层级，确保绝对不被覆盖
        // 标记为受保护的系列 - 增强标记
        _isProtected: true,
        _seriesType: 'basicFlylines',
        _permanentDisplay: true, // 新增：永久显示标记
        _lastRefresh: Date.now() // 最后刷新时间
    };
}

// ========== 用户点渲染系统 ==========

/**
 * 创建用户点系列
 */
function createUserPointsSeries() {
    const config = USER_POINTS_CONFIG.appearance;

    return {
        name: '用户点',
        type: 'scatter',
        coordinateSystem: 'geo',
        zlevel: 25, // 提高层级，确保显示在地图点位之上
        symbol: 'none', // 不显示符号，只显示标签
        symbolSize: 0,   // 符号大小为0
        label: {
            show: true,
            position: 'inside',
            formatter: function(params) {
                // 显示用户姓名
                return params.data.name || '用户';
            },
            color: '#ffffff',
            fontSize: 12,
            fontWeight: 'bold',
            textBorderColor: '#000000',
            textBorderWidth: 1
        },
        itemStyle: {
            opacity: 0 // 完全透明，不显示点
        },
        data: [] // 初始为空，将通过updateUserPoints动态更新
    };
}

/**
 * 创建用户飞线系列
 */
function createUserFlylinesSeries() {
    const config = USER_POINTS_CONFIG.flylines;

    return {
        name: '用户飞线',
        type: 'lines',
        coordinateSystem: 'geo',
        zlevel: config.zlevel,
        effect: {
            show: true,
            period: config.period,
            trailLength: 0,
            symbol: 'arrow',
            symbolSize: function(value) {
                // 支持动态箭头大小
                return value.effect ? value.effect.symbolSize : config.arrowSize;
            },
            color: function(params) {
                // 支持动态箭头颜色
                const data = params.data;
                return data.effect ? data.effect.color : config.arrowColor;
            }
        },
        lineStyle: {
            color: function(params) {
                // 支持动态线条颜色
                const data = params.data;
                return data.lineStyle ? data.lineStyle.color : config.color;
            },
            width: function(params) {
                // 支持动态线条宽度
                const data = params.data;
                return data.lineStyle ? data.lineStyle.width : config.width;
            },
            opacity: function(params) {
                // 支持动态透明度
                const data = params.data;
                return data.lineStyle ? data.lineStyle.opacity : 0.8;
            },
            curveness: config.curveness
        },
        data: [] // 初始为空，将通过updateUserPoints动态更新
    };
}

/**
 * 创建用户飞线动画增强版本
 */
function createEnhancedUserFlylines() {
    const config = USER_POINTS_CONFIG.flylines;

    return {
        name: '用户飞线增强',
        type: 'lines',
        coordinateSystem: 'geo',
        zlevel: config.zlevel - 0.5, // 稍微降低层级，避免遮挡
        effect: {
            show: true,
            period: config.period * 1.5, // 稍慢的动画
            trailLength: 0.1, // 添加轨迹效果
            symbol: 'circle',
            symbolSize: 2,
            color: '#3498db' // 蓝色轨迹点
        },
        lineStyle: {
            color: 'rgba(52, 152, 219, 0.3)', // 半透明蓝色背景线
            width: 0.5,
            opacity: 0.6,
            curveness: config.curveness
        },
        data: [] // 将与主飞线数据同步
    };
}

/**
 * 更新用户点和飞线数据
 */
function updateUserPointsData() {
    if (!window.mapChart || !UserPointsManager.isRunning) {
        return;
    }

    try {
        // 获取当前用户点数据
        const userPointsData = UserPointsManager.getRenderData();
        const userFlylinesData = UserPointsManager.getFlylineData();

        // 为增强飞线准备简化数据（只要坐标，不要样式）
        const enhancedFlylinesData = userFlylinesData.map(flyline => [
            flyline[0], flyline[1] // 只保留坐标数据
        ]);

        // 更新地图数据 - 智能保护基础飞线
        const currentOption = window.mapChart.getOption();
        const currentSeries = currentOption.series || [];
        
        // 详细检查基础飞线状态
        let hasBasicFlylines = false;
        let basicFlylinesInfo = null;
        for (let i = 0; i < currentSeries.length; i++) {
            const series = currentSeries[i];
            if (series.name === '基础飞线' || series._seriesType === 'basicFlylines') {
                hasBasicFlylines = true;
                basicFlylinesInfo = {
                    index: i,
                    name: series.name,
                    dataCount: series.data ? series.data.length : 0,
                    hasEffect: series.effect && series.effect.show
                };
                break;
            }
        }
        
        // 调试输出（偶尔输出，避免日志过多）
        if (Math.random() < 0.05) { // 5%概率输出调试信息
            console.log('🔍 updateUserPointsData 调试:', {
                currentSeriesCount: currentSeries.length,
                hasBasicFlylines,
                basicFlylinesInfo,
                userPointsCount: userPointsData.length,
                userFlylinesCount: userFlylinesData.length
            });
        }
        
        // 如果基础飞线缺失，先恢复它们
        if (!hasBasicFlylines) {
            console.warn('⚠️ 用户点更新时发现基础飞线缺失，正在恢复...');
            ensureBasicFlylinesVisible();
            // 短暂延迟后再更新用户点
            setTimeout(() => updateUserPointsData(), 500);
            return;
        }
        
        // 检查基础飞线数据是否完整
        if (basicFlylinesInfo && basicFlylinesInfo.dataCount !== TEST_NODES_DATA.length) {
            console.warn(`⚠️ 基础飞线数据不完整: 期望${TEST_NODES_DATA.length}条，实际${basicFlylinesInfo.dataCount}条`);
            ensureBasicFlylinesVisible();
            setTimeout(() => updateUserPointsData(), 500);
            return;
        }
        
        // 更新前的系列状态
        const beforeUpdate = currentSeries.map(s => ({ name: s.name, type: s.type, dataCount: s.data?.length || 0 }));
        
        // 使用超安全的更新方式：严格保护基础飞线，只更新用户相关系列
        const updatedOption = window.mapChart.getOption();
        const updatedSeries = [...(updatedOption.series || [])];
        
        // 先确保基础飞线的完整性和位置
        let basicFlylinesIndex = -1;
        let basicFlylinesData = null;
        
        for (let i = 0; i < updatedSeries.length; i++) {
            const series = updatedSeries[i];
            if (series.name === '基础飞线' || series._seriesType === 'basicFlylines' || series._permanentDisplay) {
                basicFlylinesIndex = i;
                basicFlylinesData = series;
                break;
            }
        }
        
        // 如果基础飞线存在，强制刷新其配置以确保永久显示
        if (basicFlylinesIndex >= 0 && basicFlylinesData) {
            const refreshedBasicFlylines = createNewFlylines();
            updatedSeries[basicFlylinesIndex] = {
                ...refreshedBasicFlylines,
                _lastRefresh: Date.now() // 更新刷新时间
            };
            console.log('🔧 基础飞线已强制刷新，确保永久显示');
        }
        
        // 找到并更新用户相关系列的索引 - 严格避免影响基础飞线
        const userSeriesUpdates = {
            '用户飞线增强': enhancedFlylinesData,
            '用户飞线': userFlylinesData,
            '用户点': userPointsData
        };
        
        // 更新现有的用户系列，但绝对不触碰基础飞线
        Object.keys(userSeriesUpdates).forEach(seriesName => {
            let seriesIndex = -1;
            for (let i = 0; i < updatedSeries.length; i++) {
                const series = updatedSeries[i];
                // 严格检查：不是基础飞线才允许更新
                if (series.name === seriesName && 
                    series.name !== '基础飞线' && 
                    series._seriesType !== 'basicFlylines' && 
                    !series._permanentDisplay) {
                    seriesIndex = i;
                    break;
                }
            }
            
            if (seriesIndex >= 0) {
                // 更新现有系列的数据，但保持所有其他属性
                updatedSeries[seriesIndex] = {
                    ...updatedSeries[seriesIndex],
                    data: userSeriesUpdates[seriesName],
                    _lastUpdate: Date.now() // 记录更新时间
                };
            } else {
                // 如果系列不存在，创建新的（通常不应该发生）
                console.warn(`⚠️ 用户系列 "${seriesName}" 不存在，创建新的`);
                // 这里可以根据需要创建相应的系列配置
            }
        });
        
        // 使用安全的系列配置进行更新，绝对保护基础飞线
        window.mapChart.setOption({
            series: updatedSeries
        }, false, true); // 使用 lazyUpdate: true 进一步减少对现有系列的影响
        
        // 更新后验证基础飞线是否还存在
        setTimeout(() => {
            const afterOption = window.mapChart.getOption();
            const afterSeries = afterOption.series || [];
            
            let stillHasBasicFlylines = false;
            for (const series of afterSeries) {
                if (series.name === '基础飞线' || series._seriesType === 'basicFlylines') {
                    stillHasBasicFlylines = true;
                    break;
                }
            }
            
            if (!stillHasBasicFlylines) {
                console.error('🚨 严重问题：用户点更新后基础飞线消失了！');
                console.log('更新前系列:', beforeUpdate);
                console.log('更新后系列:', afterSeries.map(s => ({ name: s.name, type: s.type, dataCount: s.data?.length || 0 })));
                
                // 立即恢复
                ensureBasicFlylinesVisible();
            }
        }, 100); // 100ms后检查

        // 定期输出飞线统计（调试用，适度频率）
        if (Math.random() < 0.02) { // 2%概率输出
            const flylineStats = UserPointsManager.getFlylineStats();
            console.log('✈️ 飞线统计:', flylineStats);
        }

    } catch (error) {
        console.error('❌ 更新用户点数据失败:', error);
    }
}

/**
 * 启动用户点渲染更新循环
 */
function startUserPointsRendering() {
    console.log('🎨 启动用户点渲染系统...');

    // 先动态添加用户飞线系列到地图中
    if (window.mapChart) {
        console.log('📍 动态添加用户飞线系列...');
        
        const currentOption = window.mapChart.getOption();
        const currentSeries = [...(currentOption.series || [])];
        
        // 检查是否已经存在用户飞线系列
        const hasUserFlylines = currentSeries.some(s => s.name === '用户飞线');
        const hasEnhancedFlylines = currentSeries.some(s => s.name === '用户飞线增强');
        
        // 只添加不存在的系列
        if (!hasEnhancedFlylines) {
            currentSeries.push(createEnhancedUserFlylines());
            console.log('➕ 添加用户飞线增强系列');
        }
        
        if (!hasUserFlylines) {
            currentSeries.push(createUserFlylinesSeries());
            console.log('➕ 添加用户飞线系列');
        }
        
        // 更新地图配置
        window.mapChart.setOption({
            series: currentSeries
        }, false);
        
        console.log('✅ 用户飞线系列添加完成');
    }

    // 启动用户点管理器
    UserPointsManager.start();

    // 启动渲染更新循环（平衡性能和流畅度）- 管理interval句柄
    const renderUpdateInterval = setInterval(() => {
        if (!UserPointsManager.isRunning) {
            clearInterval(renderUpdateInterval);
            UserPointsManager.intervalHandles.delete(renderUpdateInterval);
            console.log('🛑 用户点渲染更新已停止');
            return;
        }

        updateUserPointsData();
    }, 4000); // 每4秒更新一次渲染，平衡性能和效果

    // 记录渲染定时器句柄
    UserPointsManager.renderTimer = renderUpdateInterval;
    UserPointsManager.intervalHandles.add(renderUpdateInterval);

    console.log('✅ 用户点渲染系统启动完成');
    return renderUpdateInterval;
}

/**
 * 确保基础飞线始终显示且连续动画
 */
function ensureBasicFlylinesVisible() {
    if (!window.mapChart) return;

    try {
        // 创建新的基础飞线配置
        const basicFlylines = createNewFlylines();
        
        // 获取当前配置
        const option = window.mapChart.getOption();
        const series = option.series || [];

        // 查找基础飞线系列
        let basicFlylinesIndex = -1;
        let foundBasicFlylines = false;
        
        for (let i = 0; i < series.length; i++) {
            const s = series[i];
            if (s.type === 'lines' && (s.name === '基础飞线' || s._seriesType === 'basicFlylines' || 
                (s.name !== '用户飞线' && s.name !== '用户飞线增强'))) {
                basicFlylinesIndex = i;
                foundBasicFlylines = true;
                break;
            }
        }
        
        if (foundBasicFlylines) {
            // 更新现有的基础飞线系列，保持动画连续性
            series[basicFlylinesIndex] = {
                ...series[basicFlylinesIndex], // 保持现有属性
                ...basicFlylines, // 更新关键属性
                // 强制确保关键属性正确
                name: '基础飞线',
                data: basicFlylines.data,
                effect: basicFlylines.effect,
                lineStyle: basicFlylines.lineStyle,
                _isProtected: true,
                _seriesType: 'basicFlylines',
                _lastUpdated: Date.now()
            };
            
            console.log('🔧 基础飞线已更新维护');
        } else {
            // 基础飞线系列不存在，重新添加
            console.warn('⚠️ 基础飞线系列丢失，重新添加到地图...');
            
            // 找到合适的插入位置（在用户相关系列之前）
            let insertIndex = series.length;
            for (let i = 0; i < series.length; i++) {
                if (series[i].name === '用户飞线' || series[i].name === '用户点' || series[i].name === '用户飞线增强') {
                    insertIndex = i;
                    break;
                }
            }
            
            // 插入基础飞线系列
            series.splice(insertIndex, 0, basicFlylines);
        }

        // 使用 notMerge: false 来保持动画连续性，避免重新初始化动画
        window.mapChart.setOption({
            series: series
        }, false);
        
        // 验证更新是否成功
        setTimeout(() => {
            const updatedOption = window.mapChart.getOption();
            const updatedSeries = updatedOption.series || [];
            
            let verifySuccess = false;
            for (const s of updatedSeries) {
                if (s.name === '基础飞线' && s.data && s.data.length === TEST_NODES_DATA.length) {
                    verifySuccess = true;
                    break;
                }
            }
            
            if (!verifySuccess) {
                console.warn('⚠️ 基础飞线更新验证失败，将在下次维护周期重试');
            }
        }, 1000);
        
    } catch (error) {
        console.error('❌ 确保基础飞线显示失败:', error);
        
        // 失败时尝试完全重新初始化地图
        if (Math.random() < 0.1) { // 10%概率执行完全重新初始化，避免频繁操作
            console.log('🔄 基础飞线维护失败，尝试重新初始化地图...');
            setTimeout(() => {
                initNewMap();
            }, 2000);
        }
    }
}

/**
 * 验证基础飞线的完整性
 */
function verifyBasicFlylinesIntegrity() {
    if (!window.mapChart) return;

    try {
        const option = window.mapChart.getOption();
        const series = option.series;
        
        // 查找基础飞线系列
        let basicFlylinesFound = false;
        let basicFlylinesIndex = -1;
        
        for (let i = 0; i < series.length; i++) {
            const s = series[i];
            if (s.type === 'lines' && (s.name === '基础飞线' || (s.name !== '用户飞线' && s.name !== '用户飞线增强'))) {
                basicFlylinesFound = true;
                basicFlylinesIndex = i;
                
                // 检查数据是否存在且完整
                if (!s.data || s.data.length === 0) {
                    console.warn('⚠️ 基础飞线数据丢失，正在恢复...');
                    ensureBasicFlylinesVisible();
                    return;
                }
                
                // 检查数据数量是否正确（应该有6条飞线，从6个处理节点到石家庄）
                if (s.data.length !== TEST_NODES_DATA.length) {
                    console.warn(`⚠️ 基础飞线数量不正确: 期望${TEST_NODES_DATA.length}条，实际${s.data.length}条`);
                    ensureBasicFlylinesVisible();
                    return;
                }
                
                // 检查动画效果是否存在
                if (!s.effect || !s.effect.show) {
                    console.warn('⚠️ 基础飞线动画效果丢失，正在恢复...');
                    ensureBasicFlylinesVisible();
                    return;
                }
                
                break;
            }
        }
        
        if (!basicFlylinesFound) {
            console.warn('⚠️ 基础飞线系列丢失，正在重新创建...');
            // 重新创建整个地图
            initNewMap();
        } else {
            // 适度减少日志输出
            if (Math.random() < 0.1) { // 10%概率输出状态
                console.log(`✅ 基础飞线完整性检查通过: 第${basicFlylinesIndex}个系列，${series[basicFlylinesIndex].data.length}条飞线`);
            }
        }
        
    } catch (error) {
        console.error('❌ 基础飞线完整性检查失败:', error);
        // 出错时强制重新初始化
        ensureBasicFlylinesVisible();
    }
}

/**
 * 定期维护基础飞线的连续性 - 管理interval句柄
 */
function startBasicFlylinesMaintenace() {
    // 超高频检查基础飞线状态 - 改为5秒检查，确保飞线绝对不消失
    const maintenanceInterval = setInterval(() => {
        ensureBasicFlylinesVisible();
        
        // 每次都进行完整性检查，不再使用随机概率
        verifyBasicFlylinesIntegrity();
        
        // 额外的强制刷新检查
        if (window.mapChart) {
            const option = window.mapChart.getOption();
            const series = option.series || [];
            
            let basicFlylinesFound = false;
            for (const s of series) {
                if (s.name === '基础飞线' || s._seriesType === 'basicFlylines' || s._permanentDisplay) {
                    basicFlylinesFound = true;
                    // 检查动画效果是否正常
                    if (!s.effect || !s.effect.show) {
                        console.warn('⚠️ 检测到基础飞线动画效果异常，立即修复...');
                        ensureBasicFlylinesVisible();
                    }
                    break;
                }
            }
            
            if (!basicFlylinesFound) {
                console.error('🚨 严重：维护检查发现基础飞线完全消失！立即恢复...');
                ensureBasicFlylinesVisible();
            }
        }
    }, 5000); // 改为每5秒检查一次，更激进地保护基础飞线

    // 记录维护定时器句柄
    UserPointsManager.maintenanceTimer = maintenanceInterval;
    UserPointsManager.intervalHandles.add(maintenanceInterval);

    console.log('🔧 基础飞线超强维护系统已启动 (5秒间隔，100%保护)');
    return maintenanceInterval;
}

/**
 * 停止用户点渲染系统
 */
function stopUserPointsRendering() {
    console.log('🛑 停止用户点渲染系统...');
    UserPointsManager.stop();

    // 清空地图上的用户点数据
    if (window.mapChart) {
        window.mapChart.setOption({
            series: [
                {
                    name: '用户飞线',
                    data: []
                },
                {
                    name: '用户点',
                    data: []
                }
            ]
        }, false);
    }

    console.log('✅ 用户点渲染系统已停止');
}

/**
 * 初始化新的地图系统（集成用户点功能）
 */
async function initNewMap(containerId = 'map', enableUserPoints = true) {
    console.log('🚀 初始化全新重构的地图系统...');

    // 检查DOM元素是否存在
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`❌ 地图容器元素 "${containerId}" 不存在`);
        return null;
    }

    // 检查ECharts是否加载
    if (typeof echarts === 'undefined') {
        console.error('❌ ECharts库未加载');
        return null;
    }

    try {
        // 加载真实用户数据
        if (!REAL_USER_DATA) {
            console.log('📍 正在加载真实用户数据...');
            await loadRealUserData();
        }

        // 停止现有的用户点系统
        if (UserPointsManager.isRunning) {
            UserPointsManager.stop();
        }

        // 销毁旧的地图实例
        if (window.mapChart) {
            window.mapChart.dispose();
        }

        // 创建新的地图实例（添加错误处理）
        window.mapChart = echarts.init(container);
        
        if (!window.mapChart) {
            throw new Error('ECharts实例创建失败');
        }

    const geoConfig = NEW_MAP_CONFIG.geo;

    // 构建系列数组
    const series = [];

    // 核心系列：基础飞线 + 节点（总是存在）
    series.push(createNewFlylines());           // zlevel: 2 - 基础飞线
    series.push(createNewNormalNodes());        // zlevel: 10
    series.push(createNewCenterNode());         // zlevel: 20
    
    // 用户点系列：只在启用时才创建（避免空系列干扰）
    if (enableUserPoints) {
        series.push(createUserPointsSeries());      // zlevel: 5
        // 用户飞线系列将在用户点系统启动时动态添加，避免初始化时的空数据干扰
    }

    const option = {
        // 强制颜色调色盘，确保不受主题影响
        color: [
            NEW_MAP_CONFIG.normalNodes.color,      // 金色
            NEW_MAP_CONFIG.centerNode.color,       // 红色
            NEW_MAP_CONFIG.flylines.color,         // 金色
            USER_POINTS_CONFIG.appearance.color,   // 用户点颜色
            USER_POINTS_CONFIG.flylines.color      // 用户飞线颜色
        ],

        tooltip: {
            trigger: 'item',
            formatter: function(params) {
                // 自定义tooltip格式
                if (params.seriesName === '用户点') {
                    const point = params.data._userPoint;
                    if (point) {
                        return `用户点<br/>
                                省份: ${point.province}<br/>
                                目标: ${point.targetNode.name}<br/>
                                状态: ${point.status}<br/>
                                进度: ${(point.getLifecycleProgress() * 100).toFixed(1)}%`;
                    }
                }
                return params.name || params.seriesName;
            },
            backgroundColor: 'rgba(0,0,0,0.8)',
            borderColor: '#22ccfb',
            borderWidth: 1,
            textStyle: {
                color: '#ffffff',
                fontSize: 12
            }
        },

        geo: {
            map: 'china',
            zoom: geoConfig.zoom,
            roam: false,
            itemStyle: {
                color: geoConfig.backgroundColor,    // 🎨 正常状态：保持原来的深蓝色背景
                borderColor: geoConfig.borderColor,  // 🎨 正常状态：保持原来的青色边框
                borderWidth: geoConfig.borderWidth
            },
            label: {
                show: true,                    // 显示省份名称
                color: '#ffffff',              // 省份名称颜色（白色）
                fontSize: 11,                  // 字体大小
                fontWeight: 'normal',          // 字体粗细
                fontFamily: 'Microsoft YaHei, Arial, sans-serif'
            },
            emphasis: {
                itemStyle: {
                    color: '#00bcd4',                      // 🎨 鼠标悬停时：100%不透明的界面主题蓝色填充
                    borderColor: '#00bcd4',                // 🎨 鼠标悬停时：100%不透明的界面主题蓝色描边
                    borderWidth: 2                         // 悬停时边框加粗
                },
                label: {
                    show: true,                // 悬停时显示省份名称
                    color: '#1a1e45',          // 悬停时省份名称颜色（深蓝色，在金色背景上清晰）
                    fontSize: 13,              // 悬停时字体稍大
                    fontWeight: 'bold',        // 悬停时字体加粗
                    fontFamily: 'Microsoft YaHei, Arial, sans-serif'
                }
            }
        },

        series: series
    };

        window.mapChart.setOption(option);

        // 启动基础飞线维护系统（确保飞线连续性）
        startBasicFlylinesMaintenace();
        
        // 立即验证基础飞线是否正确创建
        setTimeout(() => {
            console.log('🔍 验证基础飞线初始状态...');
            const debugResult = debugBasicFlylines();
            if (!debugResult || !debugResult.found) {
                console.warn('⚠️ 初始化后基础飞线未找到，立即修复...');
                ensureBasicFlylinesVisible();
            }
        }, 1000);
        
        // 启动用户点系统 - 延迟更长时间确保基础飞线稳定
        if (enableUserPoints) {
            console.log('🎯 启动用户点系统...');
            setTimeout(() => {
                console.log('📍 启动用户点前再次验证基础飞线...');
                const preUserPointsCheck = debugBasicFlylines();
                if (preUserPointsCheck && preUserPointsCheck.found) {
                    console.log('✅ 基础飞线状态正常，启动用户点系统');
                    startUserPointsRendering();
                } else {
                    console.warn('⚠️ 启动用户点前发现基础飞线问题，先修复...');
                    ensureBasicFlylinesVisible();
                    setTimeout(() => {
                        startUserPointsRendering();
                    }, 2000);
                }
            }, 3000); // 延迟3秒启动，确保地图和基础飞线完全稳定
        }

        console.log('✅ 新地图系统初始化完成');
        console.log('🎨 配置信息:', {
            普通节点颜色: NEW_MAP_CONFIG.normalNodes.color,
            中心节点颜色: NEW_MAP_CONFIG.centerNode.color,
            飞线颜色: NEW_MAP_CONFIG.flylines.color,
            飞机箭头颜色: NEW_MAP_CONFIG.flylines.arrowColor,
            用户点功能: enableUserPoints ? '已启用' : '已禁用',
            用户点颜色: enableUserPoints ? USER_POINTS_CONFIG.appearance.color : '未启用',
            用户飞线颜色: enableUserPoints ? USER_POINTS_CONFIG.flylines.color : '未启用'
        });

        return window.mapChart;
        
    } catch (error) {
        console.error('❌ 地图初始化失败:', error);
        return null;
    }
}

/**
 * 快速修改配置的便捷函数（增强版）
 */
const MapConfigHelper = {
    // 修改普通节点颜色
    setNormalNodeColor: function(color) {
        NEW_MAP_CONFIG.normalNodes.color = color;
        NEW_MAP_CONFIG.normalNodes.rippleColor = color;
        console.log('普通节点颜色已更改为:', color);
    },

    // 修改中心节点颜色
    setCenterNodeColor: function(color) {
        NEW_MAP_CONFIG.centerNode.color = color;
        NEW_MAP_CONFIG.centerNode.rippleColor = color;
        console.log('中心节点颜色已更改为:', color);
    },

    // 修改飞线颜色
    setFlylineColor: function(lineColor, arrowColor) {
        NEW_MAP_CONFIG.flylines.color = lineColor;
        if (arrowColor) NEW_MAP_CONFIG.flylines.arrowColor = arrowColor;
        console.log('飞线颜色已更改为:', lineColor, '箭头:', arrowColor || '未改变');
    },

    // 修改节点大小
    setNodeSizes: function(normalSize, centerSize) {
        if (normalSize) NEW_MAP_CONFIG.normalNodes.size = normalSize;
        if (centerSize) NEW_MAP_CONFIG.centerNode.size = centerSize;
        console.log('节点大小已更改 - 普通:', normalSize, '中心:', centerSize);
    },

    // 修改用户点配置
    setUserPointsConfig: function(options) {
        if (options.color) {
            USER_POINTS_CONFIG.appearance.color = options.color;
            USER_POINTS_CONFIG.appearance.rippleColor = options.color;
        }
        if (options.size) {
            USER_POINTS_CONFIG.appearance.size = options.size;
        }
        if (options.targetCount) {
            USER_POINTS_CONFIG.quantity.target = options.targetCount;
        }
        if (options.flylineColor) {
            USER_POINTS_CONFIG.flylines.color = options.flylineColor;
        }
        console.log('用户点配置已更新:', options);
    },

    // 启用/禁用用户点系统
    toggleUserPoints: function(enable) {
        if (enable && !UserPointsManager.isRunning) {
            startUserPointsRendering();
            console.log('✅ 用户点系统已启用');
        } else if (!enable && UserPointsManager.isRunning) {
            stopUserPointsRendering();
            console.log('🛑 用户点系统已禁用');
        } else {
            console.log('⚠️ 用户点系统状态无变化');
        }
    },

    // 重启用户点系统
    restartUserPoints: function() {
        console.log('🔄 重启用户点系统...');
        UserPointsManager.restart();
        setTimeout(() => {
            startUserPointsRendering();
        }, 1500);
    },

    // 应用所有修改
    applyChanges: function(enableUserPoints = true) {
        if (window.mapChart) {
            initNewMap('map', enableUserPoints);
            console.log('✅ 配置已应用到地图');
        } else {
            console.log('❌ 地图实例不存在');
        }
    },

    // 获取当前配置
    getCurrentConfig: function() {
        return {
            mapConfig: NEW_MAP_CONFIG,
            userPointsConfig: USER_POINTS_CONFIG,
            userPointsRunning: UserPointsManager.isRunning,
            userPointsStats: UserPointsManager.isRunning ? UserPointsManager.getStats() : null
        };
    },

    // 获取系统状态
    getSystemStatus: function() {
        const stats = UserPointsManager.isRunning ? UserPointsManager.getStats() : null;
        const flylineStats = UserPointsManager.isRunning ? UserPointsManager.getFlylineStats() : null;

        return {
            mapInitialized: !!window.mapChart,
            userPointsEnabled: UserPointsManager.isRunning,
            userPointsCount: stats ? stats.total : 0,
            activeUserPoints: stats ? stats.active : 0,
            flylineCount: flylineStats ? flylineStats.total : 0,
            memoryUsage: {
                activePoints: UserPointsManager.activePoints.size,
                nextId: UserPointsManager.nextId
            }
        };
    }
};

// 调试函数（增强版）
function debugMapConfig() {
    console.log('🔍 地图配置调试');
    console.log('石家庄节点配置:', NEW_MAP_CONFIG.centerNode);
    console.log('普通节点配置:', NEW_MAP_CONFIG.normalNodes);
    console.log('飞线配置:', NEW_MAP_CONFIG.flylines);
    console.log('用户点配置:', USER_POINTS_CONFIG);
    console.log('系统状态:', MapConfigHelper.getSystemStatus());
}

// 用户点调试函数
function debugUserPoints() {
    console.log('👥 用户点系统调试');
    console.log('运行状态:', UserPointsManager.isRunning);
    console.log('统计信息:', UserPointsManager.getStats());
    console.log('飞线统计:', UserPointsManager.getFlylineStats());

    // 显示前5个用户点的详细信息
    const points = Array.from(UserPointsManager.activePoints.values()).slice(0, 5);
    console.log('前5个用户点详情:');
    points.forEach(point => {
        console.log('  ', point.getDebugInfo());
    });
}

// 禁用所有扩散效果
function disableRippleEffects() {
    console.log('🚫 禁用所有扩散效果...');

    // 禁用用户点扩散
    USER_POINTS_CONFIG.appearance.rippleScale = 0;

    // 禁用普通节点扩散
    NEW_MAP_CONFIG.normalNodes.rippleScale = 0;

    // 禁用中心节点扩散
    NEW_MAP_CONFIG.centerNode.rippleScale = 0;

    // 重新初始化地图
    if (window.mapChart) {
        initNewMap();
    }

    console.log('✅ 所有扩散效果已禁用');
}

// 启用扩散效果
function enableRippleEffects() {
    console.log('✨ 启用扩散效果...');

    // 启用用户点扩散
    USER_POINTS_CONFIG.appearance.rippleScale = 1;

    // 启用普通节点扩散
    NEW_MAP_CONFIG.normalNodes.rippleScale = 1.5;

    // 启用中心节点扩散
    NEW_MAP_CONFIG.centerNode.rippleScale = 2;

    // 重新初始化地图
    if (window.mapChart) {
        initNewMap();
    }

    console.log('✅ 扩散效果已启用');
}

// 紧急修复地图（恢复所有节点和飞线）
function emergencyFixMap() {
    console.log('🚨 紧急修复地图，恢复所有节点和飞线...');

    // 停止用户点系统
    UserPointsManager.stop();

    // 重新初始化地图
    initNewMap();

    console.log('✅ 地图已修复，所有节点和飞线已恢复');
}

// 紧急停止所有用户点
function emergencyStopUserPoints() {
    console.log('🚨 紧急停止所有用户点系统...');

    // 停止管理器
    UserPointsManager.stop();

    // 清空地图上的用户点
    if (window.mapChart) {
        window.mapChart.setOption({
            series: [
                {
                    name: '用户飞线增强',
                    data: []
                },
                {
                    name: '用户飞线',
                    data: []
                },
                {
                    name: '用户点',
                    data: []
                }
            ]
        }, false);
    }

    console.log('✅ 所有用户点已清除');
}

// 检查位置分布情况
function checkPositionDistribution() {
    console.log('📍 用户点位置分布检查:');

    const distribution = UserPointsManager.getCurrentProvinceDistribution();
    const positionHistory = UserPointsManager.positionHistory;

    console.log('各省份用户点数量和位置历史:');
    Object.keys(POPULATION_WEIGHTS).forEach(province => {
        const currentCount = distribution[province] || 0;
        const historyCount = positionHistory.get(province)?.length || 0;

        if (currentCount > 0 || historyCount > 0) {
            console.log(`  ${province}: 当前${currentCount}个, 历史位置${historyCount}个`);

            // 显示最近的几个位置
            const history = positionHistory.get(province);
            if (history && history.length > 0) {
                const recent = history.slice(-3); // 最近3个位置
                console.log(`    最近位置:`, recent.map(pos => `[${pos[0].toFixed(2)}, ${pos[1].toFixed(2)}]`).join(', '));
            }
        }
    });

    return {
        distribution,
        positionHistory: Object.fromEntries(positionHistory)
    };
}

// 检查用户点数量异常
function checkUserPointsOverflow() {
    const currentCount = UserPointsManager.activePoints.size;
    const targetCount = USER_POINTS_CONFIG.quantity.target;

    console.log('🔍 用户点数量检查:');
    console.log(`  当前数量: ${currentCount}`);
    console.log(`  目标数量: ${targetCount}`);
    console.log(`  配置范围: ${USER_POINTS_CONFIG.quantity.minActive}-${USER_POINTS_CONFIG.quantity.maxActive}`);
    console.log(`  运行状态: ${UserPointsManager.isRunning}`);

    if (currentCount > targetCount * 3) {
        console.warn('⚠️ 用户点数量异常过多！建议执行紧急清理');
        console.log('执行: emergencyStopUserPoints() 然后重新启动');
    }

    return {
        current: currentCount,
        target: targetCount,
        isOverflow: currentCount > targetCount * 2
    };
}

// 分布检查函数
function checkDistribution() {
    if (!UserPointsManager.isRunning) {
        console.log('⚠️ 用户点系统未运行');
        return;
    }

    const distribution = UserPointsManager.getCurrentProvinceDistribution();
    const totalPoints = UserPointsManager.activePoints.size;
    const totalWeight = Object.values(POPULATION_WEIGHTS).reduce((a, b) => a + b, 0);

    console.log('🗺️ 用户点分布检查:');
    console.log(`总用户点数: ${totalPoints}`);

    // 计算每个省份的分布情况
    const distributionAnalysis = Object.keys(POPULATION_WEIGHTS).map(province => {
        const currentCount = distribution[province] || 0;
        const expectedCount = Math.floor(totalPoints * (POPULATION_WEIGHTS[province] / totalWeight));
        const percentage = totalPoints > 0 ? ((currentCount / totalPoints) * 100).toFixed(1) : '0.0';
        const ratio = expectedCount > 0 ? (currentCount / expectedCount).toFixed(2) : 'N/A';

        return {
            province,
            current: currentCount,
            expected: expectedCount,
            percentage: parseFloat(percentage),
            ratio: parseFloat(ratio) || 0,
            deviation: Math.abs(currentCount - expectedCount)
        };
    });

    // 按当前用户点数量排序
    distributionAnalysis.sort((a, b) => b.current - a.current);

    console.log('省份分布详情:');
    distributionAnalysis.forEach(item => {
        const status = item.ratio > 1.3 ? '🔴过多' : item.ratio < 0.7 ? '🟡偏少' : '🟢正常';
        console.log(`  ${item.province}: ${item.current}个 (${item.percentage}%) | 期望:${item.expected} | 比例:${item.ratio} ${status}`);
    });

    // 分布质量评估
    const avgDeviation = distributionAnalysis.reduce((sum, item) => sum + item.deviation, 0) / distributionAnalysis.length;
    const maxDeviation = Math.max(...distributionAnalysis.map(item => item.deviation));
    const balanceScore = Math.max(0, 100 - (avgDeviation / totalPoints * 100 * 10)); // 平衡分数

    console.log('📊 分布质量评估:');
    console.log(`  平均偏差: ${avgDeviation.toFixed(1)}个用户点`);
    console.log(`  最大偏差: ${maxDeviation}个用户点`);
    console.log(`  平衡分数: ${balanceScore.toFixed(1)}/100`);

    if (balanceScore < 70) {
        console.log('⚠️ 建议执行重新平衡: UserPointsManager.enforceDistribution()');
    }

    return {
        distribution: distributionAnalysis,
        quality: {
            avgDeviation,
            maxDeviation,
            balanceScore
        }
    };
}

// 性能监控函数（增强版）
function monitorPerformance() {
    const stats = {
        timestamp: new Date().toLocaleTimeString(),
        system: MapConfigHelper.getSystemStatus(),
        memory: {
            used: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1024 / 1024) + 'MB' : '未知',
            total: performance.memory ? Math.round(performance.memory.totalJSHeapSize / 1024 / 1024) + 'MB' : '未知',
            limit: performance.memory ? Math.round(performance.memory.jsHeapSizeLimit / 1024 / 1024) + 'MB' : '未知'
        },
        performance: {
            userPointsCount: UserPointsManager.activePoints.size,
            renderingEnabled: UserPointsManager.isRunning,
            mapInitialized: !!window.mapChart
        }
    };

    console.log('📊 性能监控:', stats);

    // 性能警告
    if (performance.memory) {
        const memoryUsage = performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit;
        if (memoryUsage > 0.8) {
            console.warn('⚠️ 内存使用率过高:', (memoryUsage * 100).toFixed(1) + '%');
        }
    }

    return stats;
}

// 性能优化函数
function optimizePerformance() {
    console.log('🚀 执行性能优化...');

    // 1. 强制垃圾回收（如果支持）
    if (window.gc) {
        window.gc();
        console.log('✅ 执行垃圾回收');
    }

    // 2. 清理用户点系统
    if (UserPointsManager.isRunning) {
        UserPointsManager.memoryCleanup();
        console.log('✅ 清理用户点系统');
    }

    // 3. 检查并优化用户点数量
    const currentCount = UserPointsManager.activePoints.size;
    const targetCount = USER_POINTS_CONFIG.quantity.target;

    if (currentCount > targetCount * 1.2) {
        console.log('📉 用户点数量过多，执行优化...');
        UserPointsManager.emergencyCleanup();
    }

    // 4. 输出优化结果
    setTimeout(() => {
        const afterStats = monitorPerformance();
        console.log('✅ 性能优化完成');
    }, 1000);
}

// 压力测试函数
function stressTest(duration = 30000) {
    console.log(`🧪 开始压力测试 (${duration/1000}秒)...`);

    const originalTarget = USER_POINTS_CONFIG.quantity.target;
    const originalMax = USER_POINTS_CONFIG.quantity.maxActive;

    // 临时增加用户点数量
    USER_POINTS_CONFIG.quantity.target = 1000;
    USER_POINTS_CONFIG.quantity.maxActive = 1200;

    // 记录开始时间和性能
    const startTime = Date.now();
    const startStats = monitorPerformance();

    // 定期监控性能
    const monitorInterval = setInterval(() => {
        const elapsed = Date.now() - startTime;
        console.log(`🧪 压力测试进行中... ${Math.floor(elapsed/1000)}s`);
        monitorPerformance();
    }, 5000);

    // 测试结束
    setTimeout(() => {
        clearInterval(monitorInterval);

        // 恢复原始配置
        USER_POINTS_CONFIG.quantity.target = originalTarget;
        USER_POINTS_CONFIG.quantity.maxActive = originalMax;

        const endStats = monitorPerformance();
        console.log('🧪 压力测试完成');
        console.log('📊 测试前:', startStats);
        console.log('📊 测试后:', endStats);

        // 执行清理
        optimizePerformance();
    }, duration);
}

// 测试基础飞线独立显示（临时禁用用户点）
function testBasicFlylinesOnly() {
    console.log('🧪 测试基础飞线独立显示...');
    
    // 先停止用户点系统
    if (UserPointsManager.isRunning) {
        UserPointsManager.stop();
        console.log('⏹️ 已停止用户点系统');
    }
    
    // 重新初始化地图，但禁用用户点
    initNewMap('map', false);
    
    // 5秒后检查基础飞线状态
    setTimeout(() => {
        console.log('🔍 5秒后检查基础飞线状态:');
        debugBasicFlylines();
    }, 5000);
    
    // 10秒后再次检查
    setTimeout(() => {
        console.log('🔍 10秒后再次检查基础飞线状态:');
        debugBasicFlylines();
    }, 10000);
    
    console.log('✅ 测试已启动，请观察基础飞线是否持续显示');
    console.log('💡 如需恢复用户点，请运行: initNewMap()');
}

// 基础飞线调试函数
function debugBasicFlylines() {
    console.log('🔍 基础飞线系统调试');
    
    if (!window.mapChart) {
        console.log('❌ 地图实例不存在');
        return;
    }
    
    try {
        const option = window.mapChart.getOption();
        const series = option.series || [];
        
        console.log(`📊 总系列数: ${series.length}`);
        
        let basicFlylinesIndex = -1;
        let basicFlylinesData = null;
        
        series.forEach((s, index) => {
            console.log(`  系列${index}: ${s.name} (type: ${s.type})`);
            
            if (s.type === 'lines' && (s.name === '基础飞线' || s._seriesType === 'basicFlylines')) {
                basicFlylinesIndex = index;
                basicFlylinesData = s;
                console.log(`    🎯 这是基础飞线系列！`);
            }
        });
        
        if (basicFlylinesIndex >= 0 && basicFlylinesData) {
            console.log('✅ 基础飞线系列状态:');
            console.log(`  索引位置: ${basicFlylinesIndex}`);
            console.log(`  系列名称: ${basicFlylinesData.name}`);
            console.log(`  飞线数量: ${basicFlylinesData.data ? basicFlylinesData.data.length : 0}`);
            console.log(`  期望数量: ${TEST_NODES_DATA.length}`);
            console.log(`  动画效果: ${basicFlylinesData.effect?.show ? '开启' : '关闭'}`);
            console.log(`  动画周期: ${basicFlylinesData.effect?.period || '未设置'}`);
            console.log(`  线条颜色: ${basicFlylinesData.lineStyle?.color || '未设置'}`);
            console.log(`  箭头颜色: ${basicFlylinesData.effect?.color || '未设置'}`);
            console.log(`  渲染层级: ${basicFlylinesData.zlevel || '未设置'}`);
            console.log(`  是否受保护: ${basicFlylinesData._isProtected ? '是' : '否'}`);
            console.log(`  最后更新: ${basicFlylinesData._lastUpdated ? new Date(basicFlylinesData._lastUpdated).toLocaleTimeString() : '未记录'}`);
            
            // 检查每条飞线的数据
            if (basicFlylinesData.data && Array.isArray(basicFlylinesData.data)) {
                console.log('📍 飞线详情:');
                basicFlylinesData.data.forEach((flyline, i) => {
                    if (flyline && flyline.length >= 2) {
                        const from = flyline[0]?.coord || flyline[0];
                        const to = flyline[1]?.coord || flyline[1];
                        console.log(`  飞线${i+1}: [${from}] -> [${to}]`);
                    }
                });
            }
            
        } else {
            console.log('❌ 基础飞线系列未找到！');
            console.log('🔧 建议执行: ensureBasicFlylinesVisible() 或 initNewMap()');
        }
        
        return {
            found: basicFlylinesIndex >= 0,
            index: basicFlylinesIndex,
            data: basicFlylinesData,
            seriesCount: series.length
        };
        
    } catch (error) {
        console.error('❌ 基础飞线调试失败:', error);
        return null;
    }
}

// 强制基础飞线永久显示 - 用户手动控制函数
function forceBasicFlylinesAlwaysVisible() {
    console.log('🚀 强制基础飞线永久显示系统...');
    
    if (!window.mapChart) {
        console.error('❌ 地图实例不存在');
        return false;
    }
    
    // 立即强制显示基础飞线
    ensureBasicFlylinesVisible();
    
    // 设置超强维护间隔 - 每2秒检查一次
    if (window.basicFlylinesUltraInterval) {
        clearInterval(window.basicFlylinesUltraInterval);
    }
    
    window.basicFlylinesUltraInterval = setInterval(() => {
        if (!window.mapChart) return;
        
        const option = window.mapChart.getOption();
        const series = option.series || [];
        
        let needsRepair = false;
        let basicFlylinesIndex = -1;
        
        // 检查基础飞线状态
        for (let i = 0; i < series.length; i++) {
            const s = series[i];
            if (s.name === '基础飞线' || s._seriesType === 'basicFlylines') {
                basicFlylinesIndex = i;
                
                // 检查是否有任何问题
                if (!s.data || s.data.length !== TEST_NODES_DATA.length || 
                    !s.effect || !s.effect.show || s.effect.period !== NEW_MAP_CONFIG.flylines.period) {
                    needsRepair = true;
                    console.log('🔧 检测到基础飞线需要修复，立即处理...');
                }
                break;
            }
        }
        
        // 如果找不到基础飞线或需要修复
        if (basicFlylinesIndex === -1 || needsRepair) {
            console.log('⚡ 超强维护：重新确保基础飞线显示');
            ensureBasicFlylinesVisible();
            
            // 双重保险：再次验证
            setTimeout(() => {
                const recheck = window.mapChart.getOption();
                const recheckSeries = recheck.series || [];
                let verified = false;
                
                for (const s of recheckSeries) {
                    if (s.name === '基础飞线' && s.data && s.data.length === TEST_NODES_DATA.length) {
                        verified = true;
                        break;
                    }
                }
                
                if (!verified) {
                    console.error('🚨 紧急：基础飞线验证失败，重新创建地图');
                    initNewMap();
                }
            }, 1000);
        }
        
    }, 2000); // 每2秒超强检查
    
    console.log('✅ 基础飞线永久显示系统已激活 (2秒超强保护间隔)');
    return true;
}

// 停止强制保护（如果需要）
function stopForceBasicFlylines() {
    if (window.basicFlylinesUltraInterval) {
        clearInterval(window.basicFlylinesUltraInterval);
        window.basicFlylinesUltraInterval = null;
        console.log('🛑 基础飞线超强保护已停止');
    }
}

// 导出到全局作用域
window.NEW_MAP_CONFIG = NEW_MAP_CONFIG;
window.USER_POINTS_CONFIG = USER_POINTS_CONFIG;
window.UserPointsManager = UserPointsManager;
window.initNewMap = initNewMap;
window.MapConfigHelper = MapConfigHelper;
window.debugMapConfig = debugMapConfig;
window.debugUserPoints = debugUserPoints;
window.debugBasicFlylines = debugBasicFlylines;
window.testBasicFlylinesOnly = testBasicFlylinesOnly;
window.ensureBasicFlylinesVisible = ensureBasicFlylinesVisible;
window.verifyBasicFlylinesIntegrity = verifyBasicFlylinesIntegrity;
window.forceBasicFlylinesAlwaysVisible = forceBasicFlylinesAlwaysVisible; // 新增
window.stopForceBasicFlylines = stopForceBasicFlylines; // 新增
window.checkDistribution = checkDistribution;
window.emergencyStopUserPoints = emergencyStopUserPoints;
window.checkUserPointsOverflow = checkUserPointsOverflow;
window.checkPositionDistribution = checkPositionDistribution;
window.disableRippleEffects = disableRippleEffects;
window.enableRippleEffects = enableRippleEffects;
window.monitorPerformance = monitorPerformance;
window.optimizePerformance = optimizePerformance;
window.stressTest = stressTest;
window.startUserPointsRendering = startUserPointsRendering;
window.stopUserPointsRendering = stopUserPointsRendering;

console.log('🎨 新地图配置系统已加载（含用户点功能）');
console.log('🔴 石家庄中心节点颜色:', NEW_MAP_CONFIG.centerNode.color);
console.log('🟡 普通节点颜色:', NEW_MAP_CONFIG.normalNodes.color);
console.log('👤 用户点颜色:', USER_POINTS_CONFIG.appearance.color);
console.log('✈️ 用户飞线颜色:', USER_POINTS_CONFIG.flylines.color);
console.log('💡 使用方法:');
console.log('  🗺️ 地图控制:');
console.log('    initNewMap() - 初始化新地图（模拟900个用户，显示50-100个用户点）');
console.log('    initNewMap("map", false) - 初始化地图但禁用用户点');
console.log('    MapConfigHelper.toggleUserPoints(true/false) - 启用/禁用用户点');
console.log('  ✈️ 基础飞线控制 (重点):');
console.log('    forceBasicFlylinesAlwaysVisible() - 🔥 强制基础飞线永久显示 (2秒超强保护)');
console.log('    stopForceBasicFlylines() - 停止强制保护');
console.log('    ensureBasicFlylinesVisible() - 手动恢复基础飞线');
console.log('    debugBasicFlylines() - 调试基础飞线状态');
console.log('    testBasicFlylinesOnly() - 测试基础飞线独立显示');
console.log('  🔍 调试工具:');
console.log('    debugMapConfig() - 调试地图配置信息');
console.log('    debugUserPoints() - 调试用户点系统');
console.log('    verifyBasicFlylinesIntegrity() - 验证基础飞线完整性');
console.log('    checkDistribution() - 检查用户点分布情况');
console.log('    checkUserPointsOverflow() - 检查用户点数量是否异常');
console.log('    checkPositionDistribution() - 检查各省份位置分布情况');
console.log('    emergencyStopUserPoints() - 紧急停止所有用户点');
console.log('    MapConfigHelper.getSystemStatus() - 获取系统状态');
console.log('  📊 性能工具:');
console.log('    monitorPerformance() - 性能监控');
console.log('    optimizePerformance() - 执行性能优化');
console.log('    stressTest(30000) - 压力测试（默认30秒）');
console.log('  ⚙️ 高级配置:');
console.log('    USER_POINTS_CONFIG.quantity.target = 1000 - 设置目标用户数');
console.log('    MapConfigHelper.setUserPointsConfig({color: "#ff0000"}) - 修改用户点颜色');