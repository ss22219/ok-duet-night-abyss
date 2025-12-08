from ok import TriggerTask, Logger, og
from src.scene.DNAScene import DNAScene
from src.tasks.BaseCombatTask import BaseCombatTask, CharDeadException
from src.tasks.BaseListenerTask import BaseListenerTask

from pynput import mouse
import ctypes
import struct
import math
import threading
import time
from ctypes import wintypes
from typing import Optional

logger = Logger.get_logger(__name__)

# 尝试导入 OffsetFinder
try:
    from src.utils.OffsetFinder import auto_find_offsets
    OFFSET_FINDER_AVAILABLE = True
except ImportError:
    OFFSET_FINDER_AVAILABLE = False
    logger.warning("OffsetFinder 不可用，无法自动查找偏移")

# Windows API 常量
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

# 鼠标输入结构（提前定义，避免重复）
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("mi", MOUSEINPUT)
    ]

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001

# 游戏偏移 (可通过 OffsetFinder 自动更新)
OFFSET_GAMEENGINE = 0x6E63030  # 正确的 GEngine 偏移（从 IDA 验证）
OFFSET_WORLD = 0x6FCA098
GNAMES_OFFSET = 0x6E1FA80      # 正确的 GNames 偏移（从 RealtimeFNameReader.cs 获取）
OFFSET_GAMESTATE = 0x130
OFFSET_BATTLE = 0xE90
OFFSET_GAMEINSTANCE = 0xE18
OFFSET_LOCALPLAYERS = 0x38
OFFSET_PLAYERCONTROLLER = 0x30
OFFSET_ACKNOWLEDGEDPAWN = 0x320
OFFSET_ROOTCOMPONENT = 0x160
OFFSET_COMPONENTTOWORLD = 0x1C0

# AEMGameState 偏移
OFFSET_MONSTERMAP = 0x668
OFFSET_BATTLE_MONSTERENTITIES = 0x3D0

# ACharacterBase 偏移
OFFSET_CURRENTLOCATION = 0x914
OFFSET_CURRENTVELOCITY = 0x920
OFFSET_EID = 0xAE4
OFFSET_MODELID = 0x950
OFFSET_ALREADYDEAD = 0x122B
OFFSET_OBJTYPE = 0x931

# 相机偏移
OFFSET_CONTROLROTATION = 0x308  # PlayerController.ControlRotation
OFFSET_PLAYERCAMERAMANAGER = 0x338
OFFSET_CAMERACACHEPRIVATE = 0x1C70
OFFSET_POV = 0x10  # POV.Location 在这里，POV.Rotation 在 +0xC

# ACharacterBase 偏移（用于读取玩家位置）
OFFSET_PLAYER_CURRENTLOCATION = 0x914  # 和怪物一样的偏移


class TriggerDeactivateException(Exception):
    """停止激活异常。"""
    pass


class MemoryReader:
    """游戏内存读取器"""
    
    def __init__(self):
        self.process_handle = None
        self.module_base = None
        self.kernel32 = ctypes.windll.kernel32
        
    def attach(self, process_name="EM-Win64-Shipping"):
        """附加到游戏进程"""
        try:
            import psutil
            from ctypes import wintypes
            
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] == f"{process_name}.exe":
                    pid = proc.info['pid']
                    self.process_handle = self.kernel32.OpenProcess(
                        PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid
                    )
                    if not self.process_handle:
                        logger.error(f"无法打开进程 PID: {pid}")
                        continue
                    
                    try:
                        # 使用 psapi.EnumProcessModules 获取模块基址
                        psapi = ctypes.windll.psapi
                        
                        # 枚举进程模块
                        hModules = (wintypes.HMODULE * 1024)()
                        cb_needed = wintypes.DWORD()
                        
                        if psapi.EnumProcessModules(
                            self.process_handle,
                            ctypes.byref(hModules),
                            ctypes.sizeof(hModules),
                            ctypes.byref(cb_needed)
                        ):
                            # 第一个模块就是主程序
                            if hModules[0]:
                                self.module_base = hModules[0]
                                logger.info(f"已附加到进程 PID: {pid}, 基址: {hex(self.module_base)}")
                                return True
                        
                        logger.error("EnumProcessModules 失败")
                        return False
                        
                    except Exception as e:
                        logger.error(f"获取模块基址失败: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        return False
                        
            logger.warning(f"未找到进程: {process_name}")
            return False
        except Exception as e:
            logger.error(f"附加进程失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def detach(self):
        """分离进程"""
        if self.process_handle:
            self.kernel32.CloseHandle(self.process_handle)
            self.process_handle = None
    
    def read_bytes(self, address, size):
        """读取字节"""
        if not self.process_handle:
            return None
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        success = self.kernel32.ReadProcessMemory(
            self.process_handle,
            ctypes.c_void_p(address),
            buffer,
            size,
            ctypes.byref(bytes_read)
        )
        return buffer.raw if success else None
    
    def read_int64(self, address):
        """读取 64 位整数（指针）"""
        data = self.read_bytes(address, 8)
        return struct.unpack('<Q', data)[0] if data else 0
    
    def read_int32(self, address):
        """读取 32 位整数"""
        data = self.read_bytes(address, 4)
        return struct.unpack('<i', data)[0] if data else 0
    
    def read_float(self, address):
        """读取浮点数"""
        data = self.read_bytes(address, 4)
        return struct.unpack('<f', data)[0] if data else 0.0
    
    def read_bool(self, address):
        """读取布尔值"""
        data = self.read_bytes(address, 1)
        return data[0] != 0 if data else False
    
    def read_vector3(self, address):
        """读取 3D 向量"""
        data = self.read_bytes(address, 12)
        if data:
            return struct.unpack('<fff', data)
        return (0.0, 0.0, 0.0)
    
    def read_short(self, address):
        """读取 16 位整数"""
        data = self.read_bytes(address, 2)
        return struct.unpack('<h', data)[0] if data else 0
    
    def is_valid_pointer(self, ptr):
        """检查指针是否有效"""
        return ptr > 0x10000 and ptr < 0x7FFFFFFFFFFF
    
    def read_fname(self, object_ptr):
        """读取 FName"""
        try:
            if not self.module_base:
                return ""
            
            gnames_address = self.module_base + GNAMES_OFFSET
            
            name_index = self.read_int32(object_ptr + 0x18)  # UObject.Name offset
            if name_index == 0:
                return ""
            
            chunk_offset = name_index >> 16
            name_offset = name_index & 0xFFFF
            
            chunk_ptr = self.read_int64(gnames_address + 8 * (chunk_offset + 2))
            if not self.is_valid_pointer(chunk_ptr):
                return ""
            
            name_pool_chunk = chunk_ptr + 2 * name_offset
            header = self.read_short(name_pool_chunk)
            name_length = header >> 6
            
            if name_length <= 0 or name_length > 1024:
                return ""
            
            buffer = self.read_bytes(name_pool_chunk + 2, name_length)
            if buffer:
                return buffer.decode('ascii', errors='ignore').rstrip('\0')
            return ""
        except:
            return ""
    
    def get_game_state(self):
        """获取 GameState 指针"""
        if not self.module_base:
            return 0
        world_addr = self.module_base + OFFSET_WORLD
        world = self.read_int64(world_addr)
        if not world:
            return 0
        return self.read_int64(world + OFFSET_GAMESTATE)
    
    def get_player_location(self):
        """获取玩家位置 - 使用和 C# 相同的方法"""
        try:
            game_engine_addr = self.module_base + OFFSET_GAMEENGINE
            game_engine = self.read_int64(game_engine_addr)
            if not game_engine:
                return None
            
            game_instance = self.read_int64(game_engine + OFFSET_GAMEINSTANCE)
            if not game_instance:
                return None
            
            local_players_array_addr = game_instance + OFFSET_LOCALPLAYERS
            local_players_array = self.read_int64(local_players_array_addr)
            if not local_players_array:
                return None
            
            local_player = self.read_int64(local_players_array)
            if not local_player:
                return None
            
            player_controller = self.read_int64(local_player + OFFSET_PLAYERCONTROLLER)
            if not player_controller:
                return None
            
            pawn = self.read_int64(player_controller + OFFSET_ACKNOWLEDGEDPAWN)
            if not pawn:
                return None
            
            pos = self.read_vector3(pawn + OFFSET_PLAYER_CURRENTLOCATION)
            return pos
            
        except Exception as e:
            logger.error(f"  获取玩家位置异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def get_camera_location(self):
        """获取相机位置 - 从 PlayerCameraManager.CameraCache.POV.Location"""
        try:
            game_engine_addr = self.module_base + OFFSET_GAMEENGINE
            game_engine = self.read_int64(game_engine_addr)
            if not game_engine:
                return None
            
            game_instance = self.read_int64(game_engine + OFFSET_GAMEINSTANCE)
            if not game_instance:
                return None
            
            local_players_array_addr = game_instance + OFFSET_LOCALPLAYERS
            local_players_array = self.read_int64(local_players_array_addr)
            if not local_players_array:
                return None
            
            local_player = self.read_int64(local_players_array)
            if not local_player:
                return None
            
            player_controller = self.read_int64(local_player + OFFSET_PLAYERCONTROLLER)
            if not player_controller:
                return None
            
            camera_manager = self.read_int64(player_controller + OFFSET_PLAYERCAMERAMANAGER)
            if not camera_manager:
                return None
            
            # 读取 CameraCache.POV.Location
            pov_location = self.read_vector3(camera_manager + OFFSET_CAMERACACHEPRIVATE + OFFSET_POV)
            return pov_location
            
        except Exception as e:
            logger.error(f"获取相机位置异常: {e}")
            return None
    
    def get_camera_rotation(self):
        """获取相机旋转 - 从 PlayerCameraManager.CameraCache.POV.Rotation（和 C# 一致）"""
        try:
            game_engine_addr = self.module_base + OFFSET_GAMEENGINE
            game_engine = self.read_int64(game_engine_addr)
            if not game_engine:
                return None
            
            game_instance = self.read_int64(game_engine + OFFSET_GAMEINSTANCE)
            if not game_instance:
                return None
            
            local_players_array_addr = game_instance + OFFSET_LOCALPLAYERS
            local_players_array = self.read_int64(local_players_array_addr)
            if not local_players_array:
                return None
            
            local_player = self.read_int64(local_players_array)
            if not local_player:
                return None
            
            player_controller = self.read_int64(local_player + OFFSET_PLAYERCONTROLLER)
            if not player_controller:
                return None
            
            camera_manager = self.read_int64(player_controller + OFFSET_PLAYERCAMERAMANAGER)
            if not camera_manager:
                return None
            
            # 读取 CameraCache.POV.Rotation (POV.Location 在 +0x10, POV.Rotation 在 +0x1C)
            # FRotator 是 3 个 float (Pitch, Yaw, Roll)
            rotation = self.read_vector3(camera_manager + OFFSET_CAMERACACHEPRIVATE + OFFSET_POV + 0xC)
            return rotation
            
        except Exception as e:
            logger.error(f"获取相机旋转异常: {e}")
            return None
    
    def scan_monsters(self, max_distance=10000.0, debug=False):
        """扫描附近怪物"""
        monsters = []
        game_state = self.get_game_state()
        if not game_state:
            if debug:
                logger.info("❌ GameState 为空")
            return monsters
        
        player_pos = self.get_player_location()
        if not player_pos:
            # 玩家位置获取失败，但仍然可以返回怪物（距离为0）
            if debug:
                logger.info("⚠ 无法获取玩家位置，距离计算将不准确")
            player_pos = None
        
        # 读取 MonsterMap
        monster_map_addr = game_state + OFFSET_MONSTERMAP
        map_data = self.read_bytes(monster_map_addr, 40)  # TMapData 结构
        if not map_data:
            if debug:
                logger.info("❌ 无法读取 MonsterMap")
            return monsters
        
        data_ptr, array_num = struct.unpack('<Qi', map_data[:12])
        
        if array_num <= 0 or data_ptr == 0:
            # MonsterMap 为空，这是正常的（可能在主菜单或没有怪物的场景）
            return monsters
        
        if debug:
            logger.info(f"MonsterMap: array_num={array_num}, 开始扫描...")
        
        # 统计信息
        total_entities = 0
        filtered_by_objtype = 0
        filtered_by_name = 0
        filtered_by_distance = 0
        
        for i in range(min(array_num, 500)):
            element_addr = data_ptr + i * 24
            element_data = self.read_bytes(element_addr, 24)
            if not element_data:
                continue
            
            key, padding, value_ptr, hash_next, hash_index = struct.unpack('<iiQii', element_data)
            
            # 跳过空槽位
            if hash_index == -1 or value_ptr == 0:
                continue
            
            total_entities += 1
            
            # 读取怪物信息
            eid = self.read_int32(value_ptr + OFFSET_EID)
            if eid <= 0:
                continue
            
            already_dead = self.read_bool(value_ptr + OFFSET_ALREADYDEAD)
            if already_dead:
                continue
            
            # 读取 ModelId
            model_id = self.read_int32(value_ptr + OFFSET_MODELID)
            
            # 读取 ObjType
            obj_type = self.read_bytes(value_ptr + OFFSET_OBJTYPE, 1)
            obj_type_val = obj_type[0] if obj_type else 0
            
            # 调试：记录所有实体
            if debug and i < 10:  # 只打印前10个
                logger.info(f"  实体 {i}: EID={eid}, ModelID={model_id}, ObjType={obj_type_val}, Dead={already_dead}")
            
            # 过滤逻辑（接受 ObjType 10 和 11）
            # ObjType 10 = MonsterCharacter, 11 = 其他怪物类型
            if obj_type_val not in [10, 11]:
                filtered_by_objtype += 1
                continue
            
            # 读取类名，检查是否是怪物（BP_Mon 开头）
            class_ptr = self.read_int64(value_ptr + 0x10)  # UObject.Class offset
            class_name = ""
            if self.is_valid_pointer(class_ptr):
                class_name = self.read_fname(class_ptr)
            
            # 只接受 BP_Mon 或 BP_Boss 开头的实体（真正的怪物）
            if not (class_name.startswith("BP_Mon_") or class_name.startswith("BP_Boss_")):
                filtered_by_name += 1
                if debug and total_entities <= 10:
                    logger.info(f"  跳过非怪物: ClassName={class_name}, ObjType={obj_type_val}")
                continue
            
            location = self.read_vector3(value_ptr + OFFSET_CURRENTLOCATION)
            velocity = self.read_vector3(value_ptr + OFFSET_CURRENTVELOCITY)
            
            # 计算距离
            if player_pos:
                dx = location[0] - player_pos[0]
                dy = location[1] - player_pos[1]
                dz = location[2] - player_pos[2]
                distance = math.sqrt(dx*dx + dy*dy + dz*dz)
            else:
                distance = 0.0  # 无法获取玩家位置时，距离设为0
            
            if distance <= max_distance:
                if debug:
                    logger.info(f"  ✓ 找到怪物: {class_name}, EID={eid}, ModelID={model_id}, 距离={distance/100:.1f}m")
                
                monsters.append({
                    'eid': eid,
                    'model_id': model_id,
                    'class_name': class_name,
                    'location': location,
                    'velocity': velocity,
                    'distance': distance,
                    'ptr': value_ptr
                })
            else:
                filtered_by_distance += 1
        
        if debug:
            logger.info(f"扫描完成: 找到 {len(monsters)} 个怪物")
            logger.info(f"  总实体: {total_entities}, 按ObjType过滤: {filtered_by_objtype}, 按名称过滤: {filtered_by_name}, 按距离过滤: {filtered_by_distance}")
        
        return sorted(monsters, key=lambda m: m['distance'])


class AutoAimTask(BaseListenerTask, BaseCombatTask, TriggerTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "自动花序弓蓄力瞄准"
        self.description = "需主动激活，运行中可使用右键或左键打断"
        self.scene: DNAScene | None = None
        self.setup_listener_config()
        self.default_config.update(
            {
                "激活键": "right",
                "按下时间": 0.50,
                "间隔时间": 0.50,
                "启用内存瞄准": "关闭",
                "瞄准距离": 100.0,
                "鼠标灵敏度": 0.2,
                "扫描延迟": 50,
                "高度偏移": 0.0,
                "预测时间": 0.15,
            }
        )
        self.config_type["激活键"]["options"].insert(0, "right")
        self.config_type["启用内存瞄准"] = {
            "type": "drop_down",
            "options": ["关闭", "开启"]
        }
        self.config_type["自动查找偏移"] = {
            "type": "drop_down",
            "options": ["关闭", "开启"]
        }
        self.config_description.update(
            {
                "按下时间": "右键按住多久(秒)",
                "间隔时间": "右键释放后等待多久(秒)",
                "启用内存瞄准": "使用内存读取自动瞄准最近怪物",
                "自动查找偏移": "游戏更新后自动查找新的内存偏移",
                "瞄准距离": "最大瞄准距离(米)，默认100",
                "鼠标灵敏度": "瞄准灵敏度，默认0.2",
                "扫描延迟": "扫描间隔(毫秒)，默认50",
                "高度偏移": "瞄准高度偏移，默认0",
                "预测时间": "移动预测时间(秒)，默认0.15",
            }
        )
        self.manual_activate = False
        self.signal = False
        self.signal_interrupt = False
        self.is_down = False
        self.memory_reader = None
        self.last_target = None
        self.aim_thread = None
        self.aim_thread_running = False

    def disable(self):
        """禁用任务时，断开信号连接。"""
        self.reset()
        self.stop_memory_reader()
        self.try_disconnect_listener()
        return super().disable()

    def enable(self):
        """启用任务时，信号连接。"""
        self.reset()
        self.try_connect_listener()
        return super().enable()

    def reset(self):
        self.manual_activate = False
        self.signal = False
        self.signal_interrupt = False
        self.stop_memory_reader()
    
    def start_memory_reader(self):
        """启动内存读取器"""
        if self.memory_reader is not None:
            return
        
        try:
            # 如果启用了自动查找偏移
            if OFFSET_FINDER_AVAILABLE and self.config.get("自动查找偏移", "关闭") == "开启":
                logger.info("正在自动查找内存偏移...")
                offsets = auto_find_offsets()
                if offsets:
                    # 更新全局偏移
                    global OFFSET_WORLD, OFFSET_GAMEENGINE, GNAMES_OFFSET
                    if offsets.get('OFFSET_WORLD'):
                        OFFSET_WORLD = offsets['OFFSET_WORLD']
                        logger.info(f"已更新 OFFSET_WORLD = 0x{OFFSET_WORLD:X}")
                    if offsets.get('OFFSET_GAMEENGINE'):
                        OFFSET_GAMEENGINE = offsets['OFFSET_GAMEENGINE']
                        logger.info(f"已更新 OFFSET_GAMEENGINE = 0x{OFFSET_GAMEENGINE:X}")
                    if offsets.get('GNAMES_OFFSET'):
                        GNAMES_OFFSET = offsets['GNAMES_OFFSET']
                        logger.info(f"已更新 GNAMES_OFFSET = 0x{GNAMES_OFFSET:X}")
                else:
                    logger.warning("自动查找偏移失败，使用默认值")
            
            self.memory_reader = MemoryReader()
            if self.memory_reader.attach():
                logger.info("内存读取器已启动")
            else:
                logger.warning("内存读取器启动失败")
                self.memory_reader = None
        except Exception as e:
            logger.error(f"启动内存读取器失败: {e}")
            self.memory_reader = None
    
    def stop_memory_reader(self):
        """停止内存读取器"""
        self.stop_aim_thread()
        if self.memory_reader is not None:
            try:
                self.memory_reader.detach()
                logger.info("已停止内存读取器")
            except Exception as e:
                logger.error(f"停止内存读取器失败: {e}")
            finally:
                self.memory_reader = None
                self.last_target = None
    
    def start_aim_thread(self):
        """启动瞄准线程"""
        if self.aim_thread is not None and self.aim_thread.is_alive():
            return
        
        self.aim_thread_running = True
        self.aim_thread = threading.Thread(target=self._aim_loop, daemon=True)
        self.aim_thread.start()
        logger.info("瞄准线程已启动")
    
    def stop_aim_thread(self):
        """停止瞄准线程"""
        if self.aim_thread is not None:
            self.aim_thread_running = False
            if self.aim_thread.is_alive():
                self.aim_thread.join(timeout=1.0)
            self.aim_thread = None
            logger.info("瞄准线程已停止")
    
    def _aim_loop(self):
        """瞄准线程主循环 - 模仿 C# 版本的高频更新"""
        last_scan_time = 0
        scan_interval = 0.1  # 100ms 扫描一次目标
        aim_interval = 0.01  # 10ms 更新一次瞄准（和 C# 一样）
        current_target = None
        
        while self.aim_thread_running:
            try:
                if not self.manual_activate or not self.is_down:
                    time.sleep(0.05)
                    current_target = None
                    continue
                
                current_time = time.time()
                
                # 定期重新扫描目标（100ms 间隔）
                if current_time - last_scan_time >= scan_interval or current_target is None:
                    max_distance = float(self.config.get("瞄准距离", 100.0)) * 100
                    monsters = self.memory_reader.scan_monsters(max_distance)
                    
                    if monsters:
                        new_target = monsters[0]
                        if current_target is None or current_target['eid'] != new_target['eid']:
                            current_target = new_target
                            logger.info(f"锁定目标: EID={current_target['eid']}, ModelID={current_target['model_id']}, 距离={current_target['distance']/100:.1f}m")
                    else:
                        if current_target is not None:
                            logger.info("目标丢失")
                        current_target = None
                    
                    last_scan_time = current_time
                
                # 持续瞄准当前目标（10ms 更新）
                if current_target is not None:
                    self._aim_at_target(current_target)
                
                time.sleep(aim_interval)
                
            except Exception as e:
                logger.error(f"瞄准线程异常: {e}")
                time.sleep(0.1)
                current_target = None
    
    def _aim_at_target(self, target):
        """瞄准指定目标（不扫描，只瞄准）"""
        if not self.memory_reader:
            return False
        
        try:
            # 获取相机信息
            camera_pos = self.memory_reader.get_camera_location()
            camera_rot = self.memory_reader.get_camera_rotation()
            
            if not camera_pos or not camera_rot:
                return False
            
            # 如果相机位置无效，回退到玩家位置
            if camera_pos[0] == 0 and camera_pos[1] == 0 and camera_pos[2] == 0:
                camera_pos = self.memory_reader.get_player_location()
                if not camera_pos:
                    return False
            
            # 预测目标位置
            prediction_time = float(self.config.get("预测时间", 0.15))
            target_pos = (
                target['location'][0] + target['velocity'][0] * prediction_time,
                target['location'][1] + target['velocity'][1] * prediction_time,
                target['location'][2] + target['velocity'][2] * prediction_time
            )
            
            # 计算目标方向（从相机位置到目标）
            dx = target_pos[0] - camera_pos[0]
            dy = target_pos[1] - camera_pos[1]
            dz = target_pos[2] - camera_pos[2]
            
            # 计算需要的旋转角度（和 C# 完全一致）
            distance_2d = math.sqrt(dx*dx + dy*dy)
            target_yaw = math.degrees(math.atan2(dy, dx))
            target_pitch = math.degrees(math.atan2(dz, distance_2d))  # 不要负号
            
            # 计算角度差
            current_yaw = camera_rot[1]
            current_pitch = camera_rot[0]
            
            # 标准化 Pitch 角度（和 C# 的 NormalizePitch 一致）
            # 将 Pitch 从 0-360° 转换为 -180° 到 180°
            while current_pitch > 180:
                current_pitch -= 360
            while current_pitch < -180:
                current_pitch += 360
            
            # 归一化角度到 [-180, 180]
            def normalize_angle(angle):
                while angle > 180:
                    angle -= 360
                while angle < -180:
                    angle += 360
                return angle
            
            current_yaw = normalize_angle(current_yaw)
            target_yaw = normalize_angle(target_yaw)
            
            delta_yaw = normalize_angle(target_yaw - current_yaw)
            delta_pitch = target_pitch - current_pitch
            
            # 如果误差很小，不需要调整
            if abs(delta_yaw) < 0.5 and abs(delta_pitch) < 0.5:
                return True
            
            # 转换为鼠标移动（和 C# 完全一致）
            sensitivity = float(self.config.get("鼠标灵敏度", 0.2))
            pixels_per_degree = 1.0 / sensitivity
            
            mouse_dx = int(delta_yaw * pixels_per_degree)
            mouse_dy = int(-delta_pitch * pixels_per_degree)  # Pitch 是负的
            
            # 限制单次移动量
            max_move = 50
            if abs(mouse_dx) > max_move:
                mouse_dx = max_move if mouse_dx > 0 else -max_move
            if abs(mouse_dy) > max_move:
                mouse_dy = max_move if mouse_dy > 0 else -max_move
            
            # 移动鼠标（使用 SendInput 相对移动）
            if abs(mouse_dx) > 1 or abs(mouse_dy) > 1:
                input_struct = INPUT()
                input_struct.type = INPUT_MOUSE
                input_struct.mi.dx = mouse_dx
                input_struct.mi.dy = mouse_dy
                input_struct.mi.mouseData = 0
                input_struct.mi.dwFlags = MOUSEEVENTF_MOVE
                input_struct.mi.time = 0
                input_struct.mi.dwExtraInfo = None
                
                ctypes.windll.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(input_struct))
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"瞄准失败: {e}")
            return False

    def run(self):
        if self.signal:
            self.signal = False
            if not self.scene.in_team(self.in_team_and_world):
                return
            if og.device_manager.hwnd_window.is_foreground():
                self.switch_state()

        while self.manual_activate:
            try:
                self.do_aim()
            except CharDeadException:
                self.log_error("Characters dead", notify=True)
                break
            except TriggerDeactivateException as e:
                logger.info(f"auto_aim_task_deactivate {e}")
                break

        if self.is_down:
            self.is_down = False
            self.mouse_up(key="right")
        return

    def do_aim(self):
        try:
            self.mouse_down(key="right")
            self.is_down = True
            # 瞄准线程会自动在后台持续瞄准
            self.sleep_check(self.config.get('按下时间', 0.50), False)
        finally:
            if self.is_down:
                self.mouse_up(key="right")
                self.is_down = False
        self.sleep_check(self.config.get("间隔时间", 0.50))

    def sleep_check(self, sec, check_signal_flag=True):
        remaining = sec
        step = 0.2
        while remaining > 0:
            s = step if remaining > step else remaining
            self.sleep_random(s, random_range=(1, 1.2))
            remaining -= s
            if self._should_interrupt(check_signal_flag):
                self.switch_state()
            if not self.manual_activate:
                raise TriggerDeactivateException

    def _should_interrupt(self, check_signal_flag: bool) -> bool:
        """检查是否应该中断当前操作"""
        return (self.signal_interrupt or
                (check_signal_flag and self.signal))

    def switch_state(self):
        self.signal_interrupt = False
        self.signal = False
        self.manual_activate = not self.manual_activate
        if self.manual_activate:
            logger.info("激活自动蓄力瞄准")
            # 如果启用了内存瞄准，启动内存读取器和瞄准线程
            if self.config.get("启用内存瞄准", "关闭") == "开启":
                self.start_memory_reader()
                self.start_aim_thread()
        else:
            logger.info("关闭自动蓄力瞄准")
            # 停止内存读取器和瞄准线程
            self.stop_memory_reader()

    def on_global_click(self, x, y, button, pressed):
        if self._executor.paused:
            return

        key_map = {
            'x1': mouse.Button.x1,
            'x2': mouse.Button.x2,
            'right': mouse.Button.right,
            'left': mouse.Button.left,
        }
        interrupt_button = (key_map.get("right"), key_map.get("left"))
        activate_key_name = self.config.get('激活键', 'x2')

        if activate_key_name == '使用键盘':
            if button not in interrupt_button:
                return

        activate_button = key_map.get(activate_key_name)

        if pressed:
            if button == activate_button:
                self.signal = True
            elif self.manual_activate and button in interrupt_button:
                self.signal_interrupt = True

    def on_global_press(self, key):
        if self._executor.paused or self.config.get('激活键', 'x2') != '使用键盘':
            return
        lower = self.config.get('键盘', 'ctrl_r').lower()
        hot_key = self.normalize_hotkey(lower)
        if self.key_equal(key, hot_key):
            self.signal = True
