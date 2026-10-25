# -*- coding: utf-8 -*-
"""
旁听器 v2: 被动监听官方软件与鼠标之间的 HID 输入报告。

原理: Windows 的 HID 类驱动会把输入报告复制给"所有"打开了同一设备接口的句柄,
      这一点已在本机实测确认。所以我们可以开一个只读句柄当"免费抓包器"。

脚本只听不发, 不会向鼠标写入任何数据, 绝对安全。

用法:
  1. 双击 旁听.cmd   (默认监听 90 秒)
  2. 出现 ">>> 现在请打开官方软件 <<<" 后, 打开官方软件查看/刷新电量,
     建议多点几次刷新, 期间鼠标别动、保持醒着
  3. 结束后把 sniff_log.txt 发回分析

已知目标: 电量约 94%, 脚本会自动高亮所有"出现了 94(0x5E) 这个字节"的帧。
"""
import sys
import time
import ctypes
sys.path.insert(0, '.')
import diag as D

k32 = D.k32

# 鼠标常规报告(移动/按键)会刷屏, 用去重: 同样内容的帧只打一次 + 计数
SECS_DEFAULT = 90


def main():
    secs = SECS_DEFAULT
    if len(sys.argv) > 1:
        try:
            secs = int(sys.argv[1])
        except ValueError:
            pass

    log = open("sniff_log.txt", "w", encoding="utf-8")

    def out(s):
        print(s, flush=True)
        log.write(s + "\n")
        log.flush()

    devs = D.enumerate_hids()
    ls = []
    for d in devs:
        if d.vid != 0x248A or d.inlen <= 0:
            continue
        h = k32.CreateFileW(d.path, D.GENERIC_READ, 3, None, 3, D.FILE_FLAG_OVERLAPPED, None)
        if h == D.INVALID_HANDLE_VALUE or h is None:
            out("[跳过] %s (打不开 err=%d)" % (d, ctypes.get_last_error()))
            continue
        ev = k32.CreateEventW(None, True, False, None)
        ov = D.OVERLAPPED()
        ov.hEvent = ev
        L = max(d.inlen, 8)
        ls.append({"d": d, "h": h, "ev": ev, "ov": ov,
                   "buf": ctypes.create_string_buffer(L), "L": L,
                   "pending": False, "seen": {}, "n": 0})

    out("=" * 74)
    out("IN9 HID 旁听器  |  监听 %d 个接口, 持续 %d 秒" % (len(ls), secs))
    out("=" * 74)
    for x in ls:
        out("  %s" % x["d"])
    out("")
    out(">>> 现在请打开官方软件查看电量, 期间保持鼠标醒着 <<<")
    out(">>> (标准鼠标移动报告会刷屏, 已去重, 只显示新出现的帧类型) <<<")
    out("")

    def post(x):
        k32.ResetEvent(x["ev"])
        rn = ctypes.c_uint32(0)
        r = k32.ReadFile(x["h"], x["buf"], x["L"], ctypes.byref(rn), ctypes.byref(x["ov"]))
        if r:
            x["pending"] = False
            return bytes(x["buf"][:rn.value])
        if ctypes.get_last_error() == 997:   # ERROR_IO_PENDING
            x["pending"] = True
            return None
        x["pending"] = False
        return None

    def handle(x, got):
        """收到一帧: 去重后打印"""
        x["n"] += 1
        key = (len(got), D.hexs(got))
        rec = x["seen"].get(key)
        if rec is not None:
            rec[0] += 1
            return
        x["seen"][key] = [1]
        t = time.time() - t0
        tag = ""
        if len(got) > 8:
            tag = "  <== 非常规长帧"
        out("[%6.2fs] %s pid=%04X mi=%s (%d字节)%s" %
            (t, x["d"].product, x["d"].pid, x["d"].mi, len(got), tag))
        out("         %s" % D.hexs(got))
        hits = [i for i, b in enumerate(got) if b == 94]
        if hits:
            out("         *** 发现字节 94(0x5E) 在偏移 %s ***" % hits)
        # 常见电量字节提示: 偏移 0..20 之间出现 90..100 的值
        cand = [(i, b) for i, b in enumerate(got[:24]) if 50 <= b <= 100]
        if cand and len(got) > 2:
            out("         (疑似电量候选 %s)" % cand)

    t0 = time.time()
    for x in ls:
        got = post(x)
        if got:
            out("[启动前] %s -> %s" % (x["d"].product, D.hexs(got)))

    while time.time() - t0 < secs:
        left = secs - (time.time() - t0)
        if left > 0 and int(left) % 10 == 0 and int(left) != getattr(main, "_last", -1):
            main._last = int(left)
            out("     ...剩余 %d 秒..." % int(left))
        for x in ls:
            if not x["pending"]:
                got = post(x)
                if got:
                    handle(x, got)
                continue
            rc = k32.WaitForSingleObject(x["ev"], 100)
            if rc == 0:
                g = ctypes.c_uint32(0)
                if k32.GetOverlappedResult(x["h"], ctypes.byref(x["ov"]), ctypes.byref(g), False):
                    x["pending"] = False
                    if g.value > 0:
                        handle(x, bytes(x["buf"][:g.value]))

    out("")
    out("=" * 74)
    out("监听结束, 共 %d 帧" % sum(x["n"] for x in ls))
    out("=" * 74)
    out("各类帧汇总 (去重后):")
    any_long = False
    for x in ls:
        out("")
        out("接口 %s  总帧数=%d" % (x["d"], x["n"]))
        for (ln, hx), rec in sorted(x["seen"].items(), key=lambda kv: -kv[0][0]):
            out("   x%-5d %dB  %s" % (rec[0], ln, hx))
            if ln > 8:
                any_long = True
    out("")
    if any_long:
        out(">>> 存在长度 >8 的帧, 很可能就是私有协议帧, 重点看上面标注的那些 <<<")
    else:
        out(">>> 没抓到任何长度 >8 的帧: 官方软件很可能用的是 Feature Report")
        out("    (HidD_GetFeature 不会广播, 旁听抓不到) -> 需要换 USBPcap 抓包 <<<")
    log.close()

    # 排空挂起的异步 I/O, 必须做, 否则内核写已释放内存 -> Python 段错误
    for x in ls:
        try:
            g = ctypes.c_uint32(0)
            k32.CancelIoEx(x["h"], ctypes.byref(x["ov"]))
            k32.GetOverlappedResult(x["h"], ctypes.byref(x["ov"]), ctypes.byref(g), True)
        except Exception:
            pass
        k32.CloseHandle(x["ev"])
        k32.CloseHandle(x["h"])


if __name__ == "__main__":
    main()
