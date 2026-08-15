"""句子级分片 TTS 管线单元测试 — 断句器 + 单句合成 + SSE 格式化。

被测对象是 routes.py 新增的分片逻辑（不触碰真实 Edge TTS / LLM）:
  1. _split_sentences    流式断句（含 3.14 小数点防误断）
  2. _synthesize_chunk   单句合成（mock synthesize_with_word_boundary）
  3. _format_tts_chunk   合成结果 → SSE 行（audio/viseme 带 seq）
"""

from __future__ import annotations

from backend.routes import _format_tts_chunk, _split_sentences, _synthesize_chunk


class TestSplitSentences:
    def test_basic_two_sentences(self) -> None:
        sentences, rest = _split_sentences("你好。今天天气不错！")
        assert sentences == ["你好。", "今天天气不错！"]
        assert rest == ""

    def test_remainder_kept(self) -> None:
        sentences, rest = _split_sentences("你好。今天")
        assert sentences == ["你好。"]
        assert rest == "今天"

    def test_decimal_not_split(self) -> None:
        """ASCII '.' 不在句末符集合, 3.14 不会误断句。"""
        sentences, rest = _split_sentences("圆周率是3.14左右。")
        assert sentences == ["圆周率是3.14左右。"]

    def test_no_end_char_returns_empty(self) -> None:
        sentences, rest = _split_sentences("好的")
        assert sentences == []
        assert rest == "好的"

    def test_incremental_across_calls(self) -> None:
        """模拟 token 逐个到达: 标点后到时整句才被切出。"""
        s1, r1 = _split_sentences("你好")
        assert (s1, r1) == ([], "你好")
        s2, r2 = _split_sentences(r1 + "。世界")
        assert s2 == ["你好。"]
        assert r2 == "世界"

    def test_multi_end_chars_in_one_sentence(self) -> None:
        sentences, rest = _split_sentences("真的吗？！好的")
        assert sentences == ["真的吗？！"]
        assert rest == "好的"

    def test_long_run_without_punct_force_cut_at_comma(self) -> None:
        """模型漏打句末标点: 残句超长时在最近逗号处兜底强切, 延迟有界。"""
        long_text = "周末放松的方式有很多很多，比如睡个懒觉，慢慢煮早餐，泡杯咖啡，不用赶时间的感觉太治愈了"
        sentences, rest = _split_sentences(long_text)
        assert sentences  # 必须切出至少一句, 而不是全留残句
        assert len(rest) < 40
        assert "".join(sentences) + rest == long_text

    def test_long_run_without_comma_force_cut_all(self) -> None:
        """超长残句且无逗号 → 整段强切（有界延迟优先于韵律）。"""
        long_text = "我觉得最舒服的搭配就是睡个懒觉自然醒然后慢慢煮个早餐泡杯咖啡不用赶时间的感觉真的很治愈"
        sentences, rest = _split_sentences(long_text)
        assert sentences == [long_text]
        assert rest == ""


class TestSynthesizeChunk:
    async def test_success_with_boundaries(self, monkeypatch) -> None:
        async def fake_synth(text: str) -> tuple[bytes, list[dict]]:
            return b"\xff\xfb" + b"\x00" * 100, [{"offset": 0, "duration": 25000000, "text": text}]

        monkeypatch.setattr("backend.routes.synthesize_with_word_boundary", fake_synth)
        result = await _synthesize_chunk(0, "你好")
        assert result is not None
        assert result["audio"]["format"] == "mp3"
        # 边界时间 2.5s, 音频时长取 max(boundary_ms, mp3_frame_ms)
        assert result["audio"]["duration_ms"] >= 2500
        assert len(result["viseme"]) > 0
        assert all("time_ms" in f and "A" in f for f in result["viseme"])

    async def test_failure_returns_none(self, monkeypatch) -> None:
        async def fake_synth(text: str):
            raise RuntimeError("edge tts down")

        monkeypatch.setattr("backend.routes.synthesize_with_word_boundary", fake_synth)
        result = await _synthesize_chunk(0, "你好")
        assert result is None


class TestFormatTtsChunk:
    def test_audio_and_viseme_lines_with_seq(self) -> None:
        chunk = {
            "seq": 2,
            "result": {
                "audio": {"base64": "xx", "format": "mp3", "duration_ms": 1000},
                "viseme": [{"time_ms": 0.0, "A": 0.5, "I": 0, "U": 0, "E": 0, "O": 0}],
            },
        }
        text = "".join(_format_tts_chunk(chunk))
        assert "event: audio" in text
        assert '"seq": 2' in text
        assert "event: viseme" in text
        assert '"frames"' in text

    def test_failed_chunk_yields_nothing(self) -> None:
        lines = _format_tts_chunk({"seq": 3, "result": None})
        assert lines == []
