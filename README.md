<div align="center">
  <img src="icons/icon.png" alt="icon" width="200"><br>
  <h1>ok-dna</h1>
  <img src="https://img.shields.io/badge/platform-Windows-blue" alt="platform">
  <img alt="Static Badge" src="https://img.shields.io/badge/python-3.12%2B-skyblue">
  <img alt="GitHub Downloads (all assets, all releases)" src="https://img.shields.io/github/downloads/BnanZ0/ok-duet-night-abyss/total">
  <img alt="GitHub Release" src="https://img.shields.io/github/v/release/BnanZ0/ok-duet-night-abyss">
  <a href="https://discord.gg/vVyCatEBgA"><img alt="Discord" src="https://img.shields.io/discord/296598043787132928?color=5865f2&label=%20Discord"></a>
</div>

### 一个基于图像识别的二重螺旋自动化程序，支持后台运行，基于[ok-script](https://github.com/ok-oldking/ok-script)开发。

## 免责声明

本软件是一个外部工具旨在自动化《二重螺旋》的游戏玩法。它被设计成仅通过现有用户界面与游戏交互,并遵守相关法律法规。该软件包旨在提供简化和用户通过功能与游戏交互,并且它不打算以任何方式破坏游戏平衡或提供任何不公平的优势。该软件包不会以任何方式修改任何游戏文件或游戏代码。

This software is open source, free of charge and for learning and exchange purposes only. The developer team has the final right to interpret this project. All problems arising from the use of this software are not related to this project and the developer team. If you encounter a merchant using this software to practice on your behalf and charging for it, it may be the cost of equipment and time, etc. The problems and consequences arising from this software have nothing to do with it.

本软件开源、免费，仅供学习交流使用。开发者团队拥有本项目的最终解释权。使用本软件产生的所有问题与本项目与开发者团队无关。若您遇到商家使用本软件进行代练并收费，可能是设备与时间等费用，产生的问题及后果与本软件无关。

请注意，根据[二重螺旋的公平游戏宣言](https://dna.yingxiong.com/#/news/list?id=14453&type=2523):

    "严禁使用任何外挂、第三方工具以及其他破坏游戏公平性的行为。"
    "一经核实，运营团队将根据情节严重程度和次数，采取扣除违规收益、冻结或永久封禁游戏账号等措施，以维护玩家的公平权益。"

## 有什么功能？
<img width="1590" height="1150" alt="QQ_1762958578056" src="https://github.com/user-attachments/assets/cb7f145b-b304-4a0e-891a-3b6d5acff65d" />

* 副本挂机
  * 全自动或半自动
  * 自动连战
  *	适配外部移动逻辑
* 自动钓鱼（原作者b站无敌大蜜瓜）
* 快速移动
  * 自动穿引共鸣
* 自动花序弓蓄力
* 支持PC版游戏后台运行

## 兼容性
* 支持 1600x900 以上的 16:9 分辨率
* 简体中文/English

### 下载安装包运行
* 从[https://github.com/BnanZ0/ok-duet-night-abyss/releases](https://github.com/BnanZ0/ok-duet-night-abyss/releases) 下载 ok-dna-win32-China-setup.exe
* 双击安装, 安装后可自动更新

### Python 源码运行

仅支持Python 3.12

```bash
pip install -r requirements.txt --upgrade #install python dependencies, 更新代码后可能需要重新运行
python main.py # run the release version 运行发行版
python main_debug.py # run the debug version 运行调试版
```

## **程序使用指南与常见问题解答 (FAQ)**

为了确保程序稳定运行，请您在使用前仔细阅读以下配置要求和问题解决方案。

### 1. 使用前必读：环境配置

在使用本程序前，请确保您的游戏和系统环境满足以下条件：

- **图形设置**
    - **显卡滤镜**：请关闭所有显卡滤镜和锐化效果（如 NVIDIA Freestyle, AMD FidelityFX）。
    - **游戏亮度**：请使用游戏默认亮度。
- **分辨率**
    - 推荐使用 **1600x900** 或以上的分辨率。
- **按键设置**
    - 请使用游戏 **默认** 的按键绑定。
- **第三方软件**
    - 请禁用任何在游戏画面上显示信息的悬浮窗，如 MSI Afterburner (小飞机) 的 **FPS 显示**。
- **窗口与操作**
    - **鼠标干扰**：当游戏窗口处于 **前台** 时，请勿操作鼠标，否则会干扰程序的模拟点击。
    - **窗口状态**：游戏窗口可以切换到后台运行，但 **不可最小化**。
    - **系统状态**：请避免电脑 **熄屏** 或 **屏幕锁定**，这可能导致程序中断。

### 2. 快速上手

1.  进入您想运行的关卡。
2.  点击程序界面上的 **“开始”** 按钮即可。

### 3. 高级功能：添加外部逻辑 (Mod)

如果您希望扩展程序功能，可以安装外部逻辑模块：

1.  在程序主页点击 **“安装目录”**。
2.  将下载的逻辑模块文件放入 `mod` 文件夹内即可。

### 4. 常见问题排查 (Troubleshooting)

**Q1: 角色移动时撞墙，或者无法准确走到任务地点？**

-   **原因**：部分游戏引擎中，角色的移动速度会受到帧率 (FPS) 的影响。
-   **解决方案**：
    1.  **调整帧率**：请在游戏设置中，依次尝试将帧率上限设置为 **60 FPS** / **120 FPS** / **无限制**，找到最稳定的一项。
    2.  **修改时长**：修改对应任务或外部逻辑（Mod）中的 **按键时长** 参数。
    3.  **等待更新**：这个问题开发者（狗熊）后续可能会进行优化。

**Q2: 安装的外部逻辑 (Mod) 没有生效或识别不正确？**

-   **原因**：外部逻辑中的图像识别功能（识图）可能无法自动适应所有分辨率。
-   **解决方案**：
    1.  **调整分辨率**：尝试更换一个常用的游戏分辨率（如 1920x1080 或 1600x900）。
    2.  **重新录制**：如果您了解如何制作，可以为您当前的分辨率重新录制识图所用的截图。

**Q3: 程序卡在结算界面或复位界面，不再继续？**

-   **原因**：可能是鼠标的意外移动干扰了程序判断。
-   **解决方案**：
    1.  在程序左下角找到 **“设置”**。
    2.  进入 **“挂机设置”** 选项卡。
    3.  启用 **“防止鼠标干扰”** 功能。

### 5. 问题反馈

如果以上方法无法解决您的问题，欢迎向我们提交 Issue。为了帮助开发者快速定位并复现问题，请在反馈时务必提供以下信息：

-   **问题截图**：清晰地展示出现问题的界面或错误提示。
-   **日志文件**：附上程序运行目录下的日志文件。
-   **详细描述**：
    - 您进行了哪些操作？
    - 问题的具体表现是什么？
    - 问题是稳定复现还是偶尔发生？

## 社区
* 用户群 1063846003
* 开发者群 259268560
* [QQ频道](https://pd.qq.com/s/djmm6l44y)
* [Discord](https://discord.gg/vVyCatEBgA)

## 相关项目

* [ok-duet-night-abyss](https://github.com/BnanZ0/ok-duet-night-abyss) 一个基于图像识别的二重螺旋自动化程序。
* [ok-sra](https://github.com/Shasnow/ok-starrailassistant) 基于ok-script开发的星铁自动化
* [StarRailAssistant](https://github.com/Shasnow/StarRailAssistant) 一个基于图像识别的崩铁自动化程序，帮您完成从启动到退出的崩铁日常，支持多账号切换。原始项目。
* [ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves) 鸣潮 后台自动战斗 自动刷声骸 一键日常
* [ok-script-boilerplate](https://github.com/ok-oldking/ok-script-boilerplate) ok-script 脚本模板项目
