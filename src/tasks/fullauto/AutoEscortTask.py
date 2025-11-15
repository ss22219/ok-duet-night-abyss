from qfluentwidgets import FluentIcon
import time
import json
import os

from ok import Logger, TaskDisabledException, GenshinInteraction
from src.tasks.DNAOneTimeTask import DNAOneTimeTask
from src.tasks.BaseCombatTask import BaseCombatTask
from src.tasks.CommissionsTask import CommissionsTask, Mission
from src.tasks.AutoExcavation import AutoExcavation

logger = Logger.get_logger(__name__)


class AutoEscortTask(DNAOneTimeTask, CommissionsTask, BaseCombatTask):
    """自动护送任务"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.name = "自动飞枪80护送（无需巧手）【需要游戏处于前台】"
        self.description = "全自动80护送任务，搬运自emt，欢迎路径作者署名。\n需要使用水母主控，近战武器选择0精春玦戟。魔之楔配置为金色迅捷+5，紫色穿引共鸣，紫色迅捷蓄势+5，紫色迅捷坠击+5，不要携带其他魔之楔，面板攻速为1.67。\n设置中控制设置水平灵敏度和垂直灵敏度设置为1.0，默认镜头距离设置为1.3。确认好自身魔之楔和设置后展开下方配置点击我已阅读后运行"
        self.group_name = "全自动"
        self.group_icon = FluentIcon.CAFE

        self.default_config.update(
            {
                "刷几次": 999,
                "我已阅读注意事项并确认配置": False,
            }
        )

        self.setup_commission_config()
        keys_to_remove = [
            "启用自动穿引共鸣",
            "使用技能",
            "技能释放频率",
            "发出声音提醒",
        ]
        for key in keys_to_remove:
            self.default_config.pop(key, None)

        self.config_description.update(
            {
                "刷几次": "完成几次护送任务后停止",
                "我已阅读注意事项并确认配置": "必须勾选才能执行任务！",
            }
        )

        self.action_timeout = 10

        # 在初始化时加载路径数据
        self.escort_paths = self._load_escort_paths()
        self.escort_actions = self.escort_paths.get("ESCORT_PATH_A", {}).get("data", [])

        # 缓存 GenshinInteraction 实例，避免重复创建
        self._genshin_interaction = None

        # 统计信息
        self.stats = {
            "rounds_completed": 0,  # 完成轮数
            "total_time": 0.0,  # 总耗时
            "start_time": None,  # 开始时间
            "current_phase": "准备中",  # 当前阶段
            "failed_attempts": 0,  # 失败次数（重新开始）
            "selected_path": None,  # 当前选择的路径
        }

    def _load_escort_paths(self):
        """从 JSON 文件加载护送路径数据"""
        json_path = os.path.join("mod", "builtin", "escort_paths.json")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"✓ 成功加载护送路径数据: {json_path}")
                return data.get("paths", {})
        except FileNotFoundError:
            logger.error(f"✗ 护送路径文件不存在: {json_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"✗ 护送路径 JSON 解析失败: {e}")
            return {}
        except Exception as e:
            logger.error(f"✗ 加载护送路径失败: {e}")
            return {}

    def run(self):
        DNAOneTimeTask.run(self)
        self.move_mouse_to_safe_position(save_current_pos=False)
        self.set_check_monthly_card()
        try:
            return self.do_run()
        except TaskDisabledException:
            pass
        except Exception as e:
            logger.error("AutoEscortTask error", e)
            raise

    def do_run(self):
        # 检查是否已阅读注意事项
        if not self.config.get("我已阅读注意事项并确认配置", False):
            logger.error("⚠️ 请先阅读注意事项并确认配置！")

            # 使用 info_set 显示详细配置要求
            self.info_set("错误", "未勾选配置确认")
            self.info_set("角色与武器", "使用水母主控，近战武器: 0精春玦戟")
            self.info_set(
                "武器mod(不要携带其他魔之楔)",
                "金色迅捷+5、紫色穿引共鸣、紫色迅捷蓄势+5、紫色迅捷坠击+5",
            )
            self.info_set("武器面板攻速", "面板攻速: 1.67")
            self.info_set("控制设置", "水平/垂直灵敏度: 1.0。镜头距离: 1.3")

            self.log_error("请先勾选「我已阅读注意事项并确认配置」")
            return

        self.load_char()
        _start_time = 0
        _count = 0
        _path_end_time = 0  # 路径执行结束时间

        # 初始化统计信息
        self.stats["rounds_completed"] = 0
        self.stats["start_time"] = time.time()
        self.stats["failed_attempts"] = 0
        self.stats["current_phase"] = "准备中"

        # 初始化 UI 显示
        self.info_set("完成轮数", 0)
        self.info_set("失败次数", 0)
        self.info_set("总耗时", "00:00:00")
        self.info_set("当前阶段", "准备中")

        while True:
            if self.in_team():
                if _start_time == 0:
                    _count += 1
                    _start_time = time.time()

                    # 更新阶段
                    self.stats["current_phase"] = "执行初始路径"
                    self.info_set("当前阶段", "执行初始路径")

                    # 先执行初始路径（使用相对时间版本）
                    self.escort_actions = self.escort_paths.get(
                        "ESCORT_PATH_A", {}
                    ).get("data", [])
                    success = self.execute_escort_path()

                    # 如果初始路径执行失败，等待退出队伍并重新开始
                    if not success:
                        logger.warning("初始路径执行失败，等待退出队伍...")
                        self.stats["failed_attempts"] += 1
                        self.info_set("失败次数", self.stats["failed_attempts"])
                        self.stats["current_phase"] = "重新开始"
                        self.info_set("当前阶段", "重新开始")
                        self.wait_until(
                            lambda: not self.in_team(), time_out=30, settle_time=1
                        )
                        _start_time = 0
                        _path_end_time = 0
                        continue

                    self.sleep(1)
                    # 基于 track_point 位置选择后续路径
                    self.stats["current_phase"] = "检测路径"
                    self.info_set("当前阶段", "检测路径")
                    logger.info("检测 track_point 位置，选择护送路径...")
                    self.escort_actions = self.select_escort_path_by_position()

                    # 如果检测失败返回 None，说明已经调用了 give_up_mission，等待退出队伍
                    if self.escort_actions is None:
                        logger.warning("路径选择失败，等待退出队伍...")
                        self.stats["failed_attempts"] += 1
                        self.info_set("失败次数", self.stats["failed_attempts"])
                        self.stats["current_phase"] = "重新开始"
                        self.info_set("当前阶段", "重新开始")
                        self.wait_until(
                            lambda: not self.in_team(), time_out=30, settle_time=1
                        )
                        _start_time = 0
                        _path_end_time = 0
                        continue

                    # 更新选择的路径
                    self.stats["current_phase"] = "执行护送路径"
                    self.info_set(
                        "当前阶段", f"执行路径{self.stats.get('selected_path', '?')}"
                    )

                    success = self.execute_escort_path()

                    # 如果后续路径执行失败（解密失败），等待退出队伍并重新开始
                    if not success:
                        logger.warning("后续路径执行失败，等待退出队伍...")
                        self.stats["failed_attempts"] += 1
                        self.info_set("失败次数", self.stats["failed_attempts"])
                        self.stats["current_phase"] = "重新开始"
                        self.info_set("当前阶段", "重新开始")
                        self.wait_until(
                            lambda: not self.in_team(), time_out=30, settle_time=1
                        )
                        _start_time = 0
                        _path_end_time = 0
                        continue

                    # 记录路径执行结束时间
                    _path_end_time = time.time()
                    self.stats["current_phase"] = "等待结算"
                    self.info_set("当前阶段", "等待结算")
                    logger.info("护送路径执行完毕，等待结算...")

                # 路径执行完成后，检查是否超时（5秒内应该进入结算）
                if _path_end_time > 0:
                    if time.time() - _path_end_time >= 5:
                        logger.warning(
                            "路径执行完成5秒后仍未进入结算，任务超时，重新开始..."
                        )
                        self.give_up_mission()
                        self.wait_until(
                            lambda: not self.in_team(), time_out=30, settle_time=1
                        )
                        _start_time = 0
                        _path_end_time = 0

            _status = self.handle_mission_interface()
            if _status == Mission.START:
                self.wait_until(self.in_team, time_out=30)

                # 完成一轮，更新统计
                if _count > 0:
                    self.stats["rounds_completed"] += 1
                    self.info_set("完成轮数", self.stats["rounds_completed"])

                    # 计算总耗时
                    elapsed_time = time.time() - self.stats["start_time"]
                    hours = int(elapsed_time // 3600)
                    minutes = int((elapsed_time % 3600) // 60)
                    seconds = int(elapsed_time % 60)
                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    self.info_set("总耗时", time_str)

                    avg_time = elapsed_time / self.stats["rounds_completed"]

                    logger.info("=" * 50)
                    logger.info(f"✓ 完成第 {self.stats['rounds_completed']} 轮护送")
                    logger.info(f"  总耗时: {time_str}")
                    logger.info(f"  平均每轮: {avg_time:.1f} 秒")
                    logger.info(f"  失败次数: {self.stats['failed_attempts']}")
                    max_rounds = self.config.get("刷几次", 999)
                    if max_rounds > 0:
                        remaining = max_rounds - self.stats["rounds_completed"]
                        logger.info(f"  剩余轮数: {remaining}")
                    logger.info("=" * 50)

                if _count >= self.config.get("刷几次", 999):
                    self.sleep(1)
                    self.open_in_mission_menu()
                    self.log_info_notify("任务终止")
                    self.soundBeep()
                    return
                self.log_info("任务开始")
                self.stats["current_phase"] = "任务开始"
                self.info_set("当前阶段", "任务开始")
                self.sleep(2)
                _start_time = 0
                _path_end_time = 0
            elif _status == Mission.CONTINUE:
                self.wait_until(self.in_team, time_out=30)
                self.log_info("任务继续")
                self.stats["current_phase"] = "任务继续"
                self.info_set("当前阶段", "任务继续")
                _start_time = 0
                _path_end_time = 0

            self.sleep(0.2)

    def select_escort_path_by_position(self):
        """根据 track_point 的位置选择护送路径

        使用 AutoExcavation 的 find_track_point 方法检测当前位置，
        根据坐标与预设点的距离选择最近的路径。

        3840x2160 分辨率下的参考点：
        - 路径1: (1902, 431)
        - 路径2: (1719, 438)
        - 路径3: (2284, 461)
        - 路径4: (2898, 688)

        Returns:
            选择的路径动作列表
        """
        # 定义 3840x2160 分辨率下的参考点
        reference_points = {
            1: (1902, 431),
            2: (1719, 438),
            3: (2284, 461),
            4: (2898, 688),
        }

        # 获取当前分辨率
        current_width = self.width
        current_height = self.height

        # 计算缩放比例
        scale_x = current_width / 3840
        scale_y = current_height / 2160

        # 缩放参考点到当前分辨率
        scaled_points = {}
        for path_id, (x, y) in reference_points.items():
            scaled_points[path_id] = (int(x * scale_x), int(y * scale_y))

        logger.info(
            f"当前分辨率: {current_width}x{current_height}, 缩放比例: {scale_x:.3f}x{scale_y:.3f}"
        )
        logger.info(f"缩放后的参考点: {scaled_points}")

        # 使用 AutoExcavation 的 find_track_point 方法检测位置
        try:
            track_point = AutoExcavation.find_track_point(self)

            if track_point is None:
                logger.warning("❌ 未检测到 track_point，无法确定路径，重新开始任务...")
                self.give_up_mission()
                return None

            # 获取检测到的坐标（使用中心点）
            detected_x = track_point.x + track_point.width // 2
            detected_y = track_point.y + track_point.height // 2

            logger.info(f"检测到 track_point 位置: ({detected_x}, {detected_y})")

            # 计算到每个参考点的距离
            min_distance = float("inf")
            selected_path = 1

            for path_id, (ref_x, ref_y) in scaled_points.items():
                distance = (
                    (detected_x - ref_x) ** 2 + (detected_y - ref_y) ** 2
                ) ** 0.5
                logger.debug(f"路径{path_id}: 距离 = {distance:.2f}")

                if distance < min_distance:
                    min_distance = distance
                    selected_path = path_id

            logger.info(
                f"✅ 选择路径{selected_path}，距离最近参考点 {min_distance:.2f} 像素"
            )

            # 记录选择的路径
            self.stats["selected_path"] = selected_path

            # 返回对应的路径
            path_map = {
                1: self.escort_paths.get("ESCORT_PATH_A_1", {}).get("data", []),
                2: self.escort_paths.get("ESCORT_PATH_A_2", {}).get("data", []),
                3: self.escort_paths.get("ESCORT_PATH_A_3", {}).get("data", []),
                4: self.escort_paths.get("ESCORT_PATH_A_4", {}).get("data", []),
            }

            return path_map.get(
                selected_path,
                self.escort_paths.get("ESCORT_PATH_A_1", {}).get("data", []),
            )

        except Exception as e:
            logger.error(f"❌ 检测 track_point 时出错: {e}，重新开始任务...")
            self.give_up_mission()
            return None

    def execute_escort_path(self):
        """执行护送路径中的所有动作，遇到 f 键时等待 AutoPuzzleTask 完成

        Returns:
            bool: True=成功完成, False=失败需要重新开始
        """
        if not self.escort_actions:
            logger.warning("没有加载护送路径，跳过移动")
            return True

        logger.info(f"开始执行护送路径，共 {len(self.escort_actions)} 个动作")

        # 将路径按 f 键拆分成多个片段
        path_segments = self.split_path_by_f_key()

        for segment_idx, segment in enumerate(path_segments):
            logger.info(f"执行路径片段 {segment_idx + 1}/{len(path_segments)}")

            # 如果前一个片段有 f 键（刚完成解密等待），跳过当前片段第一个动作的 delay
            skip_first_delay = segment_idx > 0 and self.segment_has_f_key(
                path_segments[segment_idx - 1]
            )

            self.execute_path_segment(segment, skip_first_delay=skip_first_delay)

            # 如果这个片段包含 f 键，等待 AutoPuzzleTask 完成解密
            if self.segment_has_f_key(segment):
                logger.info("检测到 f 键，等待 AutoPuzzleTask 完成解密...")
                success = self.wait_for_puzzle_completion()
                if not success:
                    # 解密失败，需要重新开始任务
                    return False

        logger.info("护送路径执行完成")
        return True

    def split_path_by_f_key(self):
        """将路径按 f 键拆分成多个片段"""
        segments = []
        current_segment = []

        for action in self.escort_actions:
            current_segment.append(action)

            # 检测到 key_up "f" 作为一个片段的结束
            if action.get("type") == "key_up" and action.get("key") == "f":
                segments.append(current_segment)
                current_segment = []

        # 如果还有剩余动作，添加为最后一个片段
        if current_segment:
            segments.append(current_segment)

        return segments if segments else [self.escort_actions]

    def segment_has_f_key(self, segment):
        """检查片段是否包含 f 键"""
        for action in segment:
            if (
                action.get("type") in ["key_down", "key_up"]
                and action.get("key") == "f"
            ):
                return True
        return False

    def execute_path_segment(self, segment, skip_first_delay=False):
        """执行单个路径片段（使用相对时间）

        新格式：每个动作包含 delay 字段（距离上一个动作的时间间隔）
        这样在解密等待后，后续动作可以立即继续，不会因为绝对时间错位

        Args:
            segment: 路径片段（动作列表）
            skip_first_delay: 是否跳过第一个动作的 delay（解密等待后使用）
        """
        for i, action in enumerate(segment):
            action_type = action.get("type")
            delay = action.get("delay", 0)

            # 如果是第一个动作且需要跳过 delay，则不等待
            if i == 0 and skip_first_delay:
                logger.debug(
                    f"跳过片段首个动作的 delay ({delay:.3f}s)，解密等待已消耗此时间"
                )
                delay = 0

            # 等待指定的延迟时间（使用高精度等待）
            if delay > 0:
                if delay > 0.001:
                    # 先 sleep 大部分时间，预留 0.5ms 缓冲
                    time.sleep(max(0, delay - 0.0005))

                    # 自旋等待，提高时间精度
                    end_time = time.perf_counter() + 0.0005
                    while time.perf_counter() < end_time:
                        pass
                else:
                    # 短延迟直接 sleep
                    time.sleep(delay)

            # 执行不同类型的动作
            if action_type == "mouse_rotation":
                self.execute_mouse_rotation(action)
            elif action_type == "mouse_down":
                button = action.get("button", "left")
                self.mouse_down(key=button)
                logger.debug(f"按下鼠标: {button}")
            elif action_type == "mouse_up":
                button = action.get("button", "left")
                self.mouse_up(key=button)
                logger.debug(f"释放鼠标: {button}")
            elif action_type == "key_down":
                key = action.get("key")
                self.send_key_down(key)
                logger.debug(f"按下键: {key}")
            elif action_type == "key_up":
                key = action.get("key")
                self.send_key_up(key)
                logger.debug(f"释放键: {key}")
            else:
                logger.warning(f"未知动作类型: {action_type}")

    def wait_for_puzzle_completion(self, timeout=30):
        """等待 AutoPuzzleTask 完成解密

        主动检测 puzzle 并触发解密，然后等待解密完成

        Returns:
            bool: True=成功完成或无需解密, False=检测失败需要重新开始任务
        """
        from src.tasks.trigger.AutoPuzzleTask import AutoPuzzleTask

        # 获取 AutoPuzzleTask 实例
        puzzle_task = self.get_task_by_class(AutoPuzzleTask)
        if not puzzle_task:
            logger.warning("未找到 AutoPuzzleTask，跳过等待")
            return True

        # 确保 AutoPuzzleTask 已初始化检测区域
        if (
            not puzzle_task.puzzle_boxes
            or puzzle_task.template_shape != self.frame.shape[:2]
        ):
            puzzle_task.init_boxes()
            logger.debug("已初始化 AutoPuzzleTask 检测区域")

        # 等待一小段时间让界面稳定
        self.sleep(0.5)

        # 等待直到屏幕上没有 puzzle 为止
        start_time = time.time()
        puzzle_detected = False
        puzzle_solving = False  # 标记是否正在解密

        while time.time() - start_time < timeout:
            # 更新当前帧（重要！确保检测最新画面）
            self.next_frame()

            # 检查是否有 puzzle
            has_puzzle = False

            for i in range(1, 9):
                puzzle_name = f"mech_maze_{i}"
                if puzzle_name not in puzzle_task.puzzle_boxes:
                    continue

                try:
                    puzzle_box = self.find_one(
                        puzzle_name,
                        box=puzzle_task.puzzle_boxes[puzzle_name],
                        threshold=puzzle_task.detection_threshold,
                    )
                    if puzzle_box:
                        has_puzzle = True

                        # 如果检测到 puzzle 且还未开始解密，立即触发解密
                        if not puzzle_solving:
                            puzzle_detected = True
                            puzzle_solving = True
                            logger.info(f"🔍 检测到 {puzzle_name}，开始解密...")
                            # 主动调用 AutoPuzzleTask 的解密方法
                            puzzle_task.solve_puzzle(puzzle_name)
                            logger.info("解密操作已完成，等待 puzzle 消失...")
                        else:
                            logger.debug(f"解密后仍检测到 {puzzle_name}，继续等待...")
                        break
                except Exception as e:
                    logger.debug(f"检测 {puzzle_name} 时出错: {e}")
                    continue

            # 如果曾经检测到过 puzzle 并已解密，但现在没有了，说明解密完成
            if puzzle_solving and not has_puzzle:
                logger.info("✅ 解密完成，puzzle 已消失")
                self.sleep(0.3)  # 额外等待一下确保稳定
                return True

            # 如果从未检测到 puzzle，可能是：
            # 1. puzzle 还未出现（需要继续等待）
            # 2. 这个路径片段没有 puzzle
            # 持续等待一段时间，如果始终没有检测到就认为没有 puzzle
            if not puzzle_detected and time.time() - start_time > 3:
                logger.warning(
                    "❌ 3秒内未检测到解密拼图，路径可能有误，重新开始任务..."
                )
                self.give_up_mission()
                return False

            self.sleep(0.2)

        # 超时
        if puzzle_detected:
            logger.warning(f"❌ 等待解密完成超时（{timeout}秒），重新开始任务...")
            self.give_up_mission()
            return False
        else:
            logger.debug("未检测到解密拼图")
            return True

    def execute_mouse_rotation(self, action):
        """执行鼠标视角旋转动作

        使用 GenshinInteraction 的 move_mouse_relative 方法进行相对鼠标移动
        注意：PostMessageInteraction 不支持相对移动，需要使用 GenshinInteraction
        """
        direction = action.get("direction", "up")
        angle = action.get("angle", 0)
        sensitivity = action.get("sensitivity", 10)

        # 根据 escort-A.py 的计算方式：pixels = angle * sensitivity
        pixels = angle * sensitivity

        # 计算移动方向
        if direction == "left":
            dx, dy = -pixels, 0
        elif direction == "right":
            dx, dy = pixels, 0
        elif direction == "up":
            dx, dy = 0, -pixels
        elif direction == "down":
            dx, dy = 0, pixels
        else:
            logger.warning(f"未知的鼠标方向: {direction}")
            return

        # 使用 GenshinInteraction 的 move_mouse_relative 方法
        interaction = self.executor.interaction
        if isinstance(interaction, GenshinInteraction):
            # 直接使用当前的 GenshinInteraction
            # 确保窗口在前台，move_mouse_relative 需要窗口处于前台
            self.executor.device_manager.hwnd_window.bring_to_front()
            interaction.move_mouse_relative(int(dx), int(dy))
        else:
            # PostMessageInteraction 不支持相对移动，需要使用 GenshinInteraction
            # 使用缓存的实例，避免重复创建
            if self._genshin_interaction is None:
                logger.debug("创建 GenshinInteraction 实例用于相对鼠标移动")
                self._genshin_interaction = GenshinInteraction(
                    interaction.capture, self.executor.device_manager.hwnd_window
                )
            # 确保窗口在前台
            self.executor.device_manager.hwnd_window.bring_to_front()
            self._genshin_interaction.move_mouse_relative(int(dx), int(dy))

        logger.debug(f"鼠标视角旋转: {direction}, 角度: {angle}, 像素: {pixels}")
