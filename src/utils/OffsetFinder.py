"""
内存偏移查找器 - 集成版本
自动查找游戏内存偏移
"""

import ctypes
import time
from typing import List, Dict, Optional
from collections import defaultdict
from ok import Logger

logger = Logger.get_logger(__name__)

# 尝试加载 C# 原生加速库
NATIVE_AVAILABLE = False
native_lib = None

try:
    try:
        native_lib = ctypes.CDLL("./OffsetFinderAOT.dll")
    except:
        native_lib = ctypes.CDLL("./OffsetFinderNative.dll")
    
    # 定义函数签名
    native_lib.AttachProcess.argtypes = [ctypes.c_char_p]
    native_lib.AttachProcess.restype = ctypes.c_int
    
    native_lib.Release.argtypes = []
    native_lib.Release.restype = None
    
    native_lib.GetModuleBase.argtypes = []
    native_lib.GetModuleBase.restype = ctypes.c_longlong
    
    native_lib.GetModuleSize.argtypes = []
    native_lib.GetModuleSize.restype = ctypes.c_longlong
    
    native_lib.SearchPattern.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_longlong), ctypes.c_int]
    native_lib.SearchPattern.restype = ctypes.c_int
    
    native_lib.ReadMemory.argtypes = [ctypes.c_longlong, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
    native_lib.ReadMemory.restype = ctypes.c_int
    
    NATIVE_AVAILABLE = True
    logger.info("✓ 已加载 C# 原生加速库")
except:
    logger.info("⚠ 未找到 C# DLL，使用纯 Python 模式")


class OffsetFinder:
    """内存偏移查找器"""
    
    def __init__(self, process_name: str = "EM-Win64-Shipping"):
        self.process_name = process_name
        self.module_base = 0
        self.module_size = 0
        
        if NATIVE_AVAILABLE:
            self._init_native(process_name)
        else:
            self._init_python(process_name)
    
    def _init_native(self, process_name: str):
        """使用 C# 原生库初始化"""
        if process_name.endswith('.exe'):
            process_name = process_name[:-4]
        
        result = native_lib.AttachProcess(process_name.encode('utf-8'))
        
        if result == 0:
            raise Exception(f"无法附加到进程: {process_name}")
        
        self.module_base = native_lib.GetModuleBase()
        self.module_size = native_lib.GetModuleSize()
        
        logger.info(f"✓ 已连接: {process_name}.exe")
        logger.info(f"  模块基址: 0x{self.module_base:X}")
        logger.info(f"  模块大小: 0x{self.module_size:X} ({self.module_size // 1024 // 1024} MB)")
    
    def _init_python(self, process_name: str):
        """使用纯 Python 初始化（备用）"""
        try:
            import pymem
            import pymem.process
            
            if not process_name.endswith('.exe'):
                process_name += '.exe'
            
            self.pm = pymem.Pymem(process_name)
            self.module = pymem.process.module_from_name(self.pm.process_handle, process_name)
            
            self.module_base = self.module.lpBaseOfDll
            self.module_size = self.module.SizeOfImage
            
            logger.info(f"✓ 已连接: {process_name} (PID: {self.pm.process_id})")
            logger.info(f"  模块基址: 0x{self.module_base:X}")
            logger.info(f"  模块大小: 0x{self.module_size:X} ({self.module_size // 1024 // 1024} MB)")
        except ImportError:
            raise Exception("请安装 pymem: pip install pymem")
    
    def __del__(self):
        """清理资源"""
        if NATIVE_AVAILABLE:
            native_lib.Release()
    
    def pattern_scan_all(self, pattern: str) -> List[int]:
        """扫描所有匹配"""
        if NATIVE_AVAILABLE:
            return self._pattern_scan_native(pattern)
        else:
            return self._pattern_scan_python(pattern)
    
    def _pattern_scan_native(self, pattern: str) -> List[int]:
        """使用 C# 原生库扫描"""
        max_results = 10000
        result_buffer = (ctypes.c_longlong * max_results)()
        
        count = native_lib.SearchPattern(
            pattern.encode('utf-8'),
            result_buffer,
            max_results
        )
        
        return list(result_buffer[:count])
    
    def _pattern_scan_python(self, pattern: str) -> List[int]:
        """纯 Python 扫描（备用）"""
        parts = pattern.split()
        pattern_bytes = bytearray()
        mask_bytes = bytearray()
        
        for part in parts:
            if part == '??':
                pattern_bytes.append(0)
                mask_bytes.append(0)
            else:
                pattern_bytes.append(int(part, 16))
                mask_bytes.append(1)
        
        pattern_len = len(pattern_bytes)
        results = []
        chunk_size = 4 * 1024 * 1024
        
        offset = 0
        while offset < self.module_size:
            try:
                addr = self.module_base + offset
                size = min(chunk_size, self.module_size - offset)
                
                buffer = self.pm.read_bytes(addr, size)
                
                i = 0
                while i <= len(buffer) - pattern_len:
                    match = True
                    for j in range(pattern_len):
                        if mask_bytes[j] and buffer[i + j] != pattern_bytes[j]:
                            match = False
                            break
                    
                    if match:
                        results.append(offset + i)
                    
                    i += 1
            except:
                pass
            
            offset += chunk_size
        
        return results
    
    def read_int(self, offset: int, size: int = 4) -> int:
        """读取整数"""
        if NATIVE_AVAILABLE:
            buffer = (ctypes.c_ubyte * size)()
            bytes_read = native_lib.ReadMemory(offset, buffer, size)
            
            if bytes_read == size:
                value = 0
                for i in range(size):
                    value |= buffer[i] << (i * 8)
                return value
            return 0
        else:
            addr = self.module_base + offset
            if size == 1:
                return self.pm.read_uchar(addr)
            elif size == 2:
                return self.pm.read_ushort(addr)
            elif size == 4:
                return self.pm.read_int(addr)
            elif size == 8:
                return self.pm.read_longlong(addr)
            return 0
    
    def calc_rip_relative(self, instruction_offset: int, instruction_len: int = 7) -> int:
        """计算 RIP 相对地址"""
        rip_offset = self.read_int(instruction_offset + instruction_len - 4, 4)
        
        if rip_offset & 0x80000000:
            rip_offset = rip_offset - 0x100000000
        
        next_instruction = instruction_offset + instruction_len
        target = next_instruction + rip_offset
        
        return target
    
    def find_gworld(self) -> Optional[int]:
        """查找 GWorld"""
        logger.info("【查找 GWorld】")
        start_time = time.time()
        
        patterns = [
            "48 8B 1D ?? ?? ?? ?? 48 85 DB 74 ?? 41 B0 01 33 D2 48 8B CB",
            "48 8B 1D ?? ?? ?? ?? 48 85 DB 74 ?? 41 B0 01 33 D2",
            "48 8B 1D ?? ?? ?? ?? 48 85 DB 74 ?? 41 B0 01",
        ]
        
        target_counts = defaultdict(int)
        
        for pattern in patterns:
            results = self.pattern_scan_all(pattern)
            logger.info(f"  找到 {len(results)} 个匹配")
            
            if 0 < len(results) <= 20:
                for offset in results:
                    target = self.calc_rip_relative(offset, 7)
                    target_counts[target] += 1
                
                if len(results) <= 5:
                    break
        
        if not target_counts:
            logger.warning("⚠ 未找到 GWorld")
            return None
        
        sorted_targets = sorted(target_counts.items(), key=lambda x: x[1], reverse=True)
        best = sorted_targets[0][0]
        elapsed = time.time() - start_time
        logger.info(f"✓ 推荐: 0x{best:X} (耗时: {elapsed:.2f}秒)")
        return best
    
    def find_gnames(self) -> Optional[int]:
        """查找 GNames"""
        logger.info("【查找 GNames】")
        start_time = time.time()
        
        patterns = [
            # lea 指令模式（更常见，优先使用）
            "4C 8D 05 ?? ?? ?? ?? EB ?? 48 8D 0D ?? ?? ?? ?? E8",  # lea r8, GFNamePool; jmp; lea rcx, GFNamePool; call
            "48 8D 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 4C 8B C0",        # lea rcx, GFNamePool; call FNamePool_Init; mov r8, rax
            "4C 8D 05 ?? ?? ?? ??",                                 # lea r8, GFNamePool (短模式)
            "48 8D 0D ?? ?? ?? ??",                                 # lea rcx, GFNamePool (短模式)
            
            # mov 指令模式（备用）
            "48 8B 05 ?? ?? ?? ?? 48 63 ?? 48 C1 ?? ?? 48 8D",
            "48 8B 05 ?? ?? ?? ?? 48 63 ?? 48 C1 ?? ?? 48 03",
            "48 8B 05 ?? ?? ?? ?? 48 63 ?? 48 C1",
        ]
        
        target_counts = defaultdict(int)
        
        for pattern in patterns:
            results = self.pattern_scan_all(pattern)
            logger.info(f"  找到 {len(results)} 个匹配")
            
            if 0 < len(results) <= 100:
                for offset in results:
                    target = self.calc_rip_relative(offset, 7)
                    target_counts[target] += 1
                
                if len(results) <= 20:
                    break
        
        if not target_counts:
            logger.warning("⚠ 未找到 GNames")
            return None
        
        sorted_targets = sorted(target_counts.items(), key=lambda x: x[1], reverse=True)
        best = sorted_targets[0][0]
        elapsed = time.time() - start_time
        logger.info(f"✓ 推荐: 0x{best:X} (耗时: {elapsed:.2f}秒)")
        return best
    
    def find_gengine(self) -> Optional[int]:
        """查找 GEngine"""
        logger.info("【查找 GEngine】")
        start_time = time.time()
        
        patterns = [
            # 最精确的模式 - GEngine 初始化序列
            "48 8B 4C 24 60 48 89 05 ?? ?? ?? ?? 48 85 C9 74",          # mov rcx, [rsp+60h]; mov cs:GEngine, rax; test rcx, rcx; jz
            
            # 写入指令（mov [rip+offset], rax）- GEngine 初始化时使用
            "E8 ?? ?? ?? ?? 48 8B C8 48 89 05 ?? ?? ?? ?? 48 85 C9 74",  # call; mov rcx, rax; mov cs:GEngine, rax; test rcx, rcx; jz
            "48 8B C8 48 89 05 ?? ?? ?? ?? 48 85 C9 74",                 # mov rcx, rax; mov cs:GEngine, rax; test rcx, rcx; jz
            "48 89 05 ?? ?? ?? ?? 48 85 C9 74",                          # mov cs:GEngine, rax; test rcx, rcx; jz
            
            # 读取指令（备用）
            "48 8B 0D ?? ?? ?? ?? 48 85 C9 74 ?? 48 8B 01",
            "48 8B 1D ?? ?? ?? ?? 48 85 DB 74 ?? 48 8B 03",
        ]
        
        target_counts = defaultdict(int)
        
        for i, pattern in enumerate(patterns):
            results = self.pattern_scan_all(pattern)
            logger.info(f"搜索: {pattern[:50]}...")
            logger.info(f"✓ 找到 {len(results)} 个匹配")
            
            if 0 < len(results) <= 100:
                # 对于写入指令（前4个模式），需要找到 mov 指令的位置
                if i < 4:
                    # 写入指令模式，需要找到 "48 89 05" 的位置
                    for offset in results:
                        # 根据不同模式调整偏移
                        if i == 0:  # "48 8B 4C 24 60 48 89 05"
                            mov_offset = offset + 5   # "48 89 05" 在偏移 +5
                        elif i == 1:  # "E8 ?? ?? ?? ?? 48 8B C8 48 89 05"
                            mov_offset = offset + 10  # "48 89 05" 在偏移 +10
                        elif i == 2:  # "48 8B C8 48 89 05"
                            mov_offset = offset + 4   # "48 89 05" 在偏移 +4
                        else:  # "48 89 05"
                            mov_offset = offset       # 直接就是
                        
                        target = self.calc_rip_relative(mov_offset, 7)
                        target_counts[target] += 1
                else:
                    # 读取指令，正常处理
                    for offset in results:
                        target = self.calc_rip_relative(offset, 7)
                        target_counts[target] += 1
                
                # 如果找到少量匹配，可能已经足够精确
                if len(results) <= 5:
                    break
        
        if not target_counts:
            logger.warning("⚠ 未找到 GEngine")
            return None
        
        # 按引用次数和地址值排序（引用次数优先，相同时选择地址更大的）
        sorted_targets = sorted(target_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
        
        logger.info(f"候选地址:")
        for offset, count in sorted_targets[:5]:
            logger.info(f"0x{offset:X} (引用 {count} 次)")
        
        best = sorted_targets[0][0]
        elapsed = time.time() - start_time
        logger.info(f"✓ 推荐: 0x{best:X} (耗时: {elapsed:.2f}秒)")
        return best
    
    def find_all_offsets(self) -> Dict[str, int]:
        """查找所有偏移"""
        logger.info("="*60)
        logger.info("开始自动查找内存偏移")
        logger.info("="*60)
        
        total_start = time.time()
        
        offsets = {}
        offsets['OFFSET_WORLD'] = self.find_gworld()
        offsets['GNAMES_OFFSET'] = self.find_gnames()
        offsets['OFFSET_GAMEENGINE'] = self.find_gengine()
        
        total_elapsed = time.time() - total_start
        
        logger.info("="*60)
        logger.info("查找完成")
        logger.info("="*60)
        
        for name, offset in offsets.items():
            if offset is not None:
                logger.info(f"{name} = 0x{offset:X}")
        
        logger.info(f"\n总耗时: {total_elapsed:.2f}秒")
        
        return offsets


def auto_find_offsets(process_name: str = "EM-Win64-Shipping") -> Optional[Dict[str, int]]:
    """
    自动查找游戏偏移的便捷函数
    
    Args:
        process_name: 进程名称
        
    Returns:
        偏移字典，失败返回 None
    """
    try:
        finder = OffsetFinder(process_name)
        offsets = finder.find_all_offsets()
        return offsets
    except Exception as e:
        logger.error(f"自动查找偏移失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


if __name__ == "__main__":
    # 测试
    offsets = auto_find_offsets()
    if offsets:
        print("\n生成的代码:")
        print("# Python")
        for name, offset in offsets.items():
            if offset is not None:
                print(f"{name} = 0x{offset:X}")
