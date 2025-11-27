"""测试玩家位置获取"""
import ctypes
import struct
import psutil
from ctypes import wintypes

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

# 偏移
OFFSET_WORLD = 0x6FCA098
OFFSET_GAMEENGINE = 0x6FC64A0
OFFSET_GAMEENGINE_ALT = 0x6E63030  # 备用偏移
OFFSET_GAMESTATE = 0x130
OFFSET_GAMEINSTANCE = 0xE18
OFFSET_LOCALPLAYERS = 0x38
OFFSET_PLAYERCONTROLLER = 0x30
OFFSET_ACKNOWLEDGEDPAWN = 0x320
OFFSET_PLAYER_CURRENTLOCATION = 0x914
ACTOR_ROOTCOMPONENT = 0x160
SCENECOMPONENT_COMPONENTTOWORLD = 0x1C0

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

def read_int64(handle, address):
    data = read_bytes(handle, address, 8)
    return struct.unpack('<Q', data)[0] if data else 0

def read_vector3(handle, address):
    data = read_bytes(handle, address, 12)
    if data:
        return struct.unpack('<fff', data)
    return (0.0, 0.0, 0.0)

def is_valid_pointer(ptr):
    return ptr > 0x10000 and ptr < 0x7FFFFFFFFFFF

def main():
    print("=" * 80)
    print("测试玩家位置获取")
    print("=" * 80)
    
    handle, module_base = attach_process()
    if not handle:
        print("❌ 无法附加到游戏进程")
        return
    
    print(f"✓ 已附加到进程")
    print(f"  模块基址: 0x{module_base:X}")
    
    # 方法1：通过 GEngine -> GameInstance -> LocalPlayer -> PlayerController -> Pawn
    print("\n【方法1：GEngine 路径（主偏移）】")
    print("-" * 80)
    
    game_engine_addr = module_base + OFFSET_GAMEENGINE
    print(f"1. GEngine 地址: 0x{game_engine_addr:X}")
    
    game_engine = read_int64(handle, game_engine_addr)
    print(f"2. GEngine 指针: 0x{game_engine:X}")
    if not is_valid_pointer(game_engine):
        print("   ❌ GEngine 指针无效")
        
        # 尝试备用偏移
        print("\n【方法1B：GEngine 路径（备用偏移）】")
        print("-" * 80)
        game_engine_addr_alt = module_base + OFFSET_GAMEENGINE_ALT
        print(f"1. GEngine 地址（备用）: 0x{game_engine_addr_alt:X}")
        game_engine = read_int64(handle, game_engine_addr_alt)
        print(f"2. GEngine 指针: 0x{game_engine:X}")
        if not is_valid_pointer(game_engine):
            print("   ❌ GEngine 指针仍然无效")
            print("   可能原因：")
            print("   - 在主菜单（GEngine 未初始化）")
            print("   - 需要进入游戏世界")
        else:
            print("   ✓ 备用偏移有效！")
    else:
        print("   ✓ GEngine 指针有效")
        
        game_instance = read_int64(handle, game_engine + OFFSET_GAMEINSTANCE)
        print(f"3. GameInstance 指针: 0x{game_instance:X}")
        if not is_valid_pointer(game_instance):
            print("   ❌ GameInstance 指针无效")
        else:
            print("   ✓ GameInstance 指针有效")
            
            local_players_array_addr = game_instance + OFFSET_LOCALPLAYERS
            print(f"4. LocalPlayers 数组地址: 0x{local_players_array_addr:X}")
            
            local_players_array = read_int64(handle, local_players_array_addr)
            print(f"5. LocalPlayers 数组指针: 0x{local_players_array:X}")
            if not is_valid_pointer(local_players_array):
                print("   ❌ LocalPlayers 数组指针无效")
            else:
                print("   ✓ LocalPlayers 数组指针有效")
                
                local_player = read_int64(handle, local_players_array)
                print(f"6. LocalPlayer[0] 指针: 0x{local_player:X}")
                if not is_valid_pointer(local_player):
                    print("   ❌ LocalPlayer 指针无效")
                else:
                    print("   ✓ LocalPlayer 指针有效")
                    
                    player_controller = read_int64(handle, local_player + OFFSET_PLAYERCONTROLLER)
                    print(f"7. PlayerController 指针: 0x{player_controller:X}")
                    if not is_valid_pointer(player_controller):
                        print("   ❌ PlayerController 指针无效")
                    else:
                        print("   ✓ PlayerController 指针有效")
                        
                        pawn = read_int64(handle, player_controller + OFFSET_ACKNOWLEDGEDPAWN)
                        print(f"8. Pawn 指针: 0x{pawn:X}")
                        if not is_valid_pointer(pawn):
                            print("   ❌ Pawn 指针无效")
                        else:
                            print("   ✓ Pawn 指针有效")
                            
                            # 方法A：直接读取 CurrentLocation
                            print(f"\n   方法A：直接读取 CurrentLocation (offset 0x{OFFSET_PLAYER_CURRENTLOCATION:X})")
                            pos_a = read_vector3(handle, pawn + OFFSET_PLAYER_CURRENTLOCATION)
                            print(f"   位置: ({pos_a[0]:.2f}, {pos_a[1]:.2f}, {pos_a[2]:.2f})")
                            
                            # 方法B：通过 RootComponent
                            print(f"\n   方法B：通过 RootComponent")
                            root_component = read_int64(handle, pawn + ACTOR_ROOTCOMPONENT)
                            print(f"   RootComponent 指针: 0x{root_component:X}")
                            if is_valid_pointer(root_component):
                                print("   ✓ RootComponent 指针有效")
                                transform_addr = root_component + SCENECOMPONENT_COMPONENTTOWORLD
                                pos_b = read_vector3(handle, transform_addr + 0x10)
                                print(f"   位置: ({pos_b[0]:.2f}, {pos_b[1]:.2f}, {pos_b[2]:.2f})")
                            else:
                                print("   ❌ RootComponent 指针无效")
    
    # 方法2：通过 GWorld -> GameState（如果有玩家信息）
    print("\n【方法2：GWorld 路径】")
    print("-" * 80)
    
    world_addr = module_base + OFFSET_WORLD
    print(f"1. World 地址: 0x{world_addr:X}")
    
    world = read_int64(handle, world_addr)
    print(f"2. World 指针: 0x{world:X}")
    if not is_valid_pointer(world):
        print("   ❌ World 指针无效")
    else:
        print("   ✓ World 指针有效")
        
        game_state = read_int64(handle, world + OFFSET_GAMESTATE)
        print(f"3. GameState 指针: 0x{game_state:X}")
        if is_valid_pointer(game_state):
            print("   ✓ GameState 指针有效")
            print("   （GameState 通常不直接包含玩家位置）")
    
    kernel32.CloseHandle(handle)

if __name__ == "__main__":
    main()
