"""测试怪物过滤逻辑"""
import ctypes
import struct
import math
import psutil
from ctypes import wintypes

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

# 偏移
OFFSET_WORLD = 0x6FCA098
GNAMES_OFFSET = 0x6E1FA80
OFFSET_GAMESTATE = 0x130
OFFSET_MONSTERMAP = 0x668
OFFSET_EID = 0xAE4
OFFSET_MODELID = 0x950
OFFSET_ALREADYDEAD = 0x122B
OFFSET_OBJTYPE = 0x931
OFFSET_CURRENTLOCATION = 0x914
OFFSET_CURRENTVELOCITY = 0x920

kernel32 = ctypes.windll.kernel32

def attach_process():
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == "EM-Win64-Shipping.exe":
            pid = proc.info['pid']
            handle = kernel32.OpenProcess(
                PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid
            )
            if not handle:
                continue
            
            psapi = ctypes.windll.psapi
            hModules = (wintypes.HMODULE * 1024)()
            cb_needed = wintypes.DWORD()
            
            if psapi.EnumProcessModules(
                handle,
                ctypes.byref(hModules),
                ctypes.sizeof(hModules),
                ctypes.byref(cb_needed)
            ):
                if hModules[0]:
                    return handle, hModules[0]
    return None, None

def read_bytes(handle, address, size):
    buffer = ctypes.create_string_buffer(size)
    bytes_read = ctypes.c_size_t()
    success = kernel32.ReadProcessMemory(
        handle,
        ctypes.c_void_p(address),
        buffer,
        size,
        ctypes.byref(bytes_read)
    )
    return buffer.raw if success else None

def read_int32(handle, address):
    data = read_bytes(handle, address, 4)
    return struct.unpack('<i', data)[0] if data else 0

def read_int64(handle, address):
    data = read_bytes(handle, address, 8)
    return struct.unpack('<Q', data)[0] if data else 0

def read_short(handle, address):
    data = read_bytes(handle, address, 2)
    return struct.unpack('<h', data)[0] if data else 0

def read_bool(handle, address):
    data = read_bytes(handle, address, 1)
    return data[0] != 0 if data else False

def read_vector3(handle, address):
    data = read_bytes(handle, address, 12)
    if data:
        return struct.unpack('<fff', data)
    return (0.0, 0.0, 0.0)

def is_valid_pointer(ptr):
    return ptr > 0x10000 and ptr < 0x7FFFFFFFFFFF

def read_fname(handle, gnames_address, object_ptr):
    try:
        name_index = read_int32(handle, object_ptr + 0x18)
        if name_index == 0:
            return ""
        
        chunk_offset = name_index >> 16
        name_offset = name_index & 0xFFFF
        
        chunk_ptr = read_int64(handle, gnames_address + 8 * (chunk_offset + 2))
        if not is_valid_pointer(chunk_ptr):
            return ""
        
        name_pool_chunk = chunk_ptr + 2 * name_offset
        header = read_short(handle, name_pool_chunk)
        name_length = header >> 6
        
        if name_length <= 0 or name_length > 1024:
            return ""
        
        buffer = read_bytes(handle, name_pool_chunk + 2, name_length)
        if buffer:
            return buffer.decode('ascii', errors='ignore').rstrip('\0')
        return ""
    except:
        return ""

def main():
    print("=" * 80)
    print("测试怪物过滤逻辑")
    print("=" * 80)
    
    handle, module_base = attach_process()
    if not handle:
        print("❌ 无法附加到游戏进程")
        return
    
    print(f"✓ 已附加到进程")
    print(f"  模块基址: 0x{module_base:X}")
    
    gnames_address = module_base + GNAMES_OFFSET
    
    # 获取 GameState
    world_addr = module_base + OFFSET_WORLD
    world = read_int64(handle, world_addr)
    game_state = read_int64(handle, world + OFFSET_GAMESTATE)
    print(f"  GameState: 0x{game_state:X}")
    
    # 读取 MonsterMap
    monster_map_addr = game_state + OFFSET_MONSTERMAP
    map_data = read_bytes(handle, monster_map_addr, 40)
    data_ptr, array_num = struct.unpack('<Qi', map_data[:12])
    
    print(f"\nMonsterMap: {array_num} 个实体")
    print("=" * 80)
    
    found_count = 0
    filtered_count = 0
    
    for i in range(min(array_num, 100)):
        element_addr = data_ptr + i * 24
        element_data = read_bytes(handle, element_addr, 24)
        if not element_data:
            continue
        
        key, padding, value_ptr, hash_next, hash_index = struct.unpack('<iiQii', element_data)
        
        if hash_index == -1 or value_ptr == 0:
            continue
        
        # 读取基本信息
        eid = read_int32(handle, value_ptr + OFFSET_EID)
        if eid <= 0:
            continue
        
        already_dead = read_bool(handle, value_ptr + OFFSET_ALREADYDEAD)
        if already_dead:
            continue
        
        model_id = read_int32(handle, value_ptr + OFFSET_MODELID)
        obj_type = read_bytes(handle, value_ptr + OFFSET_OBJTYPE, 1)
        obj_type_val = obj_type[0] if obj_type else 0
        
        if obj_type_val not in [10, 11]:
            continue
        
        # 读取类名
        class_ptr = read_int64(handle, value_ptr + 0x10)
        class_name = ""
        if is_valid_pointer(class_ptr):
            class_name = read_fname(handle, gnames_address, class_ptr)
        
        location = read_vector3(handle, value_ptr + OFFSET_CURRENTLOCATION)
        
        print(f"\n实体 {i}:")
        print(f"  EID: {eid}")
        print(f"  ModelID: {model_id}")
        print(f"  ObjType: {obj_type_val}")
        print(f"  ClassName: {class_name}")
        print(f"  Location: ({location[0]:.2f}, {location[1]:.2f}, {location[2]:.2f})")
        
        # 检查过滤条件
        if class_name.startswith("BP_Mon_") or class_name.startswith("BP_Boss_"):
            print(f"  ✅ 通过过滤")
            found_count += 1
        else:
            print(f"  ❌ 被过滤（不是 BP_Mon_ 或 BP_Boss_ 开头）")
            filtered_count += 1
    
    print("\n" + "=" * 80)
    print(f"统计:")
    print(f"  通过过滤: {found_count} 个")
    print(f"  被过滤: {filtered_count} 个")
    print("=" * 80)
    
    kernel32.CloseHandle(handle)

if __name__ == "__main__":
    main()
