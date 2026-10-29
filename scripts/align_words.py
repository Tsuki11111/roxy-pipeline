from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

import soundfile as sf
import torch
import torchaudio
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

SAMPLE_RATE = 16000


def _norm(text: str) -> str:
    text = "".join(text.split())
    for char in "，。！？；：、,.!?;:\"'“”‘’（）()《》【】[]—…":
        text = text.replace(char, "")
    return text


def _load_audio(path: Path) -> torch.Tensor:
    data, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
    wav = torch.from_numpy(data.mean(axis=1))
    if sample_rate != SAMPLE_RATE:
        wav = torchaudio.functional.resample(wav, sample_rate, SAMPLE_RATE)
    return wav


def _build_tokens(processor, text: str) -> tuple[list[int], list[int]]:
    vocab = processor.tokenizer.get_vocab()
    tokens: list[int] = []
    positions: list[int] = []
    for index, char in enumerate(text):
        token = char.lower()
        if token in vocab:
            tokens.append(vocab[token])
            positions.append(index)
    return tokens, positions


def _forced_spans(log_probs: torch.Tensor, tokens: list[int], blank_id: int):
    targets = torch.tensor([tokens], dtype=torch.long, device=log_probs.device)
    paths, _ = torchaudio.functional.forced_align(
        log_probs.unsqueeze(0), targets, blank=blank_id
    )
    path = paths[0].tolist()
    spans: list[tuple[int, int, int]] = []
    previous = blank_id
    for frame, token in enumerate(path):
        if token == blank_id:
            previous = token
            continue
        if token != previous:
            spans.append((token, frame, frame))
        else:
            spans[-1] = (spans[-1][0], spans[-1][1], frame)
        previous = token
    return spans


def _map_normalized(
    original: str, normalized: str, normalized_chars: list[dict]
) -> list[dict]:
    """Map timings from normalized text back onto original characters."""
    result = [
        {"text": char, "start_ms": None, "end_ms": None}
        for char in original
    ]
    matcher = difflib.SequenceMatcher(a=original, b=normalized)
    norm_index = {item["index"]: item for item in normalized_chars}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(min(i2 - i1, j2 - j1)):
                item = norm_index.get(j1 + offset)
                if item is not None:
                    result[i1 + offset] = {
                        "text": original[i1 + offset],
                        "start_ms": item["start_ms"],
                        "end_ms": item["end_ms"],
                    }
        elif tag == "replace":
            items = [
                norm_index[j]
                for j in range(j1, j2)
                if j in norm_index and norm_index[j]["start_ms"] is not None
            ]
            if items and i1 < i2:
                start = min(item["start_ms"] for item in items)
                end = max(item["end_ms"] for item in items)
                for index in range(i1, i2):
                    result[index] = {
                        "text": original[index],
                        "start_ms": start,
                        "end_ms": end,
                    }
    return result


def _fill_missing(chars: list[dict], line_start: int, line_end: int) -> list[dict]:
    known = [item for item in chars if item["start_ms"] is not None]
    if not known:
        span = max(1, (line_end - line_start) // max(1, len(chars)))
        for index, item in enumerate(chars):
            item["start_ms"] = line_start + index * span
            item["end_ms"] = line_start + (index + 1) * span
        return chars

    cursor = line_start
    for item in chars:
        if item["start_ms"] is None:
            item["start_ms"] = cursor
            item["end_ms"] = cursor
        else:
            cursor = item["end_ms"]
    return chars


def _stretch(chars: list[dict], line_end: int) -> list[dict]:
    known = [
        index
        for index, item in enumerate(chars)
        if item["end_ms"] > item["start_ms"]
    ]
    for position, index in enumerate(known):
        if position + 1 < len(known):
            next_start = chars[known[position + 1]]["start_ms"]
            chars[index]["end_ms"] = max(chars[index]["end_ms"], next_start)
        else:
            chars[index]["end_ms"] = max(chars[index]["end_ms"], line_end)
    return chars


def align_line(
    model,
    processor,
    audio_path: Path,
    text: str,
    line_start: int,
    line_end: int,
    device: str,
    normalizer=None,
) -> dict:
    spoken = normalizer.normalize(text) if normalizer is not None else text
    spoken = _norm(spoken)
    tokens, positions = _build_tokens(processor, spoken)
    if not tokens:
        return {"chars": _fill_missing([] if not text else [
            {"text": char, "start_ms": None, "end_ms": None} for char in text
        ], line_start, line_end), "normalized": spoken}

    waveform = _load_audio(audio_path)
    inputs = processor(
        waveform.numpy(), sampling_rate=SAMPLE_RATE, return_tensors="pt"
    )
    input_values = inputs.input_values.to(device)
    if next(model.parameters()).dtype == torch.float16:
        input_values = input_values.half()
    with torch.inference_mode():
        logits = model(input_values).logits
        log_probs = torch.log_softmax(logits.float(), dim=-1)[0]

    blank_id = processor.tokenizer.pad_token_id
    if blank_id is None:
        blank_id = 0
    spans = _forced_spans(log_probs, tokens, blank_id)
    frame_ms = 1000.0 * waveform.shape[0] / SAMPLE_RATE / max(1, log_probs.shape[0])

    normalized_chars: list[dict] = []
    span_index = 0
    for position in range(len(spoken)):
        if span_index < len(spans) and position == positions[span_index]:
            _, first, last = spans[span_index]
            start = line_start + round(first * frame_ms)
            end = line_start + round((last + 1) * frame_ms)
            normalized_chars.append(
                {
                    "index": position,
                    "text": spoken[position],
                    "start_ms": start,
                    "end_ms": max(start + 1, end),
                }
            )
            span_index += 1
        else:
            normalized_chars.append(
                {
                    "index": position,
                    "text": spoken[position],
                    "start_ms": None,
                    "end_ms": None,
                }
            )

    chars = _map_normalized(text, spoken, normalized_chars)
    chars = _fill_missing(chars, line_start, line_end)
    chars = _stretch(chars, line_end)
    return {"chars": chars, "normalized": spoken}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--repo", default="")
    parser.add_argument("--normalize", action="store_true")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.repo:
        sys.path.insert(0, str(Path(args.repo).resolve()))

    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    dtype = torch.float16 if device.startswith("cuda") else torch.float32

    processor = Wav2Vec2Processor.from_pretrained(
        args.model_dir, local_files_only=True
    )
    model = Wav2Vec2ForCTC.from_pretrained(
        args.model_dir, local_files_only=True, torch_dtype=dtype
    )
    try:
        model = model.to(device)
    except torch.cuda.OutOfMemoryError:
        torch.cuda.empty_cache()
        device = "cpu"
        model = model.to("cpu").float()
    model.eval()

    normalizer = None
    if args.normalize:
        try:
            from indextts.utils.front import TextNormalizer

            normalizer = TextNormalizer(enable_glossary=True)
            normalizer.load()
        except Exception as exc:
            print(f">> text normalizer unavailable, aligning raw text: {exc}", flush=True)

    results = []
    for line in payload["lines"]:
        try:
            aligned = align_line(
                model,
                processor,
                Path(line["audio_path"]),
                line["text"],
                int(line["start_ms"]),
                int(line["end_ms"]),
                device,
                normalizer,
            )
            results.append(
                {
                    "id": line["id"],
                    "seq": line["seq"],
                    "chars": aligned["chars"],
                    "normalized": aligned["normalized"],
                }
            )
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            model.to("cpu").float()
            device = "cpu"
            aligned = align_line(
                model,
                processor,
                Path(line["audio_path"]),
                line["text"],
                int(line["start_ms"]),
                int(line["end_ms"]),
                device,
                normalizer,
            )
            results.append(
                {
                    "id": line["id"],
                    "seq": line["seq"],
                    "chars": aligned["chars"],
                    "normalized": aligned["normalized"],
                }
            )
        print(
            f"aligned seq={line['seq']} chars={len(aligned['chars'])}",
            flush=True,
        )

    Path(args.output).write_text(
        json.dumps({"lines": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
