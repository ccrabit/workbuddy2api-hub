"""流式响应空闲心跳（StreamKeepalive）的行为约束。

真实故障：网关挂在 nginx / Lucky / 各类隧道后面时，中间设备按「多久没收到
字节」判活（nginx 的 proxy_read_timeout 默认就是 60 秒）。上游长思考、排队或
卡住的时候，本代理一个字节都不写，中间设备就把流单方面掐掉，客户端看到的
是「回答到一半断线」，而服务端日志里只有一次 client_aborted。

这里钉住五件事：
  1. 空闲够久就写 SSE 注释行 `: keepalive`（注释行所有客户端都会忽略）；
  2. 一直在出字的流里一次都不写——心跳不能污染正常流，也不能增加延迟；
  3. write() 会重置计时，客户端还在收数据时绝不插心跳；
  4. stop() 之后线程必须退出，且不再往已经结束的响应里写字节；
  5. 环境变量口径：默认 10 秒，0 关掉，非法值回默认，上限 300 秒。

另外钉住源码层面：三个流式出口（chat.completions / responses / messages）都
必须走 StreamKeepalive.write 而不是直接写 wfile，否则改一处漏两处。
"""
import io
import os
import re
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wb_proxy  # noqa: E402


class FakeWFile:
    """记录每次写入的块，模拟 wfile（无缓冲文件对象）。"""

    def __init__(self):
        self.chunks = []
        self.lock = threading.Lock()

    def write(self, data):
        with self.lock:
            self.chunks.append(bytes(data))

    def flush(self):
        pass

    def text(self):
        with self.lock:
            return b"".join(self.chunks)


class EnvMixin(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("WB_STREAM_KEEPALIVE_SECONDS")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("WB_STREAM_KEEPALIVE_SECONDS", None)
        else:
            os.environ["WB_STREAM_KEEPALIVE_SECONDS"] = self._saved


class KeepaliveIntervalTests(EnvMixin):
    def test_default_is_ten_seconds(self):
        os.environ.pop("WB_STREAM_KEEPALIVE_SECONDS", None)
        self.assertEqual(wb_proxy.stream_keepalive_seconds(), 10.0)

    def test_zero_and_negative_disable(self):
        for raw in ("0", "0.0", "-3"):
            os.environ["WB_STREAM_KEEPALIVE_SECONDS"] = raw
            self.assertEqual(wb_proxy.stream_keepalive_seconds(), 0.0, raw)

    def test_blank_and_garbage_fall_back_to_default(self):
        for raw in ("", "   ", "abc", "10s"):
            os.environ["WB_STREAM_KEEPALIVE_SECONDS"] = raw
            self.assertEqual(wb_proxy.stream_keepalive_seconds(), 10.0, raw)

    def test_explicit_value_and_cap(self):
        os.environ["WB_STREAM_KEEPALIVE_SECONDS"] = "3.5"
        self.assertEqual(wb_proxy.stream_keepalive_seconds(), 3.5)
        os.environ["WB_STREAM_KEEPALIVE_SECONDS"] = "1000"
        self.assertEqual(wb_proxy.stream_keepalive_seconds(), 300.0)


class IdleKeepaliveTests(unittest.TestCase):
    def test_idle_stream_gets_comment_frames(self):
        out = FakeWFile()
        ka = wb_proxy.StreamKeepalive(out, interval=0.05).start()
        try:
            time.sleep(0.28)
        finally:
            ka.stop()
        self.assertGreaterEqual(ka.keepalives, 2, "idle stream must be kept alive")
        self.assertEqual(out.text(), wb_proxy.StreamKeepalive.FRAME * ka.keepalives)

    def test_frame_is_an_sse_comment(self):
        frame = wb_proxy.StreamKeepalive.FRAME
        self.assertTrue(frame.startswith(b":"), "SSE comments start with a colon")
        self.assertTrue(frame.endswith(b"\n\n"), "every SSE event ends with a blank line")
        # 注释行不能被解析成事件：data 行只允许以 "data:" 开头。
        self.assertNotIn(b"data:", frame)

    def test_busy_stream_never_gets_a_frame(self):
        out = FakeWFile()
        ka = wb_proxy.StreamKeepalive(out, interval=0.08).start()
        try:
            for _ in range(20):
                ka.write(b"data: {}\n\n")
                time.sleep(0.01)
        finally:
            ka.stop()
        self.assertEqual(ka.keepalives, 0, "a stream that keeps writing needs no heartbeat")
        self.assertNotIn(wb_proxy.StreamKeepalive.FRAME, out.text())

    def test_write_resets_the_timer(self):
        out = FakeWFile()
        ka = wb_proxy.StreamKeepalive(out, interval=0.1).start()
        try:
            time.sleep(0.06)
            ka.write(b"data: {\"x\":1}\n\n")   # 计时重启，心跳不该来
            time.sleep(0.06)
            self.assertEqual(ka.keepalives, 0)
            time.sleep(0.18)                   # 这次真的闲下来
        finally:
            ka.stop()
        self.assertGreaterEqual(ka.keepalives, 1)

    def test_stop_is_idempotent_and_silences_the_thread(self):
        out = FakeWFile()
        ka = wb_proxy.StreamKeepalive(out, interval=0.05).start()
        time.sleep(0.12)
        ka.stop()
        seen = len(out.chunks)
        time.sleep(0.15)
        self.assertEqual(len(out.chunks), seen, "no writes after stop()")
        ka.stop()                              # 再来一次不能炸
        self.assertTrue(ka.closed)
        self.assertTrue(all(t is not ka._thread for t in threading.enumerate()))

    def test_write_after_stop_is_dropped(self):
        out = FakeWFile()
        ka = wb_proxy.StreamKeepalive(out, interval=0.05).start()
        ka.stop()
        ka.write(b"data: late\n\n")
        self.assertEqual(out.chunks, [])

    def test_zero_interval_starts_no_thread(self):
        out = FakeWFile()
        ka = wb_proxy.StreamKeepalive(out, interval=0).start()
        try:
            time.sleep(0.12)
            self.assertEqual(ka.keepalives, 0)
            self.assertIsNone(ka._thread)
        finally:
            ka.stop()

    def test_context_manager_stops_the_thread(self):
        out = FakeWFile()
        with wb_proxy.StreamKeepalive(out, interval=0.05) as ka:
            self.assertIsNotNone(ka._thread)
            time.sleep(0.1)
        self.assertTrue(ka.closed)
        self.assertTrue(all(t is not ka._thread for t in threading.enumerate()))

    def test_dead_socket_stops_the_thread_quietly(self):
        class Dead(FakeWFile):
            def write(self, data):
                raise BrokenPipeError("gone")

        out = Dead()
        ka = wb_proxy.StreamKeepalive(out, interval=0.05).start()
        time.sleep(0.2)
        try:
            self.assertTrue(ka.closed, "a broken pipe must not keep the thread spinning")
        finally:
            ka.stop()

    def test_concurrent_writes_stay_whole(self):
        out = FakeWFile()
        ka = wb_proxy.StreamKeepalive(out, interval=0.02).start()
        payloads = [("data: %d\n\n" % i).encode() for i in range(40)]

        def pump(chunk):
            for _ in range(10):
                ka.write(chunk)
                time.sleep(0.001)

        threads = [threading.Thread(target=pump, args=(p,)) for p in payloads[:4]]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        ka.stop()
        allowed = set(payloads[:4]) | {wb_proxy.StreamKeepalive.FRAME}
        for chunk in out.chunks:
            self.assertIn(chunk, allowed, "writes must never interleave")


class SourceWiringTests(unittest.TestCase):
    """改一处漏两处是本项目最容易犯的错：三个流式出口都要走同一个写出口。"""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "wb_proxy.py")
        cls.src = io.open(path, encoding="utf-8").read()

    def handler_body(self, name):
        start = self.src.index("    def %s(" % name)
        nxt = self.src.find("\n    def ", start + 10)
        return self.src[start:nxt if nxt != -1 else len(self.src)]

    # 流结束后的终止标记（[DONE] / 错误帧）是**停止心跳之后**才写的，直写 wfile 是对的：
    # 那时候 keepalive 已经 stop()，再走它的 write() 反而会被 closed 挡掉。
    TERMINAL = re.compile(r'^\s*self\.wfile\.write\((?:b"data: \[DONE\]|f"data: \{err\})')

    def test_every_stream_handler_uses_the_write_outlet(self):
        for name in ("_chat_stream_response", "_responses_stream_response",
                     "_messages_stream_response"):
            body = self.handler_body(name)
            self.assertIn("StreamKeepalive(self.wfile)", body, name)
            self.assertIn("keepalive.stop()", body, name)
            leftovers = [ln for ln in body.splitlines()
                         if "self.wfile.write(" in ln and not self.TERMINAL.match(ln)]
            self.assertEqual(leftovers, [],
                             "%s must write stream frames through StreamKeepalive" % name)

    def test_env_knob_is_documented_in_the_readme(self):
        readme = io.open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "README.md"), encoding="utf-8").read()
        self.assertIn("WB_STREAM_KEEPALIVE_SECONDS", readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
