# -*- coding: utf-8 -*-
"""
在鼠标本体 (248A:5B2E, USB 有线直连) 的 mi_02 上扫命令码
每命令新句柄; 结果增量写入 scan_wired.txt (崩溃也不丢)
用法: python scan_wired.py [结束命令码, 默认0x40]
"""
import sys
import time
import ctypes
sys.path.insert(0, '.')
import diag as D

k32 = D.k32
LEN = 64
RID = 0x05

TARGET = None
for d in D.enumerate_hids():
    if d.vid == 0x248A and d.pid == 0x5B2E and d.mi == 0x02:
        TARGET = d
if TARGET is None:
    print("未找到 248A:5B2E mi_02 (鼠标本体)。请先插 USB 线。")
    sys.exit(1)
print("目标: %s" % TARGET)
print("路径: %s" % TARGET.path)

END = 0x40
if len(sys.argv) > 1:
    END = int(sys.argv[1], 0)


def mk(cmd):
    b = bytearray(LEN)
    b[0] = RID
    b[1] = cmd
    b[2] = 0x00
    b[3] = 0x01
    b[4] = 0x00
    b[32] = sum(b[5:32]) & 0xFF
    return bytes(b)


def once(data):
    h = k32.CreateFileW(TARGET.path, D.GENERIC_READ | D.GENERIC_WRITE, 3, None, 3,
                        D.FILE_FLAG_OVERLAPPED, None)
    if h == D.INVALID_HANDLE_VALUE or h is None:
        return False, []
    ev = k32.CreateEventW(None, True, False, None)
    ov = D.OVERLAPPED()
    ov.hEvent = ev
    buf = ctypes.create_string_buffer(LEN)
    ok, frames = False, []
    try:
        k32.ResetEvent(ev)
        wn = ctypes.c_uint32(0)
        r = k32.WriteFile(h, ctypes.create_string_buffer(data, LEN), LEN, ctypes.byref(wn), ctypes.byref(ov))
        if r:
            ok = True
        elif ctypes.get_last_error() == 997:
            g = ctypes.c_uint32(0)
            if k32.WaitForSingleObject(ev, 700) == 0 and k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(g), False):
                ok = True
        if ok:
            for _ in range(2):
                k32.ResetEvent(ev)
                rn = ctypes.c_uint32(0)
                rr = k32.ReadFile(h, buf, LEN, ctypes.byref(rn), ctypes.byref(ov))
                if rr:
                    frames.append(bytes(buf[:rn.value]))
                    continue
                if ctypes.get_last_error() != 997:
                    break
                g = ctypes.c_uint32(0)
                if k32.WaitForSingleObject(ev, 200) == 0 and k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(g), False):
                    frames.append(bytes(buf[:g.value]))
                else:
                    break
    finally:
        # 关键: 必须先撤销仍挂起的 I/O 并等它真正结束, 否则内核会往已释放的
        # OVERLAPPED/缓冲区里写数据 -> 段错误 (之前几次扫描崩溃就是这个原因)
        try:
            g = ctypes.c_uint32(0)
            k32.CancelIoEx(h, ctypes.byref(ov))
            k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(g), True)
        except Exception:
            pass
        k32.CloseHandle(ev)
        k32.CloseHandle(h)
    return ok, frames


out = open("scan_wired.txt", "w", encoding="utf-8")
hits = []
try:
    SKIP = {0x02}   # 实测: 0x02 会让设备卡死(之后所有写入都失败), 跳过
    for cmd in range(0x00, END):
        if cmd in SKIP:
            out.write("cmd=0x%02X 跳过(已知会使设备卡死)\n" % cmd)
            out.flush()
            continue
        data = mk(cmd)
        ok, frames = once(data)
        if not ok:
            time.sleep(1.5)          # 等设备恢复
            ok, frames = once(data)  # 重试一次
        if not ok:
            out.write("cmd=0x%02X 写入失败\n" % cmd)
            out.flush()
            continue
        if not frames:
            out.write("cmd=0x%02X 无响应\n" % cmd)
            out.flush()
            continue
        for f in frames:
            if bytes(f) == bytes(data):
                out.write("cmd=0x%02X 回显\n" % cmd)
            else:
                out.write("cmd=0x%02X ★数据 %s\n" % (cmd, D.hexs(f)))
                hits.append((cmd, f))
                print("cmd=0x%02X ★数据 %s" % (cmd, D.hexs(f[:48])), flush=True)
        out.flush()
        time.sleep(0.06)
finally:
    out.write("\n===== 有数据的命令 (%d) =====\n" % len(hits))
    for cmd, f in hits:
        out.write("cmd=0x%02X: %s\n" % (cmd, D.hexs(f)))
    out.close()
print("完成: 有数据命令 %d 个" % len(hits))
