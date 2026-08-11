# 라벨 매칭에 쓰는 임베딩 모델을 앱에 넣을 수 있는 형태로 변환한다.
#
#
# ■ 평소에는 실행할 필요가 없다
#
#   변환 결과물은 이미 app/jogyeon_matcher/resources/model/ 에 커밋되어 있다.
#   앱을 실행하거나 빌드하는 데는 이 파일이 필요 없다.
#
#   다시 돌려야 하는 경우는 넷뿐이다.
#     - 실제 조견표에 한자가 나와서 어휘 축소 수위를 낮춰야 할 때
#     - 다른 임베딩 모델로 바꿀 때 (MODEL_ID 변경)
#     - onnxruntime 을 크게 올려서 호환성 문제가 생겼을 때
#     - 모델 파일이 손상·유실됐을 때
#
#
# ■ 사용법 (인터넷 되는 개발 PC에서)
#
#   pip install -r requirements-dev.txt     # 약 3GB, 처음 한 번만
#   python tools/export_model.py            # 2~3분 소요
#
#   실행하면 resources/model/ 을 통째로 지우고 새로 만든다.
#   끝나면 반드시 아래 두 검증을 다시 돌려 확인할 것.
#     python _experiments/exp09_injection_e2e.py    # 주입 정답지 22건
#     python _experiments/exp07_rules_smoke.py      # 규칙·제약 스모크
#
#
# ■ 무엇이 만들어지나  (app/jogyeon_matcher/resources/model/)
#
#   model_int8.onnx    58.5MB   추론용 모델
#   tokenizer.json      3.6MB   문장을 토큰 번호로 바꾸는 사전
#   meta.json             1KB   출처·설정·검증 결과 기록
#
#
# ■ 왜 이런 변환이 필요한가
#
#   원본은 PyTorch 모델이라 그대로 쓰면 exe 번들이 1.5GB를 넘는다.
#   두 단계를 거쳐 62MB로 줄인다.
#
#     1) 어휘 축소   250,002 -> 102,290  (한글·ASCII 라틴만 남김)
#                    우리 라벨이 선택하지 않는 토큰이라 결과는 원본과 동일하다
#     2) int8 양자화  448MB -> 58.5MB
#
#   변환 후에는 torch·transformers 없이 onnxruntime 만으로 돌아간다.
#   덕분에 인터넷이 없는 폐쇄망 PC에도 모델을 통째로 넣어 배포할 수 있다.
#
#   mean pooling 과 L2 정규화도 ONNX 그래프 안에 넣었다. 그래서 앱 코드는
#   (input_ids, attention_mask) 를 주면 바로 정규화된 임베딩을 받는다.

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import torch
from onnxruntime.quantization import QuantType, quantize_dynamic
from transformers import AutoModel, AutoTokenizer

from prune_vocab import ALLOWED_SCRIPTS, build_keep_ids, prune_model, prune_tokenizer

MODEL_ID = "intfloat/multilingual-e5-small"
OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "jogyeon_matcher" / "resources" / "model"
OPSET = 17

# e5 계열은 프리픽스가 필수. 대칭 유사도 용도이므로 양쪽 모두 query: 로 통일한다.
PREFIX = "query: "

# 수치 검증용 샘플. 조견표 라벨의 실제 분포를 반영한다.
PROBE = [
    "기본단가", "본인부담금", "주간활동기본형", "100%이하",
    "2등급이하1인가구", "급여량", "상한액", "김치찌개",
]


class E5Wrapper(torch.nn.Module):
    """mean pooling + L2 정규화까지 그래프에 포함시켜 런타임 코드를 줄인다."""

    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, input_ids, attention_mask):
        out = self.model(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        mask = attention_mask.unsqueeze(-1).float()
        pooled = (out * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        return torch.nn.functional.normalize(pooled, p=2, dim=1)


def mb(path: Path) -> float:
    return path.stat().st_size / 1024 / 1024


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    fp32_path = OUT_DIR / "_fp32.onnx"
    int8_path = OUT_DIR / "model_int8.onnx"

    print(f"[1/6] 모델 로드: {MODEL_ID}")
    hf_tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModel.from_pretrained(MODEL_ID).eval()

    tmp = OUT_DIR / "_hf"
    hf_tok.save_pretrained(tmp)
    tok_json = json.loads((tmp / "tokenizer.json").read_text(encoding="utf-8"))
    shutil.rmtree(tmp)
    vocab = tok_json["model"]["vocab"]

    # 축소 전 기준값 — 축소가 무손실인지 확인하는 데 쓴다
    enc = hf_tok([PREFIX + t for t in PROBE], padding=True, truncation=True,
                 max_length=64, return_tensors="pt")
    with torch.no_grad():
        ref = E5Wrapper(model).eval()(enc["input_ids"], enc["attention_mask"]).numpy()

    print(f"[2/6] 어휘 축소 (보존 체계: {sorted(ALLOWED_SCRIPTS)})")
    keep = build_keep_ids(vocab)
    print(f"      {len(vocab):,} -> {len(keep):,} ({len(keep) / len(vocab) * 100:.1f}%)")
    model = prune_model(model, keep)
    (OUT_DIR / "tokenizer.json").write_text(
        json.dumps(prune_tokenizer(tok_json, keep), ensure_ascii=False), encoding="utf-8"
    )

    print(f"[3/6] ONNX 내보내기 (opset {OPSET})")
    sample = torch.tensor([[0, 100, 200, 2]], dtype=torch.long)
    torch.onnx.export(
        E5Wrapper(model).eval(),
        (sample, torch.ones_like(sample)),
        str(fp32_path),
        input_names=["input_ids", "attention_mask"],
        output_names=["embedding"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "seq"},
            "attention_mask": {0: "batch", 1: "seq"},
            "embedding": {0: "batch"},
        },
        opset_version=OPSET,
        dynamo=False,
    )

    print("[4/6] 동적 int8 양자화")
    quantize_dynamic(model_input=fp32_path, model_output=int8_path, weight_type=QuantType.QInt8)
    fp32_path.unlink()

    print("[5/6] 검증 — 축소 전 torch fp32 대비")
    import onnxruntime as ort
    from tokenizers import Tokenizer

    rt_tok = Tokenizer.from_file(str(OUT_DIR / "tokenizer.json"))
    rt_tok.enable_truncation(max_length=64)
    rt_tok.enable_padding()
    encs = rt_tok.encode_batch([PREFIX + t for t in PROBE])

    sess = ort.InferenceSession(str(int8_path), providers=["CPUExecutionProvider"])
    got = sess.run(None, {
        "input_ids": np.array([e.ids for e in encs], dtype=np.int64),
        "attention_mask": np.array([e.attention_mask for e in encs], dtype=np.int64),
    })[0]

    # 정규화된 벡터이므로 내적이 곧 코사인. 1.0 에 가까울수록 동일.
    agreement = np.sum(ref * got, axis=1)

    print("[6/6] meta.json 기록")
    meta = {
        "model_id": MODEL_ID,
        "opset": OPSET,
        "quantization": "dynamic int8 (QInt8, weights only)",
        "vocab_pruning": {
            "allowed_scripts": sorted(ALLOWED_SCRIPTS),
            "ascii_only_latin": True,
            "vocab_size": len(keep),
            "original_vocab_size": len(vocab),
        },
        "prefix": PREFIX,
        "pooling": "mean pooling + L2 normalize (그래프 내장)",
        "embedding_dim": int(got.shape[1]),
        "verification": {
            "cosine_vs_original_fp32_min": round(float(agreement.min()), 6),
            "cosine_vs_original_fp32_mean": round(float(agreement.mean()), 6),
        },
    }
    (OUT_DIR / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    print(f"  model_int8.onnx : {mb(int8_path):6.1f} MB")
    print(f"  tokenizer.json  : {mb(OUT_DIR / 'tokenizer.json'):6.1f} MB")
    print(f"  임베딩 차원      : {meta['embedding_dim']}")
    print(f"  축소 전 대비 일치도 min={agreement.min():.6f} mean={agreement.mean():.6f}")
    print(f"\n완료: {OUT_DIR}")


if __name__ == "__main__":
    main()
