from __future__ import annotations

import argparse
import gc
import json
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import soundfile as sf
import torch


def _build_model(args: argparse.Namespace):
    sys.path.insert(0, str(Path(args.repo).resolve()))
    from indextts.infer_v2 import IndexTTS2
    from indextts.utils.model_download import ensure_models_available

    aux = ensure_models_available(args.model_dir)
    tts = IndexTTS2(
        cfg_path=str(Path(args.model_dir) / "config.yaml"),
        model_dir=args.model_dir,
        use_fp16=args.fp16,
        use_cuda_kernel=False,
        use_qwen_emo=args.qwen_emo,
        aux_paths=aux,
    )

    if args.semantic_on_cpu:
        tts.semantic_model.to("cpu")
        torch.cuda.empty_cache()

        def get_emb(input_features, attention_mask):
            device = next(tts.semantic_model.parameters()).device
            out = tts.semantic_model(
                input_features=input_features.to(device),
                attention_mask=attention_mask.to(device),
                output_hidden_states=True,
            )
            feat = out.hidden_states[17]
            mean = tts.semantic_mean.to(feat.device)
            std = tts.semantic_std.to(feat.device)
            return ((feat - mean) / std).to(tts.device)

        tts.get_emb = get_emb

    return tts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--semantic-on-cpu", action="store_true")
    parser.add_argument("--qwen-emo", action="store_true")
    args = parser.parse_args()

    print(">> loading IndexTTS2...", flush=True)
    tts = _build_model(args)
    lock = threading.Lock()
    print(">> IndexTTS2 ready", flush=True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args_) -> None:
            print(fmt % args_, flush=True)

        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._json(200, {"status": "ok"})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path == "/shutdown":
                self._json(200, {"status": "shutting down"})

                def _stop() -> None:
                    with lock:
                        server.shutdown()

                threading.Thread(target=_stop, daemon=True).start()
                return
            if self.path != "/synthesize":
                self._json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                text = " ".join(str(payload["text"]).split())
                out_path = Path(payload["out_path"]).resolve()
                ref_audio = str(Path(payload["ref_audio"]).resolve())
                if not text:
                    raise ValueError("empty text")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with lock:
                    tts.infer(
                        spk_audio_prompt=ref_audio,
                        text=text,
                        output_path=str(out_path),
                        verbose=False,
                    )
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                info = sf.info(str(out_path))
                self._json(
                    200,
                    {
                        "audio_path": str(out_path),
                        "duration_ms": round(info.duration * 1000),
                        "sample_rate": info.samplerate,
                    },
                )
            except Exception as exc:
                traceback.print_exc()
                self._json(
                    500,
                    {
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc()[-2000:],
                    },
                )

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f">> listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()
    server.server_close()


if __name__ == "__main__":
    main()
