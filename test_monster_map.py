"""
测试脚本：使用 MonsterMap 查找怪物
基于 GetBattleEntitiesAPI.cs 的实现
"""

import ctypes
import struct
import math
import psutil
from ctypes import wintypes

# Windows API 常量
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

# 游戏偏移（由 OffsetFinder_hybrid.py 自动查找）
OFFSET_WORLD = 0x6FCA098       # ✅ 正确
GNAMES_OFFSET = 0x6E1FA80      # ✅ 正确（从 RealtimeFNameReader.cs 获取）
OFFSET_GAMEENGINE = 0x6D385E0  # ✅ 正确
OFFSET_GAMESTATE = 0x130

# AEMGameState 偏移
OFFSET_MONSTERMAP = 0x668

# UObject 基础偏移
UOBJECT_NAME = 0x18
UOBJECT_CLASS = 0x10

# ACharacterBase 偏移
OFFSET_CURRENTLOCATION = 0x914
OFFSET_CURRENTVELOCITY = 0x920
OFFSET_EID = 0xAE4
OFFSET_MODELID = 0x950
OFFSET_ALREADYDEAD = 0x122B
OFFSET_OBJTYPE = 0x931

# AActor 相关偏移
ACTOR_ROOTCOMPONENT = 0x160
SCENECOMPONENT_COMPONENTTOWORLD = 0x1C0

# 玩家相关偏移
OFFSET_GAMEENGINE = 0x6E63030  # 正确的 GEngine 偏移（备用偏移）
OFFSET_GAMEINSTANCE = 0xE18
OFFSET_LOCALPLAYERS = 0x38
OFFSET_PLAYERCONTROLLER = 0x30
OFFSET_ACKNOWLEDGEDPAWN = 0x320
OFFSET_PLAYER_CURRENTLOCATION = 0x914


class MemoryReader:
    """游戏内存读取器"""
    
    def __init__(self):
        self.process_handle = None
        self.module_base = None
        self.gnames_address = None
        self.kernel32 = ctypes.windll.kernel32
        
    def attach(self, process_name="EM-Win64-Shipping"):
        """附加到游戏进程"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] == f"{process_name}.exe":
                    pid = proc.info['pid']
                    self.process_handle = self.kernel32.OpenProcess(
                        PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid
                    )
                    if not self.process_handle:
                        print(f"❌ 无法打开进程 PID: {pid}")
                        continue
                    
                    # 使用 psapi.EnumProcessModules 获取模块基址
                    psapi = ctypes.windll.psapi
                    hModules = (wintypes.HMODULE * 1024)()
                    cb_needed = wintypes.DWORD()
                    
                    if psapi.EnumProcessModules(
                        self.process_handle,
                        ctypes.byref(hModules),
                        ctypes.sizeof(hModules),
                        ctypes.byref(cb_needed)
                    ):
                        if hModules[0]:
                            self.module_base = hModules[0]
                            self.gnames_address = self.module_base + GNAMES_OFFSET
                            print(f"✓ 已附加到进程 PID: {pid}")
                            print(f"  模块基址: 0x{self.module_base:X}")
                            print(f"  GNames: 0x{self.gnames_address:X}")
                            return True
                    
                    print("❌ EnumProcessModules 失败")
                    return False
                        
            print(f"❌ 未找到进程: {process_name}")
            return False
        except Exception as e:
            print(f"❌ 附加进程失败: {e}")
            import traceback
            traceback.print_exc()
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
        """读取 FName（和 C# 版本一致）"""
        try:
            name_index = self.read_int32(object_ptr + UOBJECT_NAME)
            if name_index == 0:
                return "None"
            
            chunk_offset = name_index >> 16
            name_offset = name_index & 0xFFFF
            
            # 调试信息
            # print(f"      [FName] NameIndex={name_index}, ChunkOffset={chunk_offset}, NameOffset={name_offset}")
            
            chunk_ptr = self.read_int64(self.gnames_address + 8 * (chunk_offset + 2))
            if not self.is_valid_pointer(chunk_ptr):
                return f"InvalidChunk(0x{chunk_ptr:X})"
            
            name_pool_chunk = chunk_ptr + 2 * name_offset
            header = self.read_short(name_pool_chunk)
            name_length = header >> 6
            
            if name_length <= 0 or name_length > 1024:
                return f"BadLength({name_length})"
            
            buffer = self.read_bytes(name_pool_chunk + 2, name_length)
            if buffer:
                return buffer.decode('ascii', errors='ignore').rstrip('\0')
            return "ReadError"
        except Exception as e:
            return f"Error: {e}"
    
    def get_game_state(self):
        """获取 GameState 指针"""
        if not self.module_base:
            print("  ❌ module_base 为空")
            return 0
        world_addr = self.module_base + OFFSET_WORLD
        print(f"  World 地址: 0x{world_addr:X}")
        world = self.read_int64(world_addr)
        print(f"  World 指针: 0x{world:X}")
        if not world:
            print("  ❌ World 指针为空")
            return 0
        game_state = self.read_int64(world + OFFSET_GAMESTATE)
        print(f"  GameState 指针: 0x{game_state:X}")
        return game_state
    
    def get_player_location(self):
        """获取玩家位置（和 C# 版本一致）"""
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
            print(f"  获取玩家位置异常: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_actor_position(self, actor_ptr):
        """获取 Actor 的位置（和 C# 版本一致）"""
        try:
            root_component = self.read_int64(actor_ptr + ACTOR_ROOTCOMPONENT)
            if not self.is_valid_pointer(root_component):
                return (0.0, 0.0, 0.0)
            
            # 从 ComponentToWorld 变换矩阵读取位置 (Translation at offset +0x10)
            transform_addr = root_component + SCENECOMPONENT_COMPONENTTOWORLD
            return self.read_vector3(transform_addr + 0x10)
        except:
            return (0.0, 0.0, 0.0)
    
    def scan_monster_map(self, max_distance=10000.0):
        """扫描 MonsterMap（和 C# 版本一致）"""
        monsters = []
        game_state = self.get_game_state()
        if not game_state:
            print("❌ GameState 为空")
            return monsters
        
        print(f"✓ GameState 地址: 0x{game_state:X}")
        
        # 获取玩家位置
        player_pos = self.get_player_location()
        if player_pos:
            print(f"✓ 玩家位置: ({player_pos[0]:.2f}, {player_pos[1]:.2f}, {player_pos[2]:.2f})")
        else:
            print(f"⚠ 无法获取玩家位置，距离计算将不准确")
        
        # 读取 MonsterMap
        monster_map_addr = game_state + OFFSET_MONSTERMAP
        map_data = self.read_bytes(monster_map_addr, 40)  # TMapData 结构
        if not map_data:
            print("❌ 无法读取 MonsterMap")
            return monsters
        
        data_ptr, array_num = struct.unpack('<Qi', map_data[:12])
        
        print(f"  MonsterMap 数量: {array_num}")
        print(f"  MonsterMap Data: 0x{data_ptr:X}")
        
        if array_num <= 0 or data_ptr == 0:
            print(f"❌ MonsterMap 为空")
            return monsters
        
        element_size = 24  # TSetElement size
        
        for i in range(min(array_num, 500)):
            element_addr = data_ptr + i * element_size
            element_data = self.read_bytes(element_addr, 24)
            if not element_data:
                continue
            
            key, padding, value_ptr, hash_next, hash_index = struct.unpack('<iiQii', element_data)
            
            # 跳过空槽位
            if hash_index == -1 or value_ptr == 0:
                continue
            
            if not self.is_valid_pointer(value_ptr):
                continue
            
            # 读取对象信息
            object_name = self.read_fname(value_ptr)
            class_ptr = self.read_int64(value_ptr + UOBJECT_CLASS)
            class_name = self.read_fname(class_ptr) if self.is_valid_pointer(class_ptr) else "Unknown"
            
            # 读取怪物信息
            eid = self.read_int32(value_ptr + OFFSET_EID)
            model_id = self.read_int32(value_ptr + OFFSET_MODELID)
            already_dead = self.read_bool(value_ptr + OFFSET_ALREADYDEAD)
            obj_type = self.read_bytes(value_ptr + OFFSET_OBJTYPE, 1)
            obj_type_val = obj_type[0] if obj_type else 0
            
            # 获取位置（使用 Actor 方法）
            location = self.get_actor_position(value_ptr)
            velocity = self.read_vector3(value_ptr + OFFSET_CURRENTVELOCITY)
            
            # 计算距离
            distance = 0.0
            if player_pos:
                dx = location[0] - player_pos[0]
                dy = location[1] - player_pos[1]
                dz = location[2] - player_pos[2]
                distance = math.sqrt(dx*dx + dy*dy + dz*dz)
            
            # 打印前10个实体的详细信息
            if i < 10:
                print(f"\n  实体 {i}:")
                print(f"    Key: {key}")
                print(f"    Value: 0x{value_ptr:X}")
                print(f"    HashIndex: {hash_index}")
                print(f"    Name: {object_name}")
                print(f"    ClassName: {class_name}")
                print(f"    EID: {eid}")
                print(f"    ModelID: {model_id}")
                print(f"    ObjType: {obj_type_val}")
                print(f"    AlreadyDead: {already_dead}")
                print(f"    Location: ({location[0]:.2f}, {location[1]:.2f}, {location[2]:.2f})")
                print(f"    Velocity: ({velocity[0]:.2f}, {velocity[1]:.2f}, {velocity[2]:.2f})")
                if player_pos:
                    print(f"    Distance: {distance/100:.1f}m")
            
            # 过滤条件
            if eid <= 0:
                if i < 10:
                    print(f"    ⚠ 跳过: EID <= 0")
                continue
            
            if already_dead:
                if i < 10:
                    print(f"    ⚠ 跳过: 已死亡")
                continue
            
            # 只接受 ObjType 10 和 11
            if obj_type_val not in [10, 11]:
                if i < 10:
                    print(f"    ⚠ 跳过: ObjType={obj_type_val} (不是 10 或 11)")
                continue
            
            # 只接受 BP_Mon_ 或 BP_Boss_ 开头的怪物
            if not (class_name.startswith("BP_Mon_") or class_name.startswith("BP_Boss_")):
                if i < 10:
                    print(f"    ⚠ 跳过: 不是怪物 (ClassName={class_name})")
                continue
            
            # 距离过滤
            if player_pos and distance > max_distance:
                continue
            
            print(f"  ✓ 找到怪物: {class_name}, EID={eid}, ModelID={model_id}, 距离={distance/100:.1f}m")
            
            monsters.append({
                'eid': eid,
                'model_id': model_id,
                'name': object_name,
                'class_name': class_name,
                'location': location,
                'velocity': velocity,
                'distance': distance,
                'ptr': value_ptr
            })
        
        return monsters


def main():
    print("=" * 80)
    print("MonsterMap 测试脚本")
    print("=" * 80)
    
    reader = MemoryReader()
    
    if not reader.attach():
        print("\n❌ 无法附加到游戏进程")
        return
    
    try:
        print("\n开始扫描 MonsterMap...")
        print("-" * 80)
        
        monsters = reader.scan_monster_map(max_distance=100 * 100)  # 100米
        
        print("\n" + "=" * 80)
        print(f"扫描完成: 找到 {len(monsters)} 个怪物")
        print("=" * 80)
        
        if monsters:
            print("\n怪物列表:")
            for i, monster in enumerate(monsters[:20]):  # 只显示前20个
                print(f"\n{i+1}. EID={monster['eid']}, ModelID={monster['model_id']}")
                print(f"   名称: {monster['name']}")
                print(f"   类名: {monster['class_name']}")
                print(f"   位置: ({monster['location'][0]:.2f}, {monster['location'][1]:.2f}, {monster['location'][2]:.2f})")
                print(f"   速度: ({monster['velocity'][0]:.2f}, {monster['velocity'][1]:.2f}, {monster['velocity'][2]:.2f})")
                if monster['distance'] > 0:
                    print(f"   距离: {monster['distance']/100:.1f}m")
        else:
            print("\n⚠ 未找到任何怪物")
            print("  可能原因:")
            print("  1. 当前场景没有怪物")
            print("  2. 偏移值需要更新")
            print("  3. 过滤条件太严格")
        
    finally:
        reader.detach()
        print("\n✓ 已断开连接")


if __name__ == "__main__":
    main()
