"""看板的样式表必须「整块活下来」。

背景：`dashboard.html` 里第二个 `<style>` 是面板与数据看板的全部样式。上游
v1.7.30 在统计条上加了 `@media (max-width: 860px)`，本层在同一位置有一段
自己的移动端兜底规则；合并时那个 `@media` 少了收尾的 `}`，于是它把**后面
所有规则**（整个 `#pageAnalytics` 看板设计 + `.wb-help`）都吞进了「窄屏才
生效」的分支里。

后果不是报错，而是静默降级：1484px 的桌面上看板没有栅格，KPI 卡片一张一行、
行高巨大——套件全都还是绿的，因为断言只查字符串在不在，不查它在哪一层。

这里钉住三件事：
  1. 每个 `<style>` 块的 `{` 与 `}` 数量相等（少一个就是整块失效的开始）；
  2. 关键字面规则处在**嵌套深度 0**：`#pageAnalytics{`、`.wb-help{`、
     `#cockpitRealm{`、`#cards{`、以及看板的 `.kpis` 栅格规则；
  3. 扫一遍所有「深度 > 0 的规则」，它们的父级必须是 `@media`——不能因为漏
     括号被别的规则包住。
"""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD = os.path.join(ROOT, "dashboard.html")

STYLE_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.S)


def style_blocks():
    with open(DASHBOARD, encoding="utf-8") as fh:
        html = fh.read()
    return [m.group(1) for m in STYLE_RE.finditer(html)]


def depth_before(css, index):
    """返回 css[:index] 处的嵌套深度（`{` 加一、`}` 减一）。"""
    depth = 0
    for m in re.finditer(r"[{}]", css[:index]):
        depth += 1 if m.group(0) == "{" else -1
    return depth


def at_rule_spans(css):
    """所有允许包规则的 at-rule（@media / @keyframes / @supports）的 [起, 止] 区间。"""
    spans = []
    for m in re.finditer(r"@(?:media|keyframes|-webkit-keyframes|supports)[^{]*\{", css):
        start = m.end() - 1
        depth = 0
        for k in re.finditer(r"[{}]", css[start:]):
            depth += 1 if k.group(0) == "{" else -1
            if depth == 0:
                spans.append((start, start + k.start()))
                break
    return spans


class DashboardStyleTests(unittest.TestCase):
    def test_every_style_block_has_balanced_braces(self):
        for i, css in enumerate(style_blocks()):
            self.assertEqual(
                css.count("{"), css.count("}"),
                "第 %d 个 <style> 块的括号不配平：%d 个 '{' vs %d 个 '}'" % (
                    i, css.count("{"), css.count("}"),
                ),
            )

    def test_panel_styles_are_not_swallowed_by_a_media_query(self):
        html = style_blocks()[1]
        keys = [
            "#pageAnalytics{",          # 看板整体（含调色板与栅格）
            "#pageAnalytics .kpis{",    # KPI 六列栅格
            ".wb-help{",                # 使用说明
            "#cockpitRealm{",           # cockpit 版本选择
            "#cards{",                  # 首页统计条
        ]
        for key in keys:
            idx = html.find(key)
            self.assertNotEqual(idx, -1, "%s 在样式表里不见了" % key)
            self.assertEqual(
                depth_before(html, idx), 0,
                "%s 被包在了别的规则里（深度 %d），桌面上不会生效" % (
                    key, depth_before(html, idx),
                ),
            )

    def test_nested_rules_are_only_inside_media_queries(self):
        """深度 > 0 的规则要么在 @media 里，要么说明有规则漏了 `}`。"""
        for i, css in enumerate(style_blocks()):
            spans = at_rule_spans(css)
            for m in re.finditer(r"[^{}]*\{", css):
                selector = m.group(0)[:-1].strip()
                if not selector or selector.startswith("@"):
                    continue
                if ";" in selector or ":" in selector:
                    continue  # 声明块残余，不是选择器
                start = m.start()
                if depth_before(css, start) == 0:
                    continue
                inside = any(a < start < b for a, b in spans)
                self.assertTrue(
                    inside,
                    "第 %d 个 <style> 块里 `%s` 嵌套在别的规则里，检查是不是漏了 '}'"
                    % (i, selector[:60]),
                )

    def test_analytics_kpi_grid_is_six_columns(self):
        html = style_blocks()[1]
        m = re.search(r"#pageAnalytics \.kpis\{([^}]*)\}", html)
        self.assertIsNotNone(m, "看板的 .kpis 栅格规则不见了")
        self.assertIn("grid", m.group(1))
        self.assertIn("repeat(6", m.group(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
