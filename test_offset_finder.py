"""测试 OffsetFinder"""
import sys
sys.path.insert(0, 'src')

from utils.OffsetFinder import auto_find_offsets

if __name__ == "__main__":
    print("测试 OffsetFinder")
    print("=" * 80)
    
    offsets = auto_find_offsets()
    
    if offsets:
        print("\n生成的代码:")
        print("=" * 80)
        print("# Python")
        for name, offset in offsets.items():
            if offset is not None:
                print(f"{name} = 0x{offset:X}")
        
        print("\n# C#")
        for name, offset in offsets.items():
            if offset is not None:
                print(f"const long {name} = 0x{offset:X};")
    else:
        print("❌ 偏移查找失败")
