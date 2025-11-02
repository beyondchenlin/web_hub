# Git 使用指南

本文档包含了 Git 的基本使用方法和常用命令，适合新手参考。

## 零、标准工作流程

### 首次使用（只需要做一次）：
```bash
# 1. 配置用户信息
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"

# 2. 生成 SSH 密钥（如果使用 SSH 方式）
ssh-keygen -t rsa -C "你的邮箱"
# 然后将 ~/.ssh/id_rsa.pub 中的内容添加到 GitHub SSH keys 中
```

### 首次提交项目到 GitHub：
```bash
# 1. 在 GitHub 上创建新仓库

# 2. 在项目目录中初始化 Git
git init

# 3. 添加文件到暂存区
git add .

# 4. 提交到本地仓库
git commit -m "first commit"

# 5. 重命名分支为 main
git branch -M main

# 6. 添加远程仓库（只需要做一次）
git remote add origin 仓库地址

# 7. 推送到远程仓库
git push -u origin main
```

### 日常工作流程：
```bash
# 1. 拉取最新代码
git pull

# 2. 修改代码...

# 3. 查看变更
git status

# 4. 添加修改到暂存区
git add .

# 5. 提交修改
git commit -m "cut3.0删除了不相关的代码"

# 6. 推送到远程
git push
```

在 Git 中创建新分支的命令如下：
```bash
git branch 分支名
```

如果你想创建分支并立即切换到新分支，可以使用：
```bash
git checkout -b 分支名
```

如果已经存在某个分支，想要切换到该分支，可以使用：
```bash
git checkout 分支名
```

## 一、首次添加项目到 GitHub

### 1. 初始化 Git 仓库
```bash
git init
```
> 这个命令会在当前目录创建一个新的 Git 仓库，生成 .git 目录，该目录包含了仓库所需的所有文件

### 2. 添加文件到暂存区
```bash
git add .
```
> - `.` 表示添加所有文件
> - 也可以使用 `git add 文件名` 添加特定文件
> - 使用 `git add 目录名` 添加特定目录

### 3. 提交到本地仓库
```bash
git commit -m "first commit"
```
> - `-m` 参数后面跟提交说明
> - 提交说明应该简明扼要地描述这次改动
> - 建议使用英文，且符合规范（feat: 新功能，fix: 修复bug等）

### 4. 重命名分支
```bash
git branch -M main
```
> - 将当前分支重命名为 main
> - GitHub 现在默认使用 main 作为主分支名
> - 以前的 master 分支名正在逐渐被替代

### 5. 添加远程仓库
```bash
# HTTPS方式（推荐新手使用）：
git remote add origin https://github.com/用户名/仓库名.git

# SSH方式（推荐团队使用）：
git remote add origin git@github.com:用户名/仓库名.git
```
> - HTTPS方式：需要输入用户名密码，但配置简单
> - SSH方式：需要配置SSH密钥，但更安全且不用重复输入密码
> - origin 是远程仓库的默认名称，可以修改

### 6. 推送到远程仓库
```bash
git push -u origin main
```
> - `-u` 参数设置上游分支，以后直接使用 `git push` 即可
> - 首次推送可能需要输入 GitHub 用户名和密码（HTTPS方式）
> - 如果使用 SSH 方式，确保已经配置好 SSH 密钥

## 二、从 GitHub 拉取项目

### 1. 克隆仓库
```bash
# HTTPS方式：
git clone https://github.com/用户名/仓库名.git

# SSH方式：
git clone git@github.com:用户名/仓库名.git
```
> - 会在当前目录下创建一个新目录，包含所有项目文件
> - 自动设置好远程仓库地址
> - 自动创建并切换到 main 分支

### 2. 拉取更新
```bash
git pull origin main
```
> - 获取远程仓库的最新更改并合并到当前分支
> - 相当于 `git fetch` + `git merge`
> - 如果之前用 `-u` 设置了上游分支，直接 `git pull` 即可

## 三、日常使用的常用命令

### 1. 查看仓库状态
```bash
git status
```
> - 显示工作目录和暂存区的状态
> - 显示哪些文件被修改了
> - 显示哪些文件还没有被 Git 跟踪

### 2. 添加修改到暂存区
```bash
git add .
```
> - 添加所有修改到暂存区
> - 包括新文件、修改文件和删除文件

### 3. 提交修改
```bash
git commit -m "cut3.0更新了字幕添加的逻辑,重点是stage7_0.py的大模型提示词"
```
> - 将暂存区的修改提交到本地仓库
> - 每次提交都应该有清晰的说明

### 4. 推送到远程
```bash
git push
```
> - 将本地提交推送到远程仓库
> - 如果没有设置上游分支，需要使用 `git push origin main`

### 5. 拉取更新
```bash
git pull
```
> - 获取远程仓库的更新并合并到本地

## 四、分支操作

### 1. 创建并切换到新分支
```bash
git checkout -b 分支名
```
> - 创建新分支并立即切换到该分支
> - 相当于 `git branch 分支名` + `git checkout 分支名`

### 2. 切换分支
```bash
git checkout 分支名
```
> - 切换到指定分支
> - 注意切换前最好提交或暂存当前修改

### 3. 合并分支
```bash
git merge 分支名
```
> - 将指定分支合并到当前分支
> - 可能需要解决冲突

### 4. 删除分支
```bash
git branch -d 分支名
```
> - 删除指定分支
> - 如果分支没有完全合并，使用 `-D` 强制删除

## 五、初始设置

### 1. 配置用户信息
```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```
> - 设置提交时使用的用户名和邮箱
> - `--global` 参数表示全局设置
> - 可以为不同的仓库设置不同的用户信息（去掉 --global）

### 2. 查看配置
```bash
git config --list
```
> - 显示当前的 Git 配置
> - 包括用户信息和其他设置

## 六、其他有用的命令

### 1. 查看提交历史
```bash
git log
```
> - 显示提交历史
> - 按 Q 键退出

### 2. 撤销修改
```bash
# 撤销工作区的修改
git checkout -- 文件名

# 撤销暂存区的修改
git reset HEAD 文件名
```
> - 小心使用，这些操作不可逆

### 3. 暂存当前修改
```bash
git stash
```
> - 临时保存当前的修改
> - 使用 `git stash pop` 恢复之前的修改

## 七、重置/还原代码

### 1. 使用远程仓库代码覆盖本地（慎用！）
```bash
# 方法1：强制覆盖本地代码（⚠️ 危险操作，会丢失所有本地修改）
git fetch --all
git reset --hard origin/main
git pull

# 方法2：只放弃某个文件的修改
git checkout origin/main 文件路径

# 方法3：放弃本地所有修改，但不删除文件
git checkout .
```

### 2. 温和的方式（推荐）
```bash
# 1. 先保存当前修改，以防万一
git stash

# 2. 拉取远程代码
git pull

# 如果确定不需要本地的修改了，可以删除之前的存储
git stash drop

# 如果还想保留之前的修改，可以把它们放在新分支
git stash branch new-branch-name
```

### 3. 撤销某个文件的修改
```bash
# 撤销单个文件的修改
git checkout -- 文件名

# 撤销所有未提交的修改
git checkout -- .
```

### 4. 不同阶段的撤销
```bash
# 1. 撤销工作区的修改（还没 git add）
git checkout -- 文件名

# 2. 撤销暂存区的修改（已经 git add，但没有 commit）
git reset HEAD 文件名
git checkout -- 文件名

# 3. 撤销提交（已经 commit，但没有 push）
git reset --hard HEAD^      # 回退到上一次提交
git reset --hard 提交ID    # 回退到指定的提交

# 4. 撤销已经推送到远程的提交（⚠️ 危险操作）
git reset --hard origin/main
git push -f                # 强制推送
```

### 5. 注意事项
- 使用 `--hard` 参数会丢失所有未提交的修改，请谨慎使用
- 建议在重置前先使用 `git stash` 备份当前修改
- 如果不确定，可以创建新分支进行尝试
- 强制推送 (`push -f`) 可能会影响其他协作者，请谨慎使用

## 八、恢复到最新提交

### 1. 快速参考
```bash
# 最安全的方式（推荐）
git stash              # 1. 先暂存当前的修改（以防万一）
git reset --hard HEAD  # 2. 回到最新提交
git stash drop        # 3. 如果确认不需要之前的修改了，可以删除暂存的内容
```

### 2. 根据不同阶段的恢复方法

#### 2.1 如果文件还在工作区（还没有 git add）
```bash
# 放弃所有工作区的修改，恢复到最后一次提交的状态
git checkout .

# 或者放弃指定文件的修改
git checkout -- 文件名
```

#### 2.2 如果文件在暂存区（已经 git add，但还没有 commit）
```bash
# 1. 先取消暂存
git reset HEAD

# 2. 然后放弃修改
git checkout .
```

#### 2.3 如果已经 commit 但还没有 push
```bash
# 回退到最新的提交
git reset --hard HEAD

# 或者回退到上一次提交
git reset --hard HEAD^
```

### 3. 安全的工作流程（推荐）

```bash
# 1. 查看当前状态
git status

# 2. 暂存当前修改（以防万一需要恢复）
git stash

# 3. 恢复到最新提交
git reset --hard HEAD

# 如果后面发现需要恢复之前的修改：
git stash pop    # 恢复之前暂存的修改

# 如果确认不需要之前的修改：
git stash drop   # 删除暂存的修改
```

### 4. 注意事项
- `git reset --hard` 是不可逆操作，使用前请确保你真的要放弃所有修改
- 建议使用 `git stash` 暂存当前修改，这样操作更安全
- 使用 `git status` 查看当前状态，避免误操作
- 如果不确定，可以先创建一个新分支再操作

### 5. 查看历史提交
```bash
# 查看提交历史
git log

# 查看简化的提交历史（一行显示）
git log --oneline

# 查看最近的 n 次提交
git log -n 5  # 查看最近 5 次提交
```

## 注意事项

1. 经常使用 `git status` 查看仓库状态
2. 提交前先查看改动 `git diff`
3. 养成及时提交的习惯
4. 写有意义的提交说明
5. 不要提交与项目无关的文件

## 帮助命令

如果忘记了命令的具体用法，可以使用：
```bash
git help 命令
# 或
git 命令 --help
```

这会显示该命令的详细帮助文档。

## 零、Git 重要术语解释

### 1. 仓库相关
- **repository（仓库）**：存放项目代码的地方
  - 本地仓库：在自己电脑上的代码仓库
  - 远程仓库：在 GitHub 等平台上的代码仓库

- **origin**：远程仓库的默认别名
  ```bash
  # 查看远程仓库信息
  git remote -v
  
  # 输出示例：
  # origin  git@github.com:用户名/仓库名.git (fetch)
  # origin  git@github.com:用户名/仓库名.git (push)
  ```

### 2. 分支相关
- **branch（分支）**：代码的一条独立修改路线
  - **main**：主分支（默认分支），以前叫 master
  - **dev**：开发分支（如果有的话）
  - **feature**：功能分支（如果有的话）

```bash
# 查看所有本地分支
git branch

# 查看所有远程分支
git branch -r

# 查看所有分支（本地+远程）
git branch -a
```

### 3. 命令中的参数含义
```bash
git push origin main
# origin：远程仓库的别名
# main：分支名

git push -u origin main
# -u：设置上游分支，建立本地和远程分支的关联
# 设置后后续可以直接使用 git push 和 git pull
```

### 4. 工作区和暂存区
- **工作区**：你当前看到的，正在编辑的文件
- **暂存区**：通过 `git add` 添加的文件会进入暂存区
- **本地仓库**：通过 `git commit` 提交后，文件会进入本地仓库
- **远程仓库**：通过 `git push` 推送后，文件会进入远程仓库

```bash
# 工作区 -> 暂存区
git add .

# 暂存区 -> 本地仓库
git commit -m "提交信息"

# 本地仓库 -> 远程仓库
git push
```

### 5. 关于 git pull
`git pull` 的作用是从远程仓库获取最新代码并合并到本地，它不会直接覆盖你的本地修改：

- 如果远程修改的文件，你没有修改 -> 直接更新
- 如果远程修改的文件，你也修改了 -> Git 会尝试自动合并
- 如果无法自动合并 -> 会提示冲突，让你手动解决

```bash
# 安全的工作流程
git pull                # 先拉取最新代码
# 修改代码...
git add .              # 添加修改
git commit -m "说明"    # 提交修改
git pull              # 再次拉取（确保没有新的更改）
git push              # 推送到远程
```

如果担心 pull 会影响本地修改，可以：
```bash
git stash            # 暂存本地修改
git pull            # 拉取更新
git stash pop       # 恢复本地修改
```
