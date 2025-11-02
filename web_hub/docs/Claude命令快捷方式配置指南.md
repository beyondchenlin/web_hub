# Claude命令快捷方式配置指南

## 需求描述
在终端输入 `claude` 等同于输入 `claude --dangerously-skip-permissions`，避免每次都要手动添加参数。

## 实现原理
通过创建一个批处理文件(.cmd)作为代理，在调用原始claude命令时自动添加所需参数，并将该批处理文件所在目录添加到系统PATH环境变量中。

## 配置步骤

### 步骤1：创建代理批处理文件

1. 在项目根目录创建 `claude.cmd` 文件
2. 文件内容如下：
```cmd
@echo off
wsl -d Ubuntu bash -c "/home/ai/.nvm/versions/node/v20.19.3/bin/node /home/ai/.nvm/versions/node/v20.19.3/bin/claude --dangerously-skip-permissions %*"
```

**注意事项：**
- 请根据你的实际WSL发行版名称修改 `-d Ubuntu` 部分
- 请根据你的实际claude安装路径修改node和claude的完整路径
- `%*` 表示传递所有命令行参数

### 步骤2：设置环境变量

#### 方法1：通过系统界面设置（推荐）
1. 右键"此电脑" → "属性" → "高级系统设置"
2. 点击"环境变量"按钮
3. 在"系统变量"区域找到 `Path` 变量，选中后点击"编辑"
4. 点击"新建"，添加你的项目根目录路径（例如：`D:\funclip-xiaocut-cut6.0-mmmmm`）
5. 点击"确定"保存所有设置

#### 方法2：通过命令行设置
在管理员权限的cmd中执行：
```cmd
setx PATH "%PATH%;你的项目根目录路径" /M
```
例如：
```cmd
setx PATH "%PATH%;D:\funclip-xiaocut-cut6.0-mmmmm" /M
```

### 步骤3：验证配置

1. 重新打开命令行窗口（重要！）
2. 执行验证命令：
```cmd
where claude
```

期望输出应该包含你的claude.cmd文件路径，例如：
```
D:\funclip-xiaocut-cut6.0-mmmmm\claude.cmd
C:\Users\AI\AppData\Roaming\npm\claude
C:\Users\AI\AppData\Roaming\npm\claude.cmd
```

3. 测试功能：
```cmd
claude --version
```
如果能正常显示版本信息，说明配置成功。

## 优先级说明
Windows会按照PATH中的顺序查找命令，确保你的项目目录在PATH中的位置靠前，这样会优先使用你的claude.cmd文件而不是系统中的其他claude命令。

## 故障排除

### 问题1：找不到claude命令
- 检查PATH环境变量是否正确添加
- 确认已重新打开命令行窗口
- 使用 `echo %PATH%` 查看当前PATH设置

### 问题2：WSL相关错误
- 确认WSL已正确安装并运行
- 检查WSL发行版名称是否正确
- 确认claude在WSL中的安装路径

### 问题3：权限相关错误
- 确保有足够权限修改系统环境变量
- 可尝试以管理员身份运行命令行

## 在其他电脑部署

1. 复制 `claude.cmd` 文件到目标电脑的项目目录
2. 根据目标电脑的实际情况修改文件中的路径
3. 将项目目录添加到目标电脑的PATH环境变量
4. 重启命令行窗口并验证

## 扩展用法
如果需要设置其他默认参数，只需修改claude.cmd文件中的命令行，在 `--dangerously-skip-permissions` 后添加其他参数即可。